"""Binary sensor : Starship est-il en live sur spacex.com ?"""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StarshipConfigEntry
from .const import LIVE_URL
from .live_coordinator import StarshipLiveCoordinator
from .sensor import _device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StarshipConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Ajoute le binary_sensor live."""
    async_add_entities([StarshipLiveBinarySensor(entry.runtime_data.live, entry)])


class StarshipLiveBinarySensor(CoordinatorEntity[StarshipLiveCoordinator], BinarySensorEntity):
    """on = une mission Starship est en live sur spacex.com."""

    _attr_has_entity_name = True
    _attr_translation_key = "starship_live"

    def __init__(self, coordinator: StarshipLiveCoordinator, entry: StarshipConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_starship_live_status"
        self._attr_device_info = _device_info(entry)

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.is_live

    @property
    def icon(self) -> str:
        return "mdi:rocket-launch" if self.is_on else "mdi:rocket"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self.coordinator.data
        return {
            "url": d.url,
            "vehicle_url": LIVE_URL,
            "mission": d.mission,
            "mission_status": d.mission_status,
            "launch_date": d.launch_date,
            "launch_site": d.launch_site,
            "last_check": d.last_check.isoformat(),
        }
