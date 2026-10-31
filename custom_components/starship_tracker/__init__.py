"""Intégration Starship Tracker."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_X_BEARER_TOKEN
from .coordinator import StarshipNewsCoordinator
from .live_coordinator import SpaceXLiveCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


@dataclass
class StarshipData:
    """Données runtime de l'entrée."""

    news: StarshipNewsCoordinator
    live: SpaceXLiveCoordinator | None


type StarshipConfigEntry = ConfigEntry[StarshipData]


def _x_token(entry: ConfigEntry) -> str | None:
    token = entry.options.get(CONF_X_BEARER_TOKEN) or entry.data.get(CONF_X_BEARER_TOKEN)
    return token.strip() if token else None


async def async_setup_entry(hass: HomeAssistant, entry: StarshipConfigEntry) -> bool:
    """Crée les coordinators, premier refresh, puis charge les plateformes."""
    news = StarshipNewsCoordinator(hass, entry)
    await news.async_config_entry_first_refresh()

    live: SpaceXLiveCoordinator | None = None
    if token := _x_token(entry):
        live = SpaceXLiveCoordinator(hass, token)
        await live.async_config_entry_first_refresh()

    entry.runtime_data = StarshipData(news=news, live=live)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: StarshipConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StarshipConfigEntry) -> bool:
    """Décharge l'intégration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
