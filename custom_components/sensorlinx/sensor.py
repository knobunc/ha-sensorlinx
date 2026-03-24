from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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
    entities: list[SensorEntity] = []

    for building_id, building_data in coordinator.data.items():
        for sync_code, device_data in building_data["devices"].items():
            device = device_data["device"]
            raw = device.raw

            # Demand sensor
            if raw.get("dmd") is not None:
                entities.append(
                    SensorLinxDemandSensor(coordinator, entry.entry_id, building_id, sync_code)
                )

            # Temperature sensors — one entity per enabled channel
            for idx, temp in enumerate(raw.get("temperatures") or []):
                if temp.get("enabled"):
                    entities.append(
                        SensorLinxTemperatureSensor(
                            coordinator,
                            entry.entry_id,
                            building_id,
                            sync_code,
                            idx,
                            temp.get("title") or f"Temp {idx + 1}",
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


class SensorLinxDemandSensor(CoordinatorEntity[SensorLinxCoordinator], SensorEntity):
    """Overall system demand (%) for a device."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"

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
        self._attr_unique_id = f"{entry_id}_{sync_code}_demand"
        device = coordinator.data[building_id]["devices"][sync_code]["device"]
        self._attr_name = f"{device.name or sync_code} Demand"
        self._attr_device_info = _device_info(coordinator, building_id, sync_code)

    @property
    def native_value(self) -> float | None:
        raw = self.coordinator.data[self._building_id]["devices"][self._sync_code]["device"].raw
        return raw.get("dmd")


class SensorLinxTemperatureSensor(CoordinatorEntity[SensorLinxCoordinator], SensorEntity):
    """One temperature channel on a device."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

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
        self._attr_unique_id = f"{entry_id}_{sync_code}_temp_{index}"
        device = coordinator.data[building_id]["devices"][sync_code]["device"]
        self._attr_name = f"{device.name or sync_code} {title}"
        self._attr_device_info = _device_info(coordinator, building_id, sync_code)

    @property
    def native_value(self) -> float | None:
        temps = (
            self.coordinator.data[self._building_id]["devices"][self._sync_code]["device"]
            .raw.get("temperatures") or []
        )
        if self._index < len(temps):
            return temps[self._index].get("current")
        return None

    @property
    def extra_state_attributes(self) -> dict:
        temps = (
            self.coordinator.data[self._building_id]["devices"][self._sync_code]["device"]
            .raw.get("temperatures") or []
        )
        if self._index >= len(temps):
            return {}
        t = temps[self._index]
        attrs: dict = {}
        if t.get("target") is not None:
            attrs["target_temperature"] = t["target"]
        if t.get("activatedState"):
            attrs["state"] = t["activatedState"]
        elif "activated" in t:
            attrs["state"] = "active" if t["activated"] else "idle"
        return attrs
