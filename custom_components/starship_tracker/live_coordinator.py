"""Coordinator de détection du live Starship via spacex.com."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_LAUNCH_SOON,
    EVENT_LIVE_ENDED,
    EVENT_LIVE_STARTED,
    LAUNCH_SOON_WINDOW,
    LIVE_URL,
    SCAN_INTERVAL_ALL_LAUNCHES,
    SCAN_INTERVAL_LIVE,
    SCAN_INTERVAL_MISSION_PAGE,
    SPACEX_ALL_TILES_URL,
    SPACEX_LAUNCH_URL,
    SPACEX_MISSION_URL,
    SPACEX_TILES_URL,
    TRACKED_VEHICLE,
)
from .translate import Translator, async_translate_mission
from .mission_date import (
    ParsedLaunch,
    apply_launch_fields,
    extract_mission_details,
    image_url,
    parse_mission_page,
    tile_needs_mission_page,
    tile_sort_key,
)

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


def _mission(
    tile: dict[str, Any],
    schedules: dict[str, ParsedLaunch | None] | None = None,
) -> dict[str, Any]:
    link = tile.get("link")
    parsed = schedules.get(link) if schedules is not None and link else None
    mission = {
        "mission": tile.get("title"),
        "link": link,
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
        "image": image_url(tile.get("ongoingMissionImageDesktop")) or image_url(tile.get("imageDesktop"))
        or image_url(tile.get("imageMobile")),
    }
    return apply_launch_fields(mission, tile, parsed)


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


def _schedules_for(
    tile: dict[str, Any], schedules: dict[str, ParsedLaunch | None] | None
) -> ParsedLaunch | None:
    link = tile.get("link")
    if schedules is None or not link:
        return None
    return schedules.get(link)


def _missions(
    tiles: list[dict[str, Any]],
    schedules: dict[str, ParsedLaunch | None] | None = None,
) -> list[dict[str, Any]]:
    """Toutes les missions Starship (passées + à venir), dédoublonnées, triées par date."""
    seen: dict[Any, dict[str, Any]] = {}
    for t in tiles:
        if _is_starship(t):
            seen.setdefault(t.get("link") or t.get("title"), t)
    ordered = sorted(seen.values(), key=lambda t: tile_sort_key(t, _schedules_for(t, schedules)))
    return [_mission(t, schedules) for t in ordered]


def _parse(
    tiles: list[dict[str, Any]],
    schedules: dict[str, ParsedLaunch | None] | None = None,
) -> LiveStatus:
    now = dt_util.utcnow()
    starship = sorted(
        (t for t in tiles if _is_starship(t)),
        key=lambda t: tile_sort_key(t, _schedules_for(t, schedules)),
    )
    # Priorité à une mission en live, sinon la prochaine mission Starship
    tile = next((t for t in starship if t.get("isLive")), starship[0] if starship else None)
    next_mission = _mission(starship[0], schedules) if starship else None
    if tile is None:
        return LiveStatus(False, LIVE_URL, None, None, None, None, now, None)
    current = _mission(tile, schedules)
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
                raise UpdateFailed(translation_domain=DOMAIN, translation_key="spacex_status", translation_placeholders={"status": str(resp.status), "url": "spacex.com"})
            data = await resp.json(content_type=None)
    if not isinstance(data, list):
        raise UpdateFailed(translation_domain=DOMAIN, translation_key="spacex_format", translation_placeholders={"url": "spacex.com"})
    return data


async def async_fetch_mission(session: aiohttp.ClientSession, link: str) -> dict[str, Any]:
    """Lit la page mission ``/missions/{link}`` (prose de la date de lancement)."""
    url = SPACEX_MISSION_URL.format(link=quote(str(link), safe="-._~"))
    async with asyncio.timeout(20):
        async with session.get(url) as resp:
            if resp.status != 200:
                raise UpdateFailed(translation_domain=DOMAIN, translation_key="spacex_status", translation_placeholders={"status": str(resp.status), "url": str(link)})
            data = await resp.json(content_type=None)
    if not isinstance(data, dict):
        raise UpdateFailed(translation_domain=DOMAIN, translation_key="spacex_format", translation_placeholders={"url": str(link)})
    return data


async def async_fetch_live(session: aiohttp.ClientSession) -> LiveStatus:
    """Lit les tuiles « upcoming » du site spacex.com."""
    return _parse(await async_fetch_tiles(session, SPACEX_TILES_URL))


class StarshipLiveCoordinator(DataUpdateCoordinator[LiveStatus]):
    """Vérifie toutes les 5 min si Starship est en live sur spacex.com."""

    def __init__(self, hass: HomeAssistant, translate: bool = False) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_live", update_interval=SCAN_INTERVAL_LIVE)
        self._session = async_get_clientsession(hass)
        self._translator = Translator(hass) if translate else None
        # None = premier refresh : pas d'événement au démarrage de HA
        self._was_live: bool | None = None
        # (mission, date) déjà annoncés via EVENT_LAUNCH_SOON
        self._soon_fired: set[tuple[str | None, str]] = set()
        # Tuiles Starship de la page /launches complète (flux lourd, rafraîchi toutes les 6 h)
        self._all_starship: list[dict[str, Any]] | None = None
        self._all_checked: datetime | None = None
        # link -> (fetch UTC, date extraite). Rafraîchi au plus toutes les 30 min.
        self._mission_cache: dict[str, tuple[datetime, ParsedLaunch | None]] = {}
        # link -> détails (image, description, liens) issus de la même page mission
        self._details_cache: dict[str, dict[str, Any]] = {}

    async def _async_update_data(self) -> LiveStatus:
        upcoming: list[dict[str, Any]] | None = None
        error: Exception | None = None
        try:
            upcoming = await async_fetch_tiles(self._session, SPACEX_TILES_URL)
        except (aiohttp.ClientError, TimeoutError, ValueError, UpdateFailed) as err:
            error = err
        await self._async_refresh_all(force=upcoming is None)
        if upcoming is None and self._all_starship is None:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="spacex_unavailable", translation_placeholders={"error": str(error)}) from error
        tiles = list(upcoming or [])
        known = {t.get("link") for t in tiles}
        tiles += [
            t for t in self._all_starship or []
            if t.get("missionStatus") != "final" and t.get("link") not in known
        ]
        combined = tiles + (self._all_starship or [])
        schedules = await self._async_load_schedules(combined)
        status = _parse(tiles, schedules)
        status.last_flight = _last_flight(self._all_starship or [])
        status.missions = _missions(combined, schedules)
        await self._async_add_details(status.next_mission)
        if self._translator is not None and status.next_mission:
            try:
                status.next_mission.update(await async_translate_mission(self._translator, status.next_mission))
            except Exception:  # noqa: BLE001 - la traduction ne doit jamais bloquer la mise à jour
                _LOGGER.debug("Traduction FR impossible", exc_info=True)
        # Repli image : page mission déjà en cache (aucune requête supplémentaire)
        for m in status.missions:
            if not m.get("image") and m.get("link") in self._details_cache:
                m["image"] = self._details_cache[m["link"]].get("mission_image")
        self._fire_transition(status)
        self._fire_launch_soon(status)
        return status

    async def _async_load_schedules(self, tiles: list[dict[str, Any]]) -> dict[str, ParsedLaunch | None]:
        """Pages mission des tuiles Starship sans date de flux."""
        links: list[str] = []
        for tile in tiles:
            if not _is_starship(tile) or not tile_needs_mission_page(tile):
                continue
            link = tile.get("link")
            if isinstance(link, str) and link not in links:
                links.append(link)
        if not links:
            return {}
        parsed = await asyncio.gather(*(self._async_cached_mission(link) for link in links))
        return dict(zip(links, parsed, strict=True))

    async def _async_cached_mission(self, link: str) -> ParsedLaunch | None:
        """Récupère la page mission, au plus une fois toutes les 30 minutes."""
        now = dt_util.utcnow()
        cached = self._mission_cache.get(link)
        if cached is not None and now - cached[0] < SCAN_INTERVAL_MISSION_PAGE:
            return cached[1]
        previous = cached[1] if cached else None
        try:
            payload = await async_fetch_mission(self._session, link)
            parsed = parse_mission_page(payload, now=now)
            self._details_cache[link] = extract_mission_details(payload)
        except (aiohttp.ClientError, TimeoutError, ValueError, UpdateFailed) as err:
            _LOGGER.debug("Page mission %s indisponible : %s", link, err)
            parsed = previous
        except Exception:
            _LOGGER.exception("Analyse de la page mission %s impossible", link)
            parsed = previous
        else:
            if parsed is not None and parsed.when is not None:
                _LOGGER.debug(
                    "Date de %s lue sur la page mission : %s (fenêtre %s min)",
                    link,
                    parsed.when.isoformat(),
                    parsed.launch_window_minutes,
                )
        self._mission_cache[link] = (now, parsed)
        return parsed

    async def _async_add_details(self, mission: dict[str, Any] | None) -> None:
        """Ajoute image / description / liens de la page mission à la prochaine mission."""
        if not mission:
            return
        link = mission.get("link")
        if not isinstance(link, str) or not link:
            return
        await self._async_cached_mission(link)
        details = self._details_cache.get(link) or {}
        mission.update(
            {
                "mission_image": details.get("mission_image") or mission.get("image"),
                "mission_image_mobile": details.get("mission_image_mobile"),
                "mission_description": details.get("mission_description"),
                "mission_links": details.get("mission_links") or [],
                "webcast_links": details.get("webcast_links") or [],
                "mission_url": mission.get("url"),
                "mission_videos": details.get("mission_videos") or [],
                "mission_infographic": details.get("mission_infographic"),
                "mission_infographic_mobile": details.get("mission_infographic_mobile"),
                "mission_countdown": details.get("mission_countdown") or [],
                "mission_timeline": details.get("mission_timeline") or [],
            }
        )

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

