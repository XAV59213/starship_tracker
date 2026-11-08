"""Bouton de rafraîchissement Starship Tracker."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import StarshipConfigEntry
from .const import DOMAIN
from .sensor import _device_info


PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StarshipConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Ajoute le bouton de rafraîchissement."""
    async_add_entities([StarshipRefreshButton(entry)])


class StarshipRefreshButton(ButtonEntity):
    """Force la mise à jour du live SpaceX et des actualités."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: StarshipConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = _device_info(entry)

    async def async_press(self) -> None:
        data = self._entry.runtime_data
        await data.live.async_refresh()
        await data.news.async_refresh()
        await data.stats.async_refresh()
        if not data.live.last_update_success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_failed",
            )
