"""Switch entities for SensorLinx device controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pysensorlinx import Temperature

from .const import DOMAIN
from .coordinator import SensorLinxCoordinator
from .entity import SensorLinxBaseEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True)
class SentinelSwitchDescriptor:
    """Describes a switch that toggles a sentinel-based temperature parameter."""

    translation_key: str
    device_key: str
    api_param: str
    sentinel: int
    default_on_value: float
    icon: str


@dataclass(frozen=True)
class BoolSwitchDescriptor:
    """Describes a switch backed by a simple boolean device key."""

    translation_key: str
    device_key: str
    api_param: str
    icon: str


_BOOL_SWITCHES: list[BoolSwitchDescriptor] = [
    BoolSwitchDescriptor("permanent_hd_switch", "permHD", "permanent_hd", "mdi:fire"),
    BoolSwitchDescriptor(
        "permanent_cd_switch", "permCD", "permanent_cd", "mdi:snowflake"
    ),
]

_SENTINEL_SWITCHES: list[SentinelSwitchDescriptor] = [
    SentinelSwitchDescriptor(
        translation_key="wwsd_switch",
        device_key="wwsd",
        api_param="warm_weather_shutdown",
        sentinel=32,
        default_on_value=80.0,
        icon="mdi:weather-sunny",
    ),
    SentinelSwitchDescriptor(
        translation_key="hot_outdoor_reset_switch",
        device_key="dot",
        api_param="hot_tank_outdoor_reset",
        sentinel=-41,
        default_on_value=45.0,
        icon="mdi:thermometer-auto",
    ),
    SentinelSwitchDescriptor(
        translation_key="cwsd_switch",
        device_key="cwsd",
        api_param="cold_weather_shutdown",
        sentinel=32,
        default_on_value=75.0,
        icon="mdi:weather-snowy",
    ),
    SentinelSwitchDescriptor(
        translation_key="cold_outdoor_reset_switch",
        device_key="cdot",
        api_param="cold_tank_outdoor_reset",
        sentinel=-41,
        default_on_value=90.0,
        icon="mdi:thermometer-auto",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SensorLinx switch entities from a config entry."""
    coordinator: SensorLinxCoordinator = hass.data[DOMAIN][entry.entry_id]

    _added_uids: set[str] = set()

    @callback
    def _async_add_switches() -> None:
        ent_reg = er.async_get(hass)
        new_entities: list[SwitchEntity] = []

        def _needs(uid: str) -> bool:
            if uid not in _added_uids:
                _added_uids.add(uid)
                return True
            return ent_reg.async_get_entity_id("switch", DOMAIN, uid) is None

        for building_id, building_data in coordinator.data.items():
            for sync_code, device_data in building_data["devices"].items():
                device = device_data["device"]

                if "dhwOn" in device and _needs(f"{sync_code}_dhw_switch"):
                    new_entities.append(
                        SensorLinxDHWSwitch(coordinator, building_id, sync_code)
                    )

                for desc in _BOOL_SWITCHES:
                    uid = f"{sync_code}_{desc.translation_key}"
                    if desc.device_key in device and _needs(uid):
                        new_entities.append(
                            SensorLinxBoolSwitch(
                                coordinator, building_id, sync_code, desc
                            )
                        )

                for desc in _SENTINEL_SWITCHES:
                    uid = f"{sync_code}_{desc.translation_key}"
                    if desc.device_key in device and _needs(uid):
                        new_entities.append(
                            SensorLinxSentinelSwitch(
                                coordinator, building_id, sync_code, desc
                            )
                        )

        if new_entities:
            async_add_entities(new_entities)

    _async_add_switches()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_switches))


def _safe_bool(val: Any) -> bool | None:
    if val is None:
        return None
    return bool(val)


class SensorLinxDHWSwitch(SensorLinxBaseEntity, SwitchEntity):
    """Toggle DHW demand on/off."""

    _attr_translation_key = "dhw_switch"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:water-boiler"

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
    ) -> None:
        super().__init__(coordinator, building_id, sync_code)
        self._attr_unique_id = f"{sync_code}_dhw_switch"

    @property
    def is_on(self) -> bool | None:
        device = self._get_device()
        if device is None:
            return None
        return _safe_bool(device.get("dhwOn"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_device_parameter(
            self._building_id, self._api_device_id, dhw_enabled=True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_device_parameter(
            self._building_id, self._api_device_id, dhw_enabled=False
        )


class SensorLinxBoolSwitch(SensorLinxBaseEntity, SwitchEntity):
    """Toggle a simple boolean device parameter."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
        descriptor: BoolSwitchDescriptor,
    ) -> None:
        super().__init__(coordinator, building_id, sync_code)
        self._desc = descriptor
        self._attr_translation_key = descriptor.translation_key
        self._attr_unique_id = f"{sync_code}_{descriptor.translation_key}"
        self._attr_icon = descriptor.icon

    @property
    def is_on(self) -> bool | None:
        device = self._get_device()
        if device is None:
            return None
        return _safe_bool(device.get(self._desc.device_key))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_device_parameter(
            self._building_id,
            self._api_device_id,
            **{self._desc.api_param: True},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_device_parameter(
            self._building_id,
            self._api_device_id,
            **{self._desc.api_param: False},
        )


class SensorLinxSentinelSwitch(SensorLinxBaseEntity, SwitchEntity):
    """Toggle a sentinel-based temperature parameter on/off."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
        descriptor: SentinelSwitchDescriptor,
    ) -> None:
        super().__init__(coordinator, building_id, sync_code)
        self._desc = descriptor
        self._attr_translation_key = descriptor.translation_key
        self._attr_unique_id = f"{sync_code}_{descriptor.translation_key}"
        self._attr_icon = descriptor.icon

    @property
    def is_on(self) -> bool | None:
        device = self._get_device()
        if device is None:
            return None
        val = device.get(self._desc.device_key)
        if val is None:
            return None
        return val != self._desc.sentinel

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_device_parameter(
            self._building_id,
            self._api_device_id,
            **{self._desc.api_param: "off"},
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_device_parameter(
            self._building_id,
            self._api_device_id,
            **{self._desc.api_param: Temperature(self._desc.default_on_value, "F")},
        )
