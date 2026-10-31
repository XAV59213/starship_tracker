"""Intégration Starship Tracker."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import StarshipNewsCoordinator
from .live_coordinator import StarshipLiveCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


@dataclass
class StarshipData:
    """Données runtime de l'entrée."""

    news: StarshipNewsCoordinator
    live: StarshipLiveCoordinator


type StarshipConfigEntry = ConfigEntry[StarshipData]


async def async_setup_entry(hass: HomeAssistant, entry: StarshipConfigEntry) -> bool:
    """Crée les coordinators, premier refresh, puis charge les plateformes."""
    news = StarshipNewsCoordinator(hass, entry)
    live = StarshipLiveCoordinator(hass)
    await news.async_config_entry_first_refresh()
    await live.async_config_entry_first_refresh()
    entry.runtime_data = StarshipData(news=news, live=live)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StarshipConfigEntry) -> bool:
    """Décharge l'intégration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
