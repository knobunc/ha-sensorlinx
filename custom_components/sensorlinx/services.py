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
from pysensorlinx import InvalidCredentialsError, LoginError

from .const import DOMAIN
from .coordinator import SensorLinxCoordinator

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_SET_HVAC_MODE = "set_hvac_mode_priority"
SERVICE_SET_PERMANENT_DEMAND = "set_permanent_demand"

# Field names
ATTR_DEVICE_ID = "device_id"
ATTR_MODE = "mode"
ATTR_PERMANENT_HD = "permanent_hd"
ATTR_PERMANENT_CD = "permanent_cd"

HVAC_MODES = ["heat", "cool", "auto"]

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


def async_register_services(hass: HomeAssistant) -> None:
    """Register all SensorLinx services. Safe to call multiple times."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_HVAC_MODE):
        return

    async def _handle_set_hvac_mode(call: ServiceCall) -> None:
        """Set the HVAC mode priority for a device."""
        ha_device_id: str = call.data[ATTR_DEVICE_ID]
        mode: str = call.data[ATTR_MODE]

        sync_code = _sync_code_from_device_id(hass, ha_device_id)
        coordinators: dict[str, SensorLinxCoordinator] = hass.data.get(DOMAIN, {})
        coordinator, building_id, device_id = _find_device(coordinators, sync_code)

        _LOGGER.debug(
            "Setting HVAC mode '%s' on device %s (building %s)",
            mode,
            device_id,
            building_id,
        )
        await _call_with_reauth(
            coordinator,
            building_id,
            device_id,
            hvac_mode_priority=mode,
        )
        await coordinator.async_request_refresh()

    async def _handle_set_permanent_demand(call: ServiceCall) -> None:
        """Set permanent heating and/or cooling demand for a device."""
        ha_device_id: str = call.data[ATTR_DEVICE_ID]
        permanent_hd: bool | None = call.data.get(ATTR_PERMANENT_HD)
        permanent_cd: bool | None = call.data.get(ATTR_PERMANENT_CD)

        if permanent_hd is None and permanent_cd is None:
            raise ServiceValidationError(
                "At least one of 'permanent_hd' or 'permanent_cd' must be provided."
            )

        sync_code = _sync_code_from_device_id(hass, ha_device_id)
        coordinators: dict[str, SensorLinxCoordinator] = hass.data.get(DOMAIN, {})
        coordinator, building_id, device_id = _find_device(coordinators, sync_code)

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

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        _handle_set_hvac_mode,
        schema=_SET_HVAC_MODE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PERMANENT_DEMAND,
        _handle_set_permanent_demand,
        schema=_SET_PERMANENT_DEMAND_SCHEMA,
    )
    _LOGGER.debug("Registered SensorLinx services")


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister SensorLinx services when the last entry is removed."""
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SET_HVAC_MODE)
        hass.services.async_remove(DOMAIN, SERVICE_SET_PERMANENT_DEMAND)
        _LOGGER.debug("Unregistered SensorLinx services")
