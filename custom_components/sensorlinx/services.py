"""HA service calls for SensorLinx write operations."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from pysensorlinx import (
    InvalidCredentialsError,
    LoginError,
    Temperature,
    TemperatureDelta,
)

from .const import DOMAIN
from .coordinator import SensorLinxCoordinator

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_SET_HVAC_MODE = "set_hvac_mode_priority"
SERVICE_SET_PERMANENT_DEMAND = "set_permanent_demand"
SERVICE_SET_HOT_TANK_CONFIG = "set_hot_tank_config"
SERVICE_SET_COLD_TANK_CONFIG = "set_cold_tank_config"
SERVICE_SET_DHW_CONFIG = "set_dhw_config"
SERVICE_SET_BACKUP_CONFIG = "set_backup_config"
SERVICE_SET_STAGING_CONFIG = "set_staging_config"
SERVICE_SET_SYSTEM_CONFIG = "set_system_config"

ALL_SERVICES = [
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PERMANENT_DEMAND,
    SERVICE_SET_HOT_TANK_CONFIG,
    SERVICE_SET_COLD_TANK_CONFIG,
    SERVICE_SET_DHW_CONFIG,
    SERVICE_SET_BACKUP_CONFIG,
    SERVICE_SET_STAGING_CONFIG,
    SERVICE_SET_SYSTEM_CONFIG,
]

# Field names
ATTR_DEVICE_ID = "device_id"
ATTR_MODE = "mode"
ATTR_PERMANENT_HD = "permanent_hd"
ATTR_PERMANENT_CD = "permanent_cd"

HVAC_MODES = ["heat", "cool", "auto"]

_TEMP_OR_OFF = vol.Any(vol.Coerce(float), vol.In(["off"]))
_INT_OR_OFF = vol.Any(vol.Coerce(int), vol.In(["off"]))

_SET_HVAC_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_MODE): vol.In(HVAC_MODES),
    }
)

_SET_PERMANENT_DEMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_PERMANENT_HD): cv.boolean,
        vol.Optional(ATTR_PERMANENT_CD): cv.boolean,
    }
)

_SET_HOT_TANK_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional("warm_weather_shutdown"): _TEMP_OR_OFF,
        vol.Optional("outdoor_reset"): _TEMP_OR_OFF,
        vol.Optional("differential"): vol.Coerce(float),
        vol.Optional("min_temp"): vol.Coerce(float),
        vol.Optional("max_temp"): vol.Coerce(float),
    }
)

_SET_COLD_TANK_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional("cold_weather_shutdown"): _TEMP_OR_OFF,
        vol.Optional("outdoor_reset"): _TEMP_OR_OFF,
        vol.Optional("differential"): vol.Coerce(float),
        vol.Optional("min_temp"): vol.Coerce(float),
        vol.Optional("max_temp"): vol.Coerce(float),
    }
)

_SET_DHW_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional("enabled"): cv.boolean,
        vol.Optional("target_temp"): vol.Coerce(float),
        vol.Optional("differential"): vol.Coerce(float),
    }
)

_SET_BACKUP_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional("lag_time"): _INT_OR_OFF,
        vol.Optional("temp"): _TEMP_OR_OFF,
        vol.Optional("differential"): vol.Any(vol.Coerce(float), vol.In(["off"])),
        vol.Optional("only_outdoor_temp"): _TEMP_OR_OFF,
        vol.Optional("only_tank_temp"): _TEMP_OR_OFF,
    }
)

_SET_STAGING_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional("number_of_stages"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=4)
        ),
        vol.Optional("two_stage"): cv.boolean,
        vol.Optional("stage_on_lag_time"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=240)
        ),
        vol.Optional("stage_off_lag_time"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=240)
        ),
        vol.Optional("rotate_cycles"): _INT_OR_OFF,
        vol.Optional("rotate_time"): _INT_OR_OFF,
        vol.Optional("off_staging"): cv.boolean,
    }
)

_SET_SYSTEM_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional("weather_shutdown_lag_time"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=240)
        ),
        vol.Optional("heat_cool_switch_delay"): vol.All(
            vol.Coerce(int), vol.Range(min=30, max=600)
        ),
        vol.Optional("wide_priority_differential"): cv.boolean,
    }
)


def _sync_code_from_device_id(hass: HomeAssistant, ha_device_id: str) -> str:
    """Return the SensorLinx sync_code for a given HA device registry ID.

    Raises ServiceValidationError if the device is not found or is not a
    SensorLinx device.
    """
    dev_reg = dr.async_get(hass)
    device_entry = dev_reg.async_get(ha_device_id)
    if device_entry is None:
        raise ServiceValidationError(
            f"Device '{ha_device_id}' was not found in the Home Assistant device registry."
        )
    for identifier_domain, identifier_value in device_entry.identifiers:
        if identifier_domain == DOMAIN:
            return identifier_value
    raise ServiceValidationError(
        f"Device '{device_entry.name}' is not a SensorLinx device."
    )


def _find_device(
    coordinators: dict[str, SensorLinxCoordinator],
    sync_code: str,
) -> tuple[SensorLinxCoordinator, str, str]:
    """Locate the coordinator, building_id, and device_id for a given sync_code.

    Returns (coordinator, building_id, device_id).
    Raises ServiceValidationError if not found.
    The first match wins when the same sync_code appears in multiple buildings.
    Also logs a warning when the device reports it is not connected to the cloud.
    """
    for coordinator in coordinators.values():
        if not coordinator.data:
            continue
        for building_id, building_data in coordinator.data.items():
            if sync_code in building_data["devices"]:
                device = building_data["devices"][sync_code]["device"]
                if device.get("connected") is False:
                    _LOGGER.warning(
                        "Device '%s' (sync_code=%s) is not connected to the cloud. "
                        "The API call may fail or have no effect.",
                        device.get("name", sync_code),
                        sync_code,
                    )
                # Use the API device id if available, fall back to sync_code.
                device_id = device.get("id") or sync_code
                return coordinator, building_id, device_id

    raise ServiceValidationError(
        f"SensorLinx device with sync_code '{sync_code}' was not found in coordinator data. "
        "The device may be offline or the integration may need to be reloaded."
    )


async def _call_with_reauth(
    coordinator: SensorLinxCoordinator,
    building_id: str,
    device_id: str,
    **kwargs,
) -> None:
    """Call set_device_parameter within the coordinator timeout, retrying once on auth expiry."""
    try:
        async with asyncio.timeout(coordinator.timeout):
            try:
                await coordinator.client.set_device_parameter(
                    building_id=building_id,
                    device_id=device_id,
                    **kwargs,
                )
            except (InvalidCredentialsError, LoginError):
                _LOGGER.debug("Auth error during service call, attempting re-login")
                await coordinator.client.login(
                    username=coordinator.entry_data[CONF_EMAIL],
                    password=coordinator.entry_data[CONF_PASSWORD],
                )
                await coordinator.client.set_device_parameter(
                    building_id=building_id,
                    device_id=device_id,
                    **kwargs,
                )
    except TimeoutError as err:
        raise ServiceValidationError(
            f"SensorLinx API timed out after {coordinator.timeout}s. "
            "Check your network connection and try again."
        ) from err
    except (InvalidCredentialsError, LoginError) as err:
        raise ServiceValidationError(
            f"SensorLinx authentication failed during service call: {err}"
        ) from err
    except RuntimeError as err:
        raise ServiceValidationError(f"SensorLinx API error: {err}") from err


def _resolve_device(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[SensorLinxCoordinator, str, str]:
    """Extract device_id from service call data and resolve to coordinator/building/device."""
    ha_device_id: str = call.data[ATTR_DEVICE_ID]
    sync_code = _sync_code_from_device_id(hass, ha_device_id)
    coordinators: dict[str, SensorLinxCoordinator] = hass.data.get(DOMAIN, {})
    return _find_device(coordinators, sync_code)


def _temp_or_off(value) -> Temperature | str:
    """Convert a service field value to Temperature(°F) or the string 'off'."""
    if isinstance(value, str) and value.lower() == "off":
        return "off"
    return Temperature(float(value), "F")


def _delta_or_off(value) -> TemperatureDelta | str:
    """Convert a service field value to TemperatureDelta(°F) or the string 'off'."""
    if isinstance(value, str) and value.lower() == "off":
        return "off"
    return TemperatureDelta(float(value), "F")


def _int_or_off(value) -> int | str:
    """Convert a service field value to int or the string 'off'."""
    if isinstance(value, str) and value.lower() == "off":
        return "off"
    return int(value)


def _require_at_least_one(call: ServiceCall, *fields: str) -> None:
    """Raise if none of the listed fields are provided."""
    if not any(call.data.get(f) is not None for f in fields):
        raise ServiceValidationError(
            f"At least one of {', '.join(repr(f) for f in fields)} must be provided."
        )


def async_register_services(hass: HomeAssistant) -> None:
    """Register all SensorLinx services. Safe to call multiple times."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_HVAC_MODE):
        return

    async def _handle_set_hvac_mode(call: ServiceCall) -> None:
        coordinator, building_id, device_id = _resolve_device(hass, call)
        mode: str = call.data[ATTR_MODE]
        _LOGGER.debug(
            "Setting HVAC mode '%s' on device %s (building %s)",
            mode,
            device_id,
            building_id,
        )
        await _call_with_reauth(
            coordinator, building_id, device_id, hvac_mode_priority=mode
        )
        await coordinator.async_request_refresh()

    async def _handle_set_permanent_demand(call: ServiceCall) -> None:
        permanent_hd: bool | None = call.data.get(ATTR_PERMANENT_HD)
        permanent_cd: bool | None = call.data.get(ATTR_PERMANENT_CD)
        if permanent_hd is None and permanent_cd is None:
            raise ServiceValidationError(
                "At least one of 'permanent_hd' or 'permanent_cd' must be provided."
            )
        coordinator, building_id, device_id = _resolve_device(hass, call)
        _LOGGER.debug(
            "Setting permanent demand on device %s (building %s): hd=%s cd=%s",
            device_id,
            building_id,
            permanent_hd,
            permanent_cd,
        )
        await _call_with_reauth(
            coordinator,
            building_id,
            device_id,
            permanent_hd=permanent_hd,
            permanent_cd=permanent_cd,
        )
        await coordinator.async_request_refresh()

    async def _handle_set_hot_tank_config(call: ServiceCall) -> None:
        _require_at_least_one(
            call,
            "warm_weather_shutdown",
            "outdoor_reset",
            "differential",
            "min_temp",
            "max_temp",
        )
        coordinator, building_id, device_id = _resolve_device(hass, call)
        kwargs: dict = {}
        if (v := call.data.get("warm_weather_shutdown")) is not None:
            kwargs["warm_weather_shutdown"] = _temp_or_off(v)
        if (v := call.data.get("outdoor_reset")) is not None:
            kwargs["hot_tank_outdoor_reset"] = _temp_or_off(v)
        if (v := call.data.get("differential")) is not None:
            kwargs["hot_tank_differential"] = TemperatureDelta(float(v), "F")
        if (v := call.data.get("min_temp")) is not None:
            kwargs["hot_tank_min_temp"] = Temperature(float(v), "F")
        if (v := call.data.get("max_temp")) is not None:
            kwargs["hot_tank_max_temp"] = Temperature(float(v), "F")
        await _call_with_reauth(coordinator, building_id, device_id, **kwargs)
        await coordinator.async_request_refresh()

    async def _handle_set_cold_tank_config(call: ServiceCall) -> None:
        _require_at_least_one(
            call,
            "cold_weather_shutdown",
            "outdoor_reset",
            "differential",
            "min_temp",
            "max_temp",
        )
        coordinator, building_id, device_id = _resolve_device(hass, call)
        kwargs: dict = {}
        if (v := call.data.get("cold_weather_shutdown")) is not None:
            kwargs["cold_weather_shutdown"] = _temp_or_off(v)
        if (v := call.data.get("outdoor_reset")) is not None:
            kwargs["cold_tank_outdoor_reset"] = _temp_or_off(v)
        if (v := call.data.get("differential")) is not None:
            kwargs["cold_tank_differential"] = TemperatureDelta(float(v), "F")
        if (v := call.data.get("min_temp")) is not None:
            kwargs["cold_tank_min_temp"] = Temperature(float(v), "F")
        if (v := call.data.get("max_temp")) is not None:
            kwargs["cold_tank_max_temp"] = Temperature(float(v), "F")
        await _call_with_reauth(coordinator, building_id, device_id, **kwargs)
        await coordinator.async_request_refresh()

    async def _handle_set_dhw_config(call: ServiceCall) -> None:
        _require_at_least_one(call, "enabled", "target_temp", "differential")
        coordinator, building_id, device_id = _resolve_device(hass, call)
        kwargs: dict = {}
        if (v := call.data.get("enabled")) is not None:
            kwargs["dhw_enabled"] = v
        if (v := call.data.get("target_temp")) is not None:
            kwargs["dhw_target_temp"] = Temperature(float(v), "F")
        if (v := call.data.get("differential")) is not None:
            kwargs["dhw_differential"] = TemperatureDelta(float(v), "F")
        await _call_with_reauth(coordinator, building_id, device_id, **kwargs)
        await coordinator.async_request_refresh()

    async def _handle_set_backup_config(call: ServiceCall) -> None:
        _require_at_least_one(
            call,
            "lag_time",
            "temp",
            "differential",
            "only_outdoor_temp",
            "only_tank_temp",
        )
        coordinator, building_id, device_id = _resolve_device(hass, call)
        kwargs: dict = {}
        if (v := call.data.get("lag_time")) is not None:
            kwargs["backup_lag_time"] = _int_or_off(v)
        if (v := call.data.get("temp")) is not None:
            kwargs["backup_temp"] = _temp_or_off(v)
        if (v := call.data.get("differential")) is not None:
            kwargs["backup_differential"] = _delta_or_off(v)
        if (v := call.data.get("only_outdoor_temp")) is not None:
            kwargs["backup_only_outdoor_temp"] = _temp_or_off(v)
        if (v := call.data.get("only_tank_temp")) is not None:
            kwargs["backup_only_tank_temp"] = _temp_or_off(v)
        await _call_with_reauth(coordinator, building_id, device_id, **kwargs)
        await coordinator.async_request_refresh()

    async def _handle_set_staging_config(call: ServiceCall) -> None:
        _require_at_least_one(
            call,
            "number_of_stages",
            "two_stage",
            "stage_on_lag_time",
            "stage_off_lag_time",
            "rotate_cycles",
            "rotate_time",
            "off_staging",
        )
        coordinator, building_id, device_id = _resolve_device(hass, call)
        kwargs: dict = {}
        if (v := call.data.get("number_of_stages")) is not None:
            kwargs["number_of_stages"] = int(v)
        if (v := call.data.get("two_stage")) is not None:
            kwargs["two_stage_heat_pump"] = v
        if (v := call.data.get("stage_on_lag_time")) is not None:
            kwargs["stage_on_lag_time"] = int(v)
        if (v := call.data.get("stage_off_lag_time")) is not None:
            kwargs["stage_off_lag_time"] = int(v)
        if (v := call.data.get("rotate_cycles")) is not None:
            kwargs["rotate_cycles"] = _int_or_off(v)
        if (v := call.data.get("rotate_time")) is not None:
            kwargs["rotate_time"] = _int_or_off(v)
        if (v := call.data.get("off_staging")) is not None:
            kwargs["off_staging"] = v
        await _call_with_reauth(coordinator, building_id, device_id, **kwargs)
        await coordinator.async_request_refresh()

    async def _handle_set_system_config(call: ServiceCall) -> None:
        _require_at_least_one(
            call,
            "weather_shutdown_lag_time",
            "heat_cool_switch_delay",
            "wide_priority_differential",
        )
        coordinator, building_id, device_id = _resolve_device(hass, call)
        kwargs: dict = {}
        if (v := call.data.get("weather_shutdown_lag_time")) is not None:
            kwargs["weather_shutdown_lag_time"] = int(v)
        if (v := call.data.get("heat_cool_switch_delay")) is not None:
            kwargs["heat_cool_switch_delay"] = int(v)
        if (v := call.data.get("wide_priority_differential")) is not None:
            kwargs["wide_priority_differential"] = v
        await _call_with_reauth(coordinator, building_id, device_id, **kwargs)
        await coordinator.async_request_refresh()

    _SERVICE_MAP = {
        SERVICE_SET_HVAC_MODE: (_handle_set_hvac_mode, _SET_HVAC_MODE_SCHEMA),
        SERVICE_SET_PERMANENT_DEMAND: (
            _handle_set_permanent_demand,
            _SET_PERMANENT_DEMAND_SCHEMA,
        ),
        SERVICE_SET_HOT_TANK_CONFIG: (
            _handle_set_hot_tank_config,
            _SET_HOT_TANK_CONFIG_SCHEMA,
        ),
        SERVICE_SET_COLD_TANK_CONFIG: (
            _handle_set_cold_tank_config,
            _SET_COLD_TANK_CONFIG_SCHEMA,
        ),
        SERVICE_SET_DHW_CONFIG: (_handle_set_dhw_config, _SET_DHW_CONFIG_SCHEMA),
        SERVICE_SET_BACKUP_CONFIG: (
            _handle_set_backup_config,
            _SET_BACKUP_CONFIG_SCHEMA,
        ),
        SERVICE_SET_STAGING_CONFIG: (
            _handle_set_staging_config,
            _SET_STAGING_CONFIG_SCHEMA,
        ),
        SERVICE_SET_SYSTEM_CONFIG: (
            _handle_set_system_config,
            _SET_SYSTEM_CONFIG_SCHEMA,
        ),
    }
    for name, (handler, schema) in _SERVICE_MAP.items():
        hass.services.async_register(DOMAIN, name, handler, schema=schema)
    _LOGGER.debug("Registered SensorLinx services")


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister SensorLinx services when the last entry is removed."""
    if not hass.data.get(DOMAIN):
        for name in ALL_SERVICES:
            hass.services.async_remove(DOMAIN, name)
        _LOGGER.debug("Unregistered SensorLinx services")
