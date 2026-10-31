"""Sensors Starship Tracker."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import StarshipConfigEntry
from .const import DOMAIN, LIVE_URL
from .coordinator import StarshipNewsCoordinator


def _device_info(entry: StarshipConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Starship Tracker",
        manufacturer="XAV59213",
        entry_type=DeviceEntryType.SERVICE,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StarshipConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Ajoute les sensors live et news."""
    coordinator = entry.runtime_data
    async_add_entities([StarshipLiveSensor(entry), StarshipNewsSensor(coordinator, entry)])


class StarshipLiveSensor(SensorEntity):
    """Lien vers le flux en direct SpaceX (pas de détection de diffusion)."""

    _attr_has_entity_name = True
    _attr_name = "Live stream"
    _attr_icon = "mdi:rocket-launch"
    _attr_should_poll = False

    def __init__(self, entry: StarshipConfigEntry) -> None:
        self._attr_unique_id = f"{entry.entry_id}_starship_live"
        self._attr_device_info = _device_info(entry)
        self._attr_native_value = "available"
        self._attr_extra_state_attributes = {"url": LIVE_URL}


class StarshipNewsSensor(CoordinatorEntity[StarshipNewsCoordinator], SensorEntity):
    """Nombre d'articles récents + les 5 derniers en attributs."""

    _attr_has_entity_name = True
    _attr_name = "News"
    _attr_icon = "mdi:newspaper"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "articles"

    def __init__(self, coordinator: StarshipNewsCoordinator, entry: StarshipConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_starship_news"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"news": self.coordinator.data or []}
