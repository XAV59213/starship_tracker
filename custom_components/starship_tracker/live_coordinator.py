"""Coordinator de détection du live Starship via spacex.com."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LIVE_URL, SCAN_INTERVAL_LIVE, SPACEX_LAUNCH_URL, SPACEX_TILES_URL, TRACKED_VEHICLE

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


def _parse(tiles: list[dict[str, Any]]) -> LiveStatus:
    now = dt_util.utcnow()
    starship = [t for t in tiles if (t.get("vehicle") or "").lower() == TRACKED_VEHICLE.lower()]
    # Priorité à une mission en live, sinon la prochaine mission Starship
    tile = next((t for t in starship if t.get("isLive")), starship[0] if starship else None)
    if tile is None:
        return LiveStatus(False, LIVE_URL, None, None, None, None, now)
    link = tile.get("link")
    return LiveStatus(
        is_live=bool(tile.get("isLive")),
        url=SPACEX_LAUNCH_URL.format(link=link) if link else LIVE_URL,
        mission=tile.get("title"),
        mission_status=tile.get("missionStatus"),
        launch_date=tile.get("launchDate"),
        launch_site=tile.get("launchSite"),
        last_check=now,
    )


async def async_fetch_live(session: aiohttp.ClientSession) -> LiveStatus:
    """Lit les tuiles « upcoming » du site spacex.com."""
    async with asyncio.timeout(20):
        async with session.get(SPACEX_TILES_URL) as resp:
            if resp.status != 200:
                raise UpdateFailed(f"spacex.com a répondu {resp.status}")
            data = await resp.json(content_type=None)
    if not isinstance(data, list):
        raise UpdateFailed("Format de réponse spacex.com inattendu")
    return _parse(data)


class StarshipLiveCoordinator(DataUpdateCoordinator[LiveStatus]):
    """Vérifie toutes les 5 min si Starship est en live sur spacex.com."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_live", update_interval=SCAN_INTERVAL_LIVE)
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> LiveStatus:
        try:
            return await async_fetch_live(self._session)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Erreur réseau spacex.com : {err}") from err
        except ValueError as err:
            raise UpdateFailed(f"Réponse spacex.com invalide : {err}") from err
