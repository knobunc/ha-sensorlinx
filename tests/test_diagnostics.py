"""Tests for SensorLinx diagnostics."""

from homeassistant.const import CONF_PASSWORD

from custom_components.sensorlinx.diagnostics import async_get_config_entry_diagnostics

from .conftest import CONF_DATA


async def test_diagnostics_contains_building_and_device_info(hass, setup_integration):
    """Diagnostics output includes building and device summary data."""
    entry, _ = setup_integration

    result = await async_get_config_entry_diagnostics(hass, entry)

    coordinator_data = result["coordinator"]
    assert coordinator_data["last_update_success"] is True
    assert coordinator_data["building_count"] == 1

    building = coordinator_data["buildings"][0]
    assert building["name"] == "Home"
    assert building["device_count"] == 1

    device = building["devices"][0]
    assert device["sync_code"] == "ABC123"
    assert device["name"] == "ECO Controller"
    assert device["device_type"] == "ECO-0600"
    assert device["firmware"] == "2.0.1"
    assert device["connected"] is True
    assert device["demand_pct"] == 45
    assert device["temperature_channels"] == 4
    assert device["demand_channels"] == 2
    assert device["stages"] == 3
    assert device["pumps"] == 2
    assert device["has_backup"] is True
    assert device["has_reversing_valve"] is True
    assert set(device["wsd_keys"]) == {"wwsd", "cwsd"}


async def test_diagnostics_redacts_password(hass, setup_integration):
    """Diagnostics must not expose the account password."""
    entry, _ = setup_integration

    result = await async_get_config_entry_diagnostics(hass, entry)

    # Walk entire result looking for the plaintext password
    result_str = str(result)
    assert CONF_DATA[CONF_PASSWORD] not in result_str


async def test_diagnostics_includes_config_entry_data(hass, setup_integration):
    """Diagnostics includes (redacted) config entry information."""
    entry, _ = setup_integration

    result = await async_get_config_entry_diagnostics(hass, entry)

    config_entry = result["config_entry"]
    assert config_entry["domain"] == "sensorlinx"
    # Email should be present (not redacted)
    assert CONF_DATA["email"] in str(config_entry)
    # Password must be redacted
    assert CONF_DATA[CONF_PASSWORD] not in str(config_entry)


async def test_diagnostics_last_update_time(hass, setup_integration):
    """Diagnostics captures the last update timestamp."""
    entry, _ = setup_integration

    result = await async_get_config_entry_diagnostics(hass, entry)

    coordinator_data = result["coordinator"]
    # last_update_time is None before first successful update or ISO string after
    assert coordinator_data["last_update_time"] is None or isinstance(
        coordinator_data["last_update_time"], str
    )


async def test_diagnostics_includes_poll_settings(hass, setup_integration):
    """Diagnostics exposes scan_interval and timeout from entry options."""
    from custom_components.sensorlinx.const import DEFAULT_TIMEOUT, SCAN_INTERVAL

    entry, _ = setup_integration

    result = await async_get_config_entry_diagnostics(hass, entry)

    coordinator_data = result["coordinator"]
    # No options set on the test entry — defaults should be present.
    assert coordinator_data["scan_interval"] == SCAN_INTERVAL
    assert coordinator_data["timeout"] == DEFAULT_TIMEOUT


async def test_diagnostics_when_coordinator_has_no_data(
    hass, setup_integration, mock_sensorlinx
):
    """Diagnostics handles coordinator with empty data gracefully."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_buildings.return_value = []
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)

    coordinator_data = result["coordinator"]
    assert coordinator_data["last_update_success"] is True
    assert coordinator_data["building_count"] == 0
    assert coordinator_data["buildings"] == []
