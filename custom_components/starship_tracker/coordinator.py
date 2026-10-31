"""Coordinator de récupération des actualités Starship (NewsAPI)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_API_KEY, DOMAIN, NEWS_API_URL, NEWS_LIMIT, NEWS_QUERY, SCAN_INTERVAL_NEWS

_LOGGER = logging.getLogger(__name__)


class InvalidApiKey(Exception):
    """Clé NewsAPI refusée."""


async def async_fetch_news(session: aiohttp.ClientSession, api_key: str) -> list[dict[str, Any]]:
    """Récupère les dernières actualités Starship depuis NewsAPI."""
    params = {
        "q": NEWS_QUERY,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": str(NEWS_LIMIT),
    }
    headers = {"X-Api-Key": api_key}
    async with asyncio.timeout(20):
        async with session.get(NEWS_API_URL, params=params, headers=headers) as resp:
            if resp.status == 401:
                raise InvalidApiKey
            data = await resp.json(content_type=None)
            if resp.status != 200 or data.get("status") != "ok":
                raise UpdateFailed(f"NewsAPI error {resp.status}: {data.get('message', 'unknown')}")
    return [
        {
            "title": a.get("title"),
            "link": a.get("url"),
            "published": a.get("publishedAt"),
        }
        for a in data.get("articles", [])[:NEWS_LIMIT]
    ]


class StarshipNewsCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator unique pour les actualités."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}_news", update_interval=SCAN_INTERVAL_NEWS)
        self._api_key: str = entry.data[CONF_API_KEY]
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await async_fetch_news(self._session, self._api_key)
        except InvalidApiKey as err:
            raise UpdateFailed("Clé NewsAPI invalide") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Erreur réseau NewsAPI : {err}") from err
        except ValueError as err:
            raise UpdateFailed(f"Réponse NewsAPI invalide : {err}") from err
