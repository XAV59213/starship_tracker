"""Coordinator de détection du live Starship via spacex.com."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, EVENT_LAUNCH_SOON, EVENT_LIVE_ENDED, EVENT_LIVE_STARTED, LAUNCH_SOON_WINDOW, LIVE_URL, SCAN_INTERVAL_LIVE, SCAN_INTERVAL_ALL_LAUNCHES, SPACEX_ALL_TILES_URL, SPACEX_LAUNCH_URL, SPACEX_TILES_URL, TRACKED_VEHICLE

_LOGGER = logging.getLogger(__name__)


@dataclass
class LiveStatus:
    """Résultat d'une vérification."""

    is_live: bool
    url: str
    mission: str | None
    mission_status: str | None
    launch_date: str | None
    launch_site: str | None
    last_check: datetime
    next_mission: dict[str, Any] | None = None
    last_flight: dict[str, Any] | None = None
    missions: list[dict[str, Any]] | None = None


def _mission(tile: dict[str, Any]) -> dict[str, Any]:
    link = tile.get("link")
    return {
        "mission": tile.get("title"),
        "launch_date": tile.get("launchDate"),
        "launch_time": tile.get("launchTime"),
        "launch_site": tile.get("launchSite"),
        "mission_status": tile.get("missionStatus"),
        "vehicle": tile.get("vehicle"),
        "mission_type": tile.get("missionType"),
        "url": SPACEX_LAUNCH_URL.format(link=link) if link else LIVE_URL,
        "return_site": tile.get("returnSite"),
        # Le webcast (live / replay) est diffusé sur la page mission spacex.com
        "video_url": SPACEX_LAUNCH_URL.format(link=link) if link else LIVE_URL,
        "call_to_action": tile.get("callToAction"),
        "is_live": bool(tile.get("isLive")),
    }


def launch_datetime(mission: dict[str, Any] | None) -> datetime | None:
    """Combine launch_date / launch_time du flux SpaceX en datetime UTC."""
    if not mission or not mission.get("launch_date"):
        return None
    date = str(mission["launch_date"])
    time = mission.get("launch_time")
    candidates = [date]
    if time and "T" not in date:
        candidates.insert(0, f"{date[:10]}T{time}")
    for raw in candidates:
        parsed = dt_util.parse_datetime(raw)
        if parsed is None:
            day = dt_util.parse_date(raw[:10])
            if day is None:
                continue
            parsed = datetime(day.year, day.month, day.day)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_util.UTC)
        return dt_util.as_utc(parsed)
    return None


def _is_starship(tile: dict[str, Any]) -> bool:
    return (tile.get("vehicle") or "").lower() == TRACKED_VEHICLE.lower()


def _last_flight(tiles: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Dernier vol Starship terminé (missionStatus « final ») de la page /launches."""
    done = [t for t in tiles if _is_starship(t) and t.get("missionStatus") == "final" and t.get("launchDate")]
    if not done:
        return None
    return _mission(max(done, key=lambda t: (t["launchDate"], t.get("launchTime") or "")))


def _missions(tiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Toutes les missions Starship (passées + à venir), dédoublonnées, triées par date."""
    seen: dict[Any, dict[str, Any]] = {}
    for t in tiles:
        if _is_starship(t):
            seen.setdefault(t.get("link") or t.get("title"), t)
    ordered = sorted(seen.values(), key=lambda t: (t.get("launchDate") or "9999", t.get("launchTime") or ""))
    return [_mission(t) for t in ordered]


def _parse(tiles: list[dict[str, Any]]) -> LiveStatus:
    now = dt_util.utcnow()
    starship = sorted(
        (t for t in tiles if _is_starship(t)),
        key=lambda t: (t.get("launchDate") or "9999", t.get("launchTime") or ""),
    )
    # Priorité à une mission en live, sinon la prochaine mission Starship
    tile = next((t for t in starship if t.get("isLive")), starship[0] if starship else None)
    next_mission = _mission(starship[0]) if starship else None
    if tile is None:
        return LiveStatus(False, LIVE_URL, None, None, None, None, now, None)
    current = _mission(tile)
    return LiveStatus(
        is_live=bool(tile.get("isLive")),
        url=current["url"],
        mission=current["mission"],
        mission_status=current["mission_status"],
        launch_date=current["launch_date"],
        launch_site=current["launch_site"],
        last_check=now,
        next_mission=next_mission,
    )


async def async_fetch_tiles(session: aiohttp.ClientSession, url: str, timeout: int = 20) -> list[dict[str, Any]]:
    """Lit un flux de tuiles du site spacex.com (liste JSON)."""
    async with asyncio.timeout(timeout):
        async with session.get(url) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"spacex.com a répondu {resp.status}")
            data = await resp.json(content_type=None)
    if not isinstance(data, list):
        raise UpdateFailed("Format de réponse spacex.com inattendu")
    return data


async def async_fetch_live(session: aiohttp.ClientSession) -> LiveStatus:
    """Lit les tuiles « upcoming » du site spacex.com."""
    return _parse(await async_fetch_tiles(session, SPACEX_TILES_URL))


class StarshipLiveCoordinator(DataUpdateCoordinator[LiveStatus]):
    """Vérifie toutes les 5 min si Starship est en live sur spacex.com."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_live", update_interval=SCAN_INTERVAL_LIVE)
        self._session = async_get_clientsession(hass)
        # None = premier refresh : pas d'événement au démarrage de HA
        self._was_live: bool | None = None
        # (mission, date) déjà annoncés via EVENT_LAUNCH_SOON
        self._soon_fired: set[tuple[str | None, str]] = set()
        # Tuiles Starship de la page /launches complète (flux lourd, rafraîchi toutes les 6 h)
        self._all_starship: list[dict[str, Any]] | None = None
        self._all_checked: datetime | None = None

    async def _async_update_data(self) -> LiveStatus:
        upcoming: list[dict[str, Any]] | None = None
        error: Exception | None = None
        try:
            upcoming = await async_fetch_tiles(self._session, SPACEX_TILES_URL)
        except (aiohttp.ClientError, TimeoutError, ValueError, UpdateFailed) as err:
            error = err
        await self._async_refresh_all(force=upcoming is None)
        if upcoming is None and self._all_starship is None:
            raise UpdateFailed(f"spacex.com indisponible : {error}") from error
        tiles = list(upcoming or [])
        known = {t.get("link") for t in tiles}
        tiles += [
            t for t in self._all_starship or []
            if t.get("missionStatus") != "final" and t.get("link") not in known
        ]
        status = _parse(tiles)
        status.last_flight = _last_flight(self._all_starship or [])
        status.missions = _missions(tiles + (self._all_starship or []))
        self._fire_transition(status)
        self._fire_launch_soon(status)
        return status

    async def _async_refresh_all(self, force: bool = False) -> None:
        """Met à jour le cache du flux complet /launches (dernier vol, missions en cours)."""
        now = dt_util.utcnow()
        if not force and self._all_checked and now - self._all_checked < SCAN_INTERVAL_ALL_LAUNCHES:
            return
        self._all_checked = now
        try:
            tiles = await async_fetch_tiles(self._session, SPACEX_ALL_TILES_URL, timeout=60)
        except (aiohttp.ClientError, TimeoutError, ValueError, UpdateFailed) as err:
            _LOGGER.debug("Flux /launches complet indisponible : %s", err)
            return
        self._all_starship = [t for t in tiles if _is_starship(t)]

    def _fire_transition(self, status: LiveStatus) -> None:
        """Déclenche un événement HA quand le live commence ou se termine."""
        previous, self._was_live = self._was_live, status.is_live
        if previous is None or previous == status.is_live:
            return
        event = EVENT_LIVE_STARTED if status.is_live else EVENT_LIVE_ENDED
        self.hass.bus.async_fire(
            event,
            {
                "mission": status.mission,
                "url": status.url,
                "launch_date": status.launch_date,
                "launch_site": status.launch_site,
                "mission_status": status.mission_status,
            },
        )
        _LOGGER.info("%s : %s", event, status.mission)

    def _fire_launch_soon(self, status: LiveStatus) -> None:
        """Déclenche EVENT_LAUNCH_SOON une fois quand le lancement est à moins d'1 h."""
        nxt = status.next_mission
        launch = launch_datetime(nxt)
        if nxt is None or launch is None:
            return
        remaining = launch - dt_util.utcnow()
        key = (nxt.get("mission"), launch.isoformat())
        if not timedelta(0) < remaining <= LAUNCH_SOON_WINDOW or key in self._soon_fired:
            return
        self._soon_fired.add(key)
        self.hass.bus.async_fire(
            EVENT_LAUNCH_SOON,
            {
                "mission": nxt.get("mission"),
                "url": nxt.get("url"),
                "launch_time": launch.isoformat(),
                "minutes_remaining": int(remaining.total_seconds() // 60),
                "launch_site": nxt.get("launch_site"),
                "mission_status": nxt.get("mission_status"),
            },
        )
        _LOGGER.info("%s : %s", EVENT_LAUNCH_SOON, nxt.get("mission"))

