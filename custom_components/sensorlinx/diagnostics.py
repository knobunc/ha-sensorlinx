"""Diagnostics support for SensorLinx."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    SCAN_INTERVAL,
)
from .coordinator import SensorLinxCoordinator

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SensorLinxCoordinator = hass.data[DOMAIN][entry.entry_id]

    # last_update_success_time was added in a later HA version; fall back gracefully.
    last_update_time = getattr(coordinator, "last_update_success_time", None)
    buildings: list[dict[str, Any]] = []
    for building_id, building_data in (coordinator.data or {}).items():
        devices: list[dict[str, Any]] = []
        for sync_code, device_data in building_data["devices"].items():
            device = device_data["device"]
            devices.append(
                {
                    "sync_code": sync_code,
                    "name": device.get("name"),
                    "device_type": device.get("deviceType"),
                    "firmware": device.get("firmVer"),
                    "connected": device.get("connected"),
                    "demand_pct": device.get("dmd"),
                    "temperature_channels": len(device.get("temperatures") or []),
                    "demand_channels": len(device.get("demands") or []),
                    "stages": len(device.get("stages") or []),
                    "pumps": len(device.get("pumps") or []),
                    "has_backup": device.get("backup") is not None,
                    "has_reversing_valve": device.get("reversingValve") is not None,
                    "dhw_enabled": device.get("dhwOn"),
                    "has_cold_tank": "cwsd" in device,
                    "wsd_keys": list((device.get("wsd") or {}).keys()),
                }
            )
        building = building_data["building"]
        buildings.append(
            {
                "id": building_id,
                "name": building.get("name"),
                "has_weather": building.get("weather") is not None,
                "device_count": len(devices),
                "devices": devices,
            }
        )

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_update_time": last_update_time.isoformat()
            if last_update_time
            else None,
            "last_exception": (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
            "scan_interval": entry.options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
            "timeout": entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            "building_count": len(buildings),
            "buildings": buildings,
        },
    }
