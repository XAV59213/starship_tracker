"""Binary sensor : SpaceX est-il en live sur X ?"""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StarshipConfigEntry
from .live_coordinator import SpaceXLiveCoordinator
from .sensor import _device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StarshipConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Ajoute le binary_sensor seulement si un bearer token X est configuré."""
    if (live := entry.runtime_data.live) is not None:
        async_add_entities([SpaceXLiveBinarySensor(live, entry)])


class SpaceXLiveBinarySensor(CoordinatorEntity[SpaceXLiveCoordinator], BinarySensorEntity):
    """on = SpaceX diffuse un live sur X."""

    _attr_has_entity_name = True
    _attr_translation_key = "spacex_live"

    def __init__(self, coordinator: SpaceXLiveCoordinator, entry: StarshipConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_spacex_live_x"
        self._attr_device_info = _device_info(entry)

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.is_live

    @property
    def icon(self) -> str:
        return "mdi:access-point" if self.is_on else "mdi:access-point-off"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        return {
            "url": d.url,
            "title": d.title,
            "post_url": d.post_url,
            "started_at": d.started_at.isoformat() if d.started_at else None,
            "last_check": d.last_check.isoformat(),
        }
