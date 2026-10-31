"""Intégration Starship Tracker."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import StarshipNewsCoordinator
from .live_coordinator import StarshipLiveCoordinator

CARD_FILE = "starship-tracker-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILE}"

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


@dataclass
class StarshipData:
    """Données runtime de l'entrée."""

    news: StarshipNewsCoordinator
    live: StarshipLiveCoordinator


type StarshipConfigEntry = ConfigEntry[StarshipData]


async def _async_register_card(hass: HomeAssistant) -> None:
    """Sert la carte Lovelace livrée avec l'intégration et la charge dans le frontend."""
    if hass.data.get(f"{DOMAIN}_card"):
        return
    hass.data[f"{DOMAIN}_card"] = True
    path = Path(__file__).parent / "www" / CARD_FILE
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(path), True)])
    version = (await async_get_integration(hass, DOMAIN)).version
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")


async def async_setup_entry(hass: HomeAssistant, entry: StarshipConfigEntry) -> bool:
    """Crée les coordinators, premier refresh, puis charge les plateformes."""
    await _async_register_card(hass)
    news = StarshipNewsCoordinator(hass, entry)
    live = StarshipLiveCoordinator(hass)
    await live.async_config_entry_first_refresh()
    # NewsAPI optionnel au démarrage : en cas d'échec (clé, quota, réseau) le live
    # continue et le sensor actualités reste indisponible jusqu'au prochain essai.
    await news.async_refresh()
    entry.runtime_data = StarshipData(news=news, live=live)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StarshipConfigEntry) -> bool:
    """Décharge l'intégration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
