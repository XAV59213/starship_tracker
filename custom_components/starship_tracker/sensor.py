"""Sensors Starship Tracker."""
from __future__ import annotations

from typing import Any

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import StarshipConfigEntry
from .const import DOMAIN, LIVE_URL
from .coordinator import StarshipNewsCoordinator
from .live_coordinator import StarshipLiveCoordinator, launch_datetime


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
            StarshipCountdownSensor(entry.runtime_data.live, entry),
            StarshipMissionStatusSensor(entry.runtime_data.live, entry),
            StarshipLastFlightSensor(entry.runtime_data.live, entry),
            StarshipMissionsSensor(entry.runtime_data.live, entry),
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


def _human(seconds: int) -> str:
    days, rem = divmod(max(seconds, 0), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    return f"{days}d {hours:02d}h {minutes:02d}m"


class StarshipCountdownSensor(CoordinatorEntity[StarshipLiveCoordinator], SensorEntity):
    """Compte à rebours jusqu'au prochain lancement Starship (timestamp)."""

    _attr_has_entity_name = True
    _attr_translation_key = "countdown"
    _attr_icon = "mdi:timer-sand"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: StarshipLiveCoordinator, entry: StarshipConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_starship_countdown"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> datetime | None:
        return launch_datetime(self.coordinator.data.next_mission)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nxt = self.coordinator.data.next_mission or {}
        launch = launch_datetime(nxt)
        attrs: dict[str, Any] = {
            "mission": nxt.get("mission"),
            "launch_site": nxt.get("launch_site"),
            "url": nxt.get("url"),
            "last_check": self.coordinator.data.last_check.isoformat(),
        }
        if launch:
            seconds = int((launch - dt_util.utcnow()).total_seconds())
            attrs.update(
                seconds_remaining=max(seconds, 0),
                countdown=_human(seconds),
                launched=seconds <= 0,
            )
        return attrs


class StarshipMissionStatusSensor(CoordinatorEntity[StarshipLiveCoordinator], SensorEntity):
    """Statut de la prochaine mission Starship (missionStatus du flux SpaceX)."""

    _attr_has_entity_name = True
    _attr_translation_key = "mission_status"
    _attr_icon = "mdi:rocket"

    def __init__(self, coordinator: StarshipLiveCoordinator, entry: StarshipConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_starship_mission_status"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if data.is_live:
            return "live"
        nxt = data.next_mission
        return (nxt or {}).get("mission_status") or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        nxt = data.next_mission or {}
        return {
            "mission": nxt.get("mission"),
            "is_live": data.is_live,
            "launch_date": nxt.get("launch_date"),
            "url": nxt.get("url"),
            "video_url": nxt.get("video_url"),
            "last_check": data.last_check.isoformat(),
        }


class StarshipLastFlightSensor(CoordinatorEntity[StarshipLiveCoordinator], SensorEntity):
    """Dernier vol Starship (page https://www.spacex.com/launches)."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_flight"
    _attr_icon = "mdi:rocket-launch-outline"

    def __init__(self, coordinator: StarshipLiveCoordinator, entry: StarshipConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_starship_last_flight"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        last = self.coordinator.data.last_flight
        return last["mission"] if last else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last = self.coordinator.data.last_flight or {}
        launch = launch_datetime(last)
        return {**last, "launch_time_utc": launch.isoformat() if launch else None}



class StarshipMissionsSensor(CoordinatorEntity[StarshipLiveCoordinator], SensorEntity):
    """Suivi des missions Starship : nombre de vols + listes passés / à venir en attributs."""

    _attr_has_entity_name = True
    _attr_translation_key = "missions"
    _attr_icon = "mdi:rocket-launch"
    _attr_native_unit_of_measurement = "missions"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: StarshipLiveCoordinator, entry: StarshipConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_starship_missions"
        self._attr_device_info = _device_info(entry)

    def _split(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        past: list[dict[str, Any]] = []
        upcoming: list[dict[str, Any]] = []
        for m in self.coordinator.data.missions or []:
            item = {k: m.get(k) for k in ("mission", "launch_date", "launch_time", "launch_site", "mission_status", "url", "video_url", "call_to_action", "is_live")}
            (past if m.get("mission_status") == "final" else upcoming).append(item)
        return past, upcoming

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.missions or [])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        past, upcoming = self._split()
        return {
            "past_count": len(past),
            "upcoming_count": len(upcoming),
            # Les 10 derniers vols (plus récent d'abord) pour limiter la taille de l'état
            "past": list(reversed(past))[:10],
            "upcoming": upcoming,
            "source": "https://www.spacex.com/launches",
        }
