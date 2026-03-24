from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from sensorlinx import SensorLinxClient

from .const import DOMAIN
from .coordinator import SensorLinxCoordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    token = entry.data.get("token")
    client = SensorLinxClient(token=token) if token else SensorLinxClient()

    if not token:
        await hass.async_add_executor_job(
            client.login,
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
        )

    coordinator = SensorLinxCoordinator(hass, client, entry.data)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: SensorLinxCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await hass.async_add_executor_job(coordinator.client.close)
    return unload_ok
