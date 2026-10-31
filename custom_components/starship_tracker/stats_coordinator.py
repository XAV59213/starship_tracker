"""Coordinator des compteurs SpaceX (page https://www.spacex.com/launches)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_STATS, SPACEX_STATS_URL

_LOGGER = logging.getLogger(__name__)


class SpaceXStatsCoordinator(DataUpdateCoordinator[dict[str, int | None]]):
    """Lit totalLaunches / totalLandings / totalReflights du site SpaceX."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_stats", update_interval=SCAN_INTERVAL_STATS)

    async def _async_update_data(self) -> dict[str, int | None]:
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(20):
                resp = await session.get(SPACEX_STATS_URL)
                resp.raise_for_status()
                raw: dict[str, Any] = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise UpdateFailed(f"SpaceX stats: {err}") from err

        def _int(key: str) -> int | None:
            try:
                return int(raw[key])
            except (KeyError, TypeError, ValueError):
                return None

        return {
            "total_launches": _int("totalLaunches"),
            "total_landings": _int("totalLandings"),
            "total_reflights": _int("totalReflights"),
        }
