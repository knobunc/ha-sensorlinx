from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    """Set up SensorLinx binary sensor entities from a config entry."""
    coordinator: SensorLinxCoordinator = hass.data[DOMAIN][entry.entry_id]

    _added_uids: set[str] = set()

    @callback
    def _async_add_binary_sensors() -> None:
        """Add binary sensor entities for devices not yet added in this setup session."""
        ent_reg = er.async_get(hass)
        new_entities: list[BinarySensorEntity] = []

        def _needs(uid: str) -> bool:
            """Return True if this entity should be created now.

            Skip if already added this session AND still present in the registry.
            Re-add if stale cleanup removed it from the registry mid-session.
            """
            if uid not in _added_uids:
                _added_uids.add(uid)
                return True
            return ent_reg.async_get_entity_id("binary_sensor", DOMAIN, uid) is None

        for building_id, building_data in coordinator.data.items():
            for sync_code, device_data in building_data["devices"].items():
                device = device_data["device"]

                # Cloud connectivity
                if _needs(f"{sync_code}_connected"):
                    new_entities.append(
                        SensorLinxConnectedSensor(coordinator, building_id, sync_code)
                    )

                # Demand channels (heat, cool, etc.)
                for idx, demand in enumerate(device.get("demands") or []):
                    if _needs(f"{sync_code}_demand_{idx}"):
                        new_entities.append(
                            SensorLinxDemandActiveSensor(
                                coordinator,
                                building_id,
                                sync_code,
                                idx,
                                demand.get("title") or f"Demand {idx + 1}",
                            )
                        )

                # Heat pump stages
                for idx, stage in enumerate(device.get("stages") or []):
                    if stage.get("enabled") and _needs(f"{sync_code}_stage_{idx}"):
                        new_entities.append(
                            SensorLinxStageBinarySensor(
                                coordinator,
                                building_id,
                                sync_code,
                                idx,
                                stage.get("title") or f"Stage {idx + 1}",
                            )
                        )

                # Backup heating
                backup = device.get("backup")
                if backup and backup.get("enabled") and _needs(f"{sync_code}_backup"):
                    new_entities.append(
                        SensorLinxBackupBinarySensor(
                            coordinator, building_id, sync_code
                        )
                    )

                # Pumps
                for idx, pump in enumerate(device.get("pumps") or []):
                    if _needs(f"{sync_code}_pump_{idx}"):
                        new_entities.append(
                            SensorLinxPumpBinarySensor(
                                coordinator,
                                building_id,
                                sync_code,
                                idx,
                                pump.get("title") or f"Pump {idx + 1}",
                            )
                        )

                # Reversing valve
                if device.get("reversingValve") is not None and _needs(
                    f"{sync_code}_reversing_valve"
                ):
                    new_entities.append(
                        SensorLinxReversingValveBinarySensor(
                            coordinator, building_id, sync_code
                        )
                    )

                # Weather shutdowns (warm / cold)
                for wsd_key, wsd_data in (device.get("wsd") or {}).items():
                    if _needs(f"{sync_code}_wsd_{wsd_key}"):
                        title = wsd_data.get("title") or wsd_key
                        new_entities.append(
                            SensorLinxWeatherShutdownBinarySensor(
                                coordinator, building_id, sync_code, wsd_key, title
                            )
                        )

        if new_entities:
            _LOGGER.debug(
                "Adding %d new binary sensor entity/entities", len(new_entities)
            )
            async_add_entities(new_entities)

    _async_add_binary_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_binary_sensors))


def _safe_bool(value: bool | int | None) -> bool | None:
    """Return bool(value) if value is not None, else None."""
    return bool(value) if value is not None else None


def _get_list_item(lst: list[dict | bool], index: int) -> dict | bool | None:
    """Return lst[index] if in bounds, else None."""
    return lst[index] if index < len(lst) else None


class SensorLinxConnectedSensor(SensorLinxBaseEntity, BinarySensorEntity):
    """Whether the device is currently connected to the cloud."""

    _attr_translation_key = "connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
    ) -> None:
        """Initialise the connectivity sensor."""
        super().__init__(coordinator, building_id, sync_code)
        self._attr_unique_id = f"{sync_code}_connected"

    @property
    def is_on(self) -> bool | None:
        """Return True when the device reports it is connected."""
        device = self._get_device()
        if device is None:
            return None
        connected = device.get("connected")
        return bool(connected) if connected is not None else None


class SensorLinxDemandActiveSensor(SensorLinxBaseEntity, BinarySensorEntity):
    """Whether a demand channel (e.g. Heat, Cool) is active."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
        index: int,
        title: str,
    ) -> None:
        """Initialise the demand-active sensor for a specific channel index."""
        super().__init__(coordinator, building_id, sync_code)
        self._index = index
        self._attr_name = title
        self._attr_unique_id = f"{sync_code}_demand_{index}"

    @property
    def is_on(self) -> bool | None:
        """Return True when this demand channel is activated."""
        device = self._get_device()
        if device is None:
            return None
        demands = device.get("demands") or []
        item = _get_list_item(demands, self._index)
        if not isinstance(item, dict):
            return None
        return _safe_bool(item.get("activated"))


class SensorLinxStageBinarySensor(SensorLinxBaseEntity, BinarySensorEntity):
    """Whether a heat pump stage is running."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
        index: int,
        title: str,
    ) -> None:
        """Initialise the stage binary sensor for a specific stage index."""
        super().__init__(coordinator, building_id, sync_code)
        self._index = index
        self._attr_name = title
        self._attr_unique_id = f"{sync_code}_stage_{index}"

    @property
    def is_on(self) -> bool | None:
        """Return True when this heat pump stage is activated."""
        device = self._get_device()
        if device is None:
            return None
        stages = device.get("stages") or []
        item = _get_list_item(stages, self._index)
        if not isinstance(item, dict):
            return None
        return _safe_bool(item.get("activated"))

    @property
    def extra_state_attributes(self) -> dict:
        """Return run_time as an extra attribute when available."""
        device = self._get_device()
        if device is None:
            return {}
        stages = device.get("stages") or []
        item = _get_list_item(stages, self._index)
        if not isinstance(item, dict):
            return {}
        run_time = item.get("runTime")
        return {"run_time": run_time} if run_time is not None else {}


class SensorLinxBackupBinarySensor(SensorLinxBaseEntity, BinarySensorEntity):
    """Whether the backup heating system is running."""

    _attr_translation_key = "backup_heat"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
    ) -> None:
        """Initialise the backup heat binary sensor."""
        super().__init__(coordinator, building_id, sync_code)
        self._attr_unique_id = f"{sync_code}_backup"

    @property
    def is_on(self) -> bool | None:
        """Return True when backup heating is activated."""
        device = self._get_device()
        if device is None:
            return None
        backup = device.get("backup")
        if not isinstance(backup, dict):
            return None
        return _safe_bool(backup.get("activated"))

    @property
    def extra_state_attributes(self) -> dict:
        """Return run_time as an extra attribute when available."""
        device = self._get_device()
        if device is None:
            return {}
        backup = device.get("backup") or {}
        run_time = backup.get("runTime")
        return {"run_time": run_time} if run_time is not None else {}


class SensorLinxPumpBinarySensor(SensorLinxBaseEntity, BinarySensorEntity):
    """Whether a pump is running."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
        index: int,
        title: str,
    ) -> None:
        """Initialise the pump binary sensor for a specific pump index."""
        super().__init__(coordinator, building_id, sync_code)
        self._index = index
        self._attr_name = title
        self._attr_unique_id = f"{sync_code}_pump_{index}"

    @property
    def is_on(self) -> bool | None:
        """Return True when this pump is activated."""
        device = self._get_device()
        if device is None:
            return None
        pumps = device.get("pumps") or []
        item = _get_list_item(pumps, self._index)
        if not isinstance(item, dict):
            return None
        return _safe_bool(item.get("activated"))


class SensorLinxReversingValveBinarySensor(SensorLinxBaseEntity, BinarySensorEntity):
    """Whether the reversing valve is activated (cooling mode)."""

    _attr_translation_key = "reversing_valve"
    _attr_icon = "mdi:valve"

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
    ) -> None:
        """Initialise the reversing valve binary sensor."""
        super().__init__(coordinator, building_id, sync_code)
        self._attr_unique_id = f"{sync_code}_reversing_valve"

    @property
    def is_on(self) -> bool | None:
        """Return True when the reversing valve is activated."""
        device = self._get_device()
        if device is None:
            return None
        rv = device.get("reversingValve")
        if not isinstance(rv, dict):
            return None
        return _safe_bool(rv.get("activated"))


class SensorLinxWeatherShutdownBinarySensor(SensorLinxBaseEntity, BinarySensorEntity):
    """Whether warm or cold weather shutdown is currently active."""

    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
        wsd_key: str,
        title: str,
    ) -> None:
        """Initialise the weather shutdown sensor for a specific wsd key."""
        super().__init__(coordinator, building_id, sync_code)
        self._wsd_key = wsd_key
        self._attr_name = title
        self._attr_unique_id = f"{sync_code}_wsd_{wsd_key}"

    @property
    def is_on(self) -> bool | None:
        """Return True when this weather shutdown condition is active."""
        device = self._get_device()
        if device is None:
            return None
        wsd = device.get("wsd") or {}
        entry = wsd.get(self._wsd_key)
        if not isinstance(entry, dict):
            return None
        return _safe_bool(entry.get("activated"))
