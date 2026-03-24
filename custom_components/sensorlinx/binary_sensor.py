from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SensorLinxCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SensorLinxCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BinarySensorEntity] = []

    for building_id, building_data in coordinator.data.items():
        for sync_code in building_data["devices"]:
            entities.append(
                SensorLinxConnectedSensor(coordinator, entry.entry_id, building_id, sync_code)
            )

            # One binary sensor per demand channel (e.g. heating, cooling)
            raw = building_data["devices"][sync_code]["device"].raw
            for idx, demand in enumerate(raw.get("demands") or []):
                entities.append(
                    SensorLinxDemandActiveSensor(
                        coordinator,
                        entry.entry_id,
                        building_id,
                        sync_code,
                        idx,
                        demand.get("title") or f"Demand {idx + 1}",
                    )
                )

    async_add_entities(entities)


def _device_info(coordinator: SensorLinxCoordinator, building_id: str, sync_code: str) -> DeviceInfo:
    device = coordinator.data[building_id]["devices"][sync_code]["device"]
    building = coordinator.data[building_id]["building"]
    return DeviceInfo(
        identifiers={(DOMAIN, sync_code)},
        name=device.name or sync_code,
        model=device.device_type,
        sw_version=device.firmware_version,
        manufacturer=MANUFACTURER,
        suggested_area=building.name,
    )


class SensorLinxConnectedSensor(CoordinatorEntity[SensorLinxCoordinator], BinarySensorEntity):
    """Whether the device is currently connected to the cloud."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        entry_id: str,
        building_id: str,
        sync_code: str,
    ) -> None:
        super().__init__(coordinator)
        self._building_id = building_id
        self._sync_code = sync_code
        self._attr_unique_id = f"{entry_id}_{sync_code}_connected"
        device = coordinator.data[building_id]["devices"][sync_code]["device"]
        self._attr_name = f"{device.name or sync_code} Connected"
        self._attr_device_info = _device_info(coordinator, building_id, sync_code)

    @property
    def is_on(self) -> bool | None:
        raw = self.coordinator.data[self._building_id]["devices"][self._sync_code]["device"].raw
        connected = raw.get("connected")
        if connected is None:
            return None
        return bool(connected)


class SensorLinxDemandActiveSensor(CoordinatorEntity[SensorLinxCoordinator], BinarySensorEntity):
    """Whether a specific demand channel (e.g. Heat, Cool) is active."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        entry_id: str,
        building_id: str,
        sync_code: str,
        index: int,
        title: str,
    ) -> None:
        super().__init__(coordinator)
        self._building_id = building_id
        self._sync_code = sync_code
        self._index = index
        self._attr_unique_id = f"{entry_id}_{sync_code}_demand_{index}"
        device = coordinator.data[building_id]["devices"][sync_code]["device"]
        self._attr_name = f"{device.name or sync_code} {title}"
        self._attr_device_info = _device_info(coordinator, building_id, sync_code)

    @property
    def is_on(self) -> bool | None:
        demands = (
            self.coordinator.data[self._building_id]["devices"][self._sync_code]["device"]
            .raw.get("demands") or []
        )
        if self._index < len(demands):
            return bool(demands[self._index].get("activated"))
        return None
