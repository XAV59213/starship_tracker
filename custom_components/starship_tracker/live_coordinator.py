"""Coordinator de détection du live SpaceX sur X."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LIVE_WINDOW, SCAN_INTERVAL_LIVE, X_PROFILE_URL, X_SEARCH_QUERY, X_SEARCH_URL

_LOGGER = logging.getLogger(__name__)


class InvalidXToken(Exception):
    """Bearer token X refusé."""


@dataclass
class LiveStatus:
    """Résultat d'une vérification."""

    is_live: bool
    url: str
    title: str | None
    post_url: str | None
    started_at: datetime | None
    last_check: datetime


async def async_fetch_live(session: aiohttp.ClientSession, token: str) -> LiveStatus:
    """Cherche le dernier post SpaceX contenant un lien x.com/i/broadcasts."""
    params = {
        "query": X_SEARCH_QUERY,
        "max_results": "10",
        "tweet.fields": "created_at,entities",
    }
    headers = {"Authorization": f"Bearer {token}"}
    async with asyncio.timeout(20):
        async with session.get(X_SEARCH_URL, params=params, headers=headers) as resp:
            if resp.status in (401, 403):
                raise InvalidXToken
            if resp.status == 429:
                raise UpdateFailed("Quota API X atteint (429)")
            if resp.status != 200:
                raise UpdateFailed(f"Erreur API X {resp.status}")
            data = await resp.json(content_type=None)

    now = dt_util.utcnow()
    for post in data.get("data", []):
        for url in post.get("entities", {}).get("urls", []):
            link = url.get("unwound_url") or url.get("expanded_url") or ""
            if "x.com/i/broadcasts/" not in link:
                continue
            created = dt_util.parse_datetime(post.get("created_at", ""))
            is_live = created is not None and now - created <= LIVE_WINDOW
            return LiveStatus(
                is_live=is_live,
                url=link,
                title=url.get("description") or post.get("text"),
                post_url=f"{X_PROFILE_URL}/status/{post['id']}",
                started_at=created,
                last_check=now,
            )
    return LiveStatus(False, X_PROFILE_URL, None, None, None, now)


class SpaceXLiveCoordinator(DataUpdateCoordinator[LiveStatus]):
    """Vérifie toutes les 10 min si SpaceX diffuse sur X."""

    def __init__(self, hass: HomeAssistant, token: str) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_live", update_interval=SCAN_INTERVAL_LIVE)
        self._token = token
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> LiveStatus:
        try:
            return await async_fetch_live(self._session, self._token)
        except InvalidXToken as err:
            raise UpdateFailed("Bearer token X invalide") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Erreur réseau API X : {err}") from err
        except ValueError as err:
            raise UpdateFailed(f"Réponse API X invalide : {err}") from err
