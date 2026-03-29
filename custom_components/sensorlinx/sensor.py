from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DOMAIN
from .coordinator import SensorLinxCoordinator
from .entity import SensorLinxBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SensorLinx sensor entities from a config entry."""
    coordinator: SensorLinxCoordinator = hass.data[DOMAIN][entry.entry_id]

    @callback
    def _async_add_sensors() -> None:
        """Add sensor entities for any devices not yet in the entity registry."""
        ent_reg = er.async_get(hass)
        new_entities: list[SensorEntity] = []

        for building_id, building_data in coordinator.data.items():
            for sync_code, device_data in building_data["devices"].items():
                device = device_data["device"]

                if device.get("dmd") is not None:
                    uid = f"{sync_code}_demand"
                    if not ent_reg.async_get_entity_id("sensor", DOMAIN, uid):
                        new_entities.append(
                            SensorLinxDemandSensor(coordinator, building_id, sync_code)
                        )

                for idx, temp in enumerate(device.get("temperatures") or []):
                    if temp.get("enabled"):
                        uid = f"{sync_code}_temp_{idx}"
                        if not ent_reg.async_get_entity_id("sensor", DOMAIN, uid):
                            new_entities.append(
                                SensorLinxTemperatureSensor(
                                    coordinator,
                                    building_id,
                                    sync_code,
                                    idx,
                                    temp.get("title") or f"Temp {idx + 1}",
                                )
                            )

        if new_entities:
            _LOGGER.debug("Adding %d new sensor entity/entities", len(new_entities))
            async_add_entities(new_entities)

    _async_add_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_sensors))


class SensorLinxDemandSensor(SensorLinxBaseEntity, SensorEntity):
    """Overall system demand (%) for a device."""

    _attr_translation_key = "demand"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:gauge"

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
    ) -> None:
        """Initialise the demand sensor."""
        super().__init__(coordinator, building_id, sync_code)
        self._attr_unique_id = f"{sync_code}_demand"

    @property
    def native_value(self) -> float | None:
        """Return the current demand percentage."""
        device = self._get_device()
        return device.get("dmd") if device is not None else None


class SensorLinxTemperatureSensor(SensorLinxBaseEntity, SensorEntity):
    """One temperature channel on a device."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    # HBX SensorLinx is a North American HVAC platform; the API always returns °F.
    # HA auto-converts native_value to the user's preferred unit via device_class.
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
        index: int,
        title: str,
    ) -> None:
        """Initialise the temperature sensor for a specific channel index."""
        super().__init__(coordinator, building_id, sync_code)
        self._index = index
        self._attr_name = title
        self._attr_unique_id = f"{sync_code}_temp_{index}"

    def _get_temp(self) -> dict | None:
        """Return the temperature channel dict for this index, or None if missing."""
        device = self._get_device()
        if device is None:
            return None
        temps = device.get("temperatures") or []
        return temps[self._index] if self._index < len(temps) else None

    @property
    def native_value(self) -> float | None:
        """Return the current temperature reading."""
        t = self._get_temp()
        return t.get("current") if t is not None else None

    @property
    def extra_state_attributes(self) -> dict:
        """Return target temperature and activation state as extra attributes.

        target_temperature is converted from the native Fahrenheit API value to
        the same unit HA uses for native_value so both figures are consistent.
        """
        t = self._get_temp()
        if t is None:
            return {}
        attrs: dict = {}
        if t.get("target") is not None:
            target: float = t["target"]
            display_unit = self.hass.config.units.temperature_unit
            if display_unit != UnitOfTemperature.FAHRENHEIT:
                target = TemperatureConverter.convert(
                    target, UnitOfTemperature.FAHRENHEIT, display_unit
                )
            attrs["target_temperature"] = round(target, 1)
        if t.get("activatedState"):
            attrs["state"] = t["activatedState"]
        elif "activated" in t:
            attrs["state"] = "active" if t["activated"] else "idle"
        return attrs
