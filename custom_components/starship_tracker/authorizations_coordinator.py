"""Coordinator du récapitulatif « Autorisations avant décollage »."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .authorizations import (
    CAMERON_URL,
    FAA_STARSHIP_URL,
    FAA_TFR_LIST_URL,
    FAA_TFR_TEXT_URL,
    NGA_WARNINGS_URL,
    build_items,
    overall,
    parse_cameron_closures,
    parse_faa_page_updated,
    parse_nga_warnings,
    parse_tfr_list,
    parse_tfr_webtext,
)
from .const import DOMAIN, SCAN_INTERVAL_AUTHORIZATIONS

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 20
MAX_BYTES = 3 * 1024 * 1024
MAX_NOTAM_TEXTS = 6
# Intervalle minimal par source (le coordinator tourne toutes les 30 min).
_EVERY = {
    "notam": timedelta(minutes=30),
    "navigation": timedelta(hours=1),
    "road_closure": timedelta(hours=1),
    "faa_page": timedelta(hours=6),
}


class LaunchAuthorizationsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Agrège FAA (NOTAM, licence), NGA et Cameron County. Ne lève jamais d'erreur."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_authorizations", update_interval=SCAN_INTERVAL_AUTHORIZATIONS)
        self._session = async_get_clientsession(hass)
        self._checked: dict[str, datetime] = {}
        self._updated: dict[str, str] = {}
        self._notams: list[dict[str, Any]] | None = None
        self._navigation: list[dict[str, Any]] | None = None
        self._closures: list[dict[str, Any]] | None = None
        self._faa_page: str | None = None
        # (notam_id, révision) -> {"start", "end"} : le texte n'est relu que s'il change.
        self._notam_times: dict[tuple[str, str], dict[str, str]] = {}

    async def _get(self, url: str, *, as_json: bool) -> Any:
        async with asyncio.timeout(TIMEOUT):
            async with self._session.get(url, headers={"Accept": "application/json" if as_json else "text/html"}) as resp:
                resp.raise_for_status()
                if (getattr(resp, "content_length", None) or 0) > MAX_BYTES:
                    raise ValueError(f"response too large: {url}")
                raw: bytes = await resp.read()
        if len(raw) > MAX_BYTES:
            raise ValueError(f"response too large: {url}")
        text = raw.decode("utf-8", errors="replace")
        return json.loads(text) if as_json else text

    def _due(self, key: str, now: datetime) -> bool:
        last = self._checked.get(key)
        return last is None or now - last >= _EVERY[key]

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        await asyncio.gather(
            self._refresh_notams(now),
            self._refresh_navigation(now),
            self._refresh_closures(now),
            self._refresh_faa_page(now),
        )
        items = build_items(
            notams=self._notams,
            notams_updated=self._updated.get("notam"),
            closures=self._closures,
            closures_updated=self._updated.get("road_closure"),
            navigation=self._navigation,
            navigation_updated=self._updated.get("navigation"),
            faa_page_updated=self._faa_page,
        )
        return {
            "overall": overall(items),
            "ok_count": sum(1 for i in items if i["status"] == "ok"),
            "total": len(items),
            "items": items,
            "last_check": now.isoformat(),
        }

    async def _refresh_notams(self, now: datetime) -> None:
        if not self._due("notam", now):
            return
        self._checked["notam"] = now
        try:
            notams = parse_tfr_list(await self._get(FAA_TFR_LIST_URL, as_json=True))
        except Exception as err:  # noqa: BLE001 - source complémentaire, jamais bloquante
            _LOGGER.debug("FAA TFR indisponible : %s", err)
            return
        for notam in notams[:MAX_NOTAM_TEXTS]:
            key = (notam["notam_id"], notam.get("revision") or "")
            if key not in self._notam_times:
                try:
                    url = FAA_TFR_TEXT_URL.format(notam_id=notam["notam_id"])
                    self._notam_times[key] = parse_tfr_webtext(await self._get(url, as_json=True))
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Texte NOTAM %s indisponible : %s", notam["notam_id"], err)
                    continue
            notam.update(self._notam_times[key])
        self._notams = notams
        self._updated["notam"] = now.isoformat()

    async def _refresh_navigation(self, now: datetime) -> None:
        if not self._due("navigation", now):
            return
        self._checked["navigation"] = now
        try:
            self._navigation = parse_nga_warnings(await self._get(NGA_WARNINGS_URL, as_json=True))
            self._updated["navigation"] = now.isoformat()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Avis aux navigateurs NGA indisponibles : %s", err)

    async def _refresh_closures(self, now: datetime) -> None:
        if not self._due("road_closure", now):
            return
        self._checked["road_closure"] = now
        try:
            page = await self._get(CAMERON_URL, as_json=False)
            # Dates du comté en heure du Texas : on garde aussi la veille (UTC vs CST).
            today = dt_util.as_local(now).date() - timedelta(days=1)
            self._closures = parse_cameron_closures(page, today)
            self._updated["road_closure"] = now.isoformat()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Fermetures Cameron County indisponibles : %s", err)

    async def _refresh_faa_page(self, now: datetime) -> None:
        if not self._due("faa_page", now):
            return
        self._checked["faa_page"] = now
        try:
            self._faa_page = parse_faa_page_updated(await self._get(FAA_STARSHIP_URL, as_json=False))
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Page FAA Starship indisponible : %s", err)

