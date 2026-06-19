"""Number entities for SensorLinx device controls."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pysensorlinx import Temperature, TemperatureDelta

from .const import DOMAIN
from .coordinator import SensorLinxCoordinator
from .entity import SensorLinxBaseEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True)
class NumberDescriptor:
    """Describes a number entity for a device configuration parameter."""

    translation_key: str
    device_key: str
    api_param: str
    min_value: float
    max_value: float
    step: float
    is_delta: bool
    sentinel: int | None
    icon: str


_NUMBER_ENTITIES: list[NumberDescriptor] = [
    # DHW
    NumberDescriptor(
        "dhw_target_temp_control", "dhwT", "dhw_target_temp",
        33, 180, 1, False, None, "mdi:water-thermometer",
    ),
    NumberDescriptor(
        "dhw_differential_control", "auxDif", "dhw_differential",
        2, 100, 1, True, None, "mdi:thermometer-plus",
    ),
    # Hot tank
    NumberDescriptor(
        "min_tank_temp_control", "mbt", "hot_tank_min_temp",
        2, 180, 1, False, None, "mdi:thermometer-low",
    ),
    NumberDescriptor(
        "max_tank_temp_control", "dbt", "hot_tank_max_temp",
        2, 180, 1, False, None, "mdi:thermometer-high",
    ),
    NumberDescriptor(
        "heat_differential_control", "htDif", "hot_tank_differential",
        2, 100, 1, True, None, "mdi:thermometer-plus",
    ),
    NumberDescriptor(
        "wwsd_temp_control", "wwsd", "warm_weather_shutdown",
        34, 180, 1, False, 32, "mdi:weather-sunny",
    ),
    NumberDescriptor(
        "outdoor_reset_control", "dot", "hot_tank_outdoor_reset",
        -40, 127, 1, False, -41, "mdi:thermometer-auto",
    ),
    # Cold tank
    NumberDescriptor(
        "cold_min_tank_temp_control", "mst", "cold_tank_min_temp",
        2, 180, 1, False, None, "mdi:thermometer-low",
    ),
    NumberDescriptor(
        "cold_max_tank_temp_control", "dst", "cold_tank_max_temp",
        2, 180, 1, False, None, "mdi:thermometer-high",
    ),
    NumberDescriptor(
        "cold_differential_control", "clDif", "cold_tank_differential",
        2, 100, 1, True, None, "mdi:thermometer-plus",
    ),
    NumberDescriptor(
        "cwsd_temp_control", "cwsd", "cold_weather_shutdown",
        33, 119, 1, False, 32, "mdi:weather-snowy",
    ),
    NumberDescriptor(
        "cold_outdoor_reset_control", "cdot", "cold_tank_outdoor_reset",
        0, 119, 1, False, -41, "mdi:thermometer-auto",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SensorLinx number entities from a config entry."""
    coordinator: SensorLinxCoordinator = hass.data[DOMAIN][entry.entry_id]

    _added_uids: set[str] = set()

    @callback
    def _async_add_numbers() -> None:
        ent_reg = er.async_get(hass)
        new_entities: list[NumberEntity] = []

        def _needs(uid: str) -> bool:
            if uid not in _added_uids:
                _added_uids.add(uid)
                return True
            return ent_reg.async_get_entity_id("number", DOMAIN, uid) is None

        for building_id, building_data in coordinator.data.items():
            for sync_code, device_data in building_data["devices"].items():
                device = device_data["device"]

                for desc in _NUMBER_ENTITIES:
                    uid = f"{sync_code}_{desc.translation_key}"
                    if desc.device_key in device and _needs(uid):
                        new_entities.append(
                            SensorLinxNumberEntity(
                                coordinator, building_id, sync_code, desc
                            )
                        )

        if new_entities:
            async_add_entities(new_entities)

    _async_add_numbers()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_numbers))


class SensorLinxNumberEntity(SensorLinxBaseEntity, NumberEntity):
    """A writable numeric configuration parameter."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
        descriptor: NumberDescriptor,
    ) -> None:
        super().__init__(coordinator, building_id, sync_code)
        self._desc = descriptor
        self._attr_translation_key = descriptor.translation_key
        self._attr_unique_id = f"{sync_code}_{descriptor.translation_key}"
        self._attr_icon = descriptor.icon
        self._attr_native_min_value = descriptor.min_value
        self._attr_native_max_value = descriptor.max_value
        self._attr_native_step = descriptor.step
        if not descriptor.is_delta:
            self._attr_device_class = NumberDeviceClass.TEMPERATURE

    @property
    def native_value(self) -> float | None:
        device = self._get_device()
        if device is None:
            return None
        val = device.get(self._desc.device_key)
        if val is None:
            return None
        if self._desc.sentinel is not None and val == self._desc.sentinel:
            return None
        return float(val)

    async def async_set_native_value(self, value: float) -> None:
        if self._desc.is_delta:
            api_value = TemperatureDelta(value, "F")
        else:
            api_value = Temperature(value, "F")
        await self.coordinator.async_set_device_parameter(
            self._building_id,
            self._api_device_id,
            **{self._desc.api_param: api_value},
        )
