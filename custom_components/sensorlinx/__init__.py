from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from pysensorlinx import InvalidCredentialsError, LoginError, Sensorlinx

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SCAN_INTERVAL,
)
from .coordinator import SensorLinxCoordinator
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SensorLinx from a config entry."""
    _LOGGER.debug("Setting up SensorLinx entry %s", entry.entry_id)
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    timeout = entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    client = Sensorlinx()
    try:
        async with asyncio.timeout(timeout):
            await client.login(
                username=entry.data[CONF_EMAIL],
                password=entry.data[CONF_PASSWORD],
            )
    except TimeoutError as err:
        raise ConfigEntryNotReady(
            f"Timed out connecting to SensorLinx after {timeout}s"
        ) from err
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed(f"Invalid credentials: {err}") from err
    except (LoginError, RuntimeError) as err:
        raise ConfigEntryNotReady(f"Could not connect to SensorLinx: {err}") from err
    coordinator = SensorLinxCoordinator(
        hass, client, entry.data, scan_interval, timeout
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_register_services(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(_register_stale_cleanup(hass, entry, coordinator))
    _LOGGER.debug(
        "SensorLinx entry %s set up with %d building(s)",
        entry.entry_id,
        len(coordinator.data),
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    _LOGGER.debug("SensorLinx options changed, reloading entry %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SensorLinx config entry."""
    _LOGGER.debug("Unloading SensorLinx entry %s", entry.entry_id)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: SensorLinxCoordinator | None = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )
        if coordinator is not None:
            await coordinator.client.close()
        async_unregister_services(hass)
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Block manual removal of devices that are still present in the API.

    Returns False (removal blocked) when the device is currently in coordinator
    data, because live discovery would re-add it on the next poll anyway.
    Returns True when the device is no longer known to the coordinator (e.g. it
    was already cleaned up by stale cleanup), allowing the user to tidy the
    registry manually.
    """
    coordinator: SensorLinxCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coordinator is None or not coordinator.data:
        return True

    known_sync_codes = {
        sync_code
        for building_data in coordinator.data.values()
        for sync_code in building_data["devices"]
    }
    for identifier_domain, identifier_value in device_entry.identifiers:
        if identifier_domain == DOMAIN and identifier_value in known_sync_codes:
            return False
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry versions to the current schema."""
    _LOGGER.debug("Migrating SensorLinx entry from version %s", entry.version)
    # No migrations needed for version 1 — placeholder for future version bumps.
    return True


def _register_stale_cleanup(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: SensorLinxCoordinator,
) -> Callable[[], None]:
    """Register a coordinator listener that removes devices/entities no longer in the API.

    Returns the unsubscribe callable so it can be passed to entry.async_on_unload.
    """

    @callback
    def _cleanup() -> None:
        if not coordinator.last_update_success or not coordinator.data:
            return

        known_sync_codes = {
            sync_code
            for building_data in coordinator.data.values()
            for sync_code in building_data["devices"]
        }

        dev_reg = dr.async_get(hass)
        ent_reg = er.async_get(hass)

        for device_entry in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            stale = {
                identifier_value
                for (identifier_domain, identifier_value) in device_entry.identifiers
                if identifier_domain == DOMAIN
                and identifier_value not in known_sync_codes
            }
            if stale:
                _LOGGER.debug(
                    "Removing stale device '%s' (sync_codes: %s)",
                    device_entry.name,
                    stale,
                )
                for entity_entry in er.async_entries_for_device(
                    ent_reg, device_entry.id, include_disabled_entities=True
                ):
                    ent_reg.async_remove(entity_entry.entity_id)
                dev_reg.async_remove_device(device_entry.id)

    return coordinator.async_add_listener(_cleanup)
