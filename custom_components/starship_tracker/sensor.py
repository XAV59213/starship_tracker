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
from .live_coordinator import StarshipLiveCoordinator


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
    coordinator = entry.runtime_data.news
    async_add_entities(
        [
            StarshipLiveSensor(entry),
            StarshipNewsSensor(coordinator, entry),
            StarshipNextMissionSensor(entry.runtime_data.live, entry),
        ]
    )


class StarshipLiveSensor(SensorEntity):
    """Lien vers la page Starship de spacex.com (état live : voir binary_sensor)."""

    _attr_has_entity_name = True
    _attr_translation_key = "vehicle_page"
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
    _attr_translation_key = "news"
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


class StarshipNextMissionSensor(CoordinatorEntity[StarshipLiveCoordinator], SensorEntity):
    """Prochaine mission Starship annoncée sur spacex.com (même flux que le live)."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_mission"
    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator: StarshipLiveCoordinator, entry: StarshipConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_starship_next_mission"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        nxt = self.coordinator.data.next_mission
        return nxt["mission"] if nxt else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nxt = self.coordinator.data.next_mission or {}
        return {**nxt, "last_check": self.coordinator.data.last_check.isoformat()}
