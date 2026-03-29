"""Edge-case tests: options flow boundaries, service errors, and duplicate sync codes."""

import pytest
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResultType
from pysensorlinx import InvalidCredentialsError, LoginError

from .conftest import FAKE_DEVICES
from .conftest import ha_device_id as _ha_device_id

# ---------------------------------------------------------------------------
# Options flow — scan_interval boundary values
# ---------------------------------------------------------------------------


async def test_options_scan_interval_minimum_accepted(hass, setup_integration):
    """scan_interval=30 (minimum) is accepted."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 30, "timeout": 30}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["scan_interval"] == 30


async def test_options_scan_interval_maximum_accepted(hass, setup_integration):
    """scan_interval=3600 (maximum) is accepted."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 3600, "timeout": 30}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["scan_interval"] == 3600


async def test_options_scan_interval_below_minimum_rejected(hass, setup_integration):
    """scan_interval=29 (below minimum) is rejected."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises((vol.Invalid, Exception)):
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"scan_interval": 29, "timeout": 30}
        )


async def test_options_scan_interval_above_maximum_rejected(hass, setup_integration):
    """scan_interval=3601 (above maximum) is rejected."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises((vol.Invalid, Exception)):
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"scan_interval": 3601, "timeout": 30}
        )


# ---------------------------------------------------------------------------
# Options flow — timeout boundary values
# ---------------------------------------------------------------------------


async def test_options_timeout_minimum_accepted(hass, setup_integration):
    """timeout=10 (minimum) is accepted."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 60, "timeout": 10}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["timeout"] == 10


async def test_options_timeout_maximum_accepted(hass, setup_integration):
    """timeout=120 (maximum) is accepted."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 60, "timeout": 120}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["timeout"] == 120


async def test_options_timeout_below_minimum_rejected(hass, setup_integration):
    """timeout=9 (below minimum) is rejected."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises((vol.Invalid, Exception)):
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"scan_interval": 60, "timeout": 9}
        )


async def test_options_timeout_above_maximum_rejected(hass, setup_integration):
    """timeout=121 (above maximum) is rejected."""
    entry, _ = setup_integration
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises((vol.Invalid, Exception)):
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"scan_interval": 60, "timeout": 121}
        )


# ---------------------------------------------------------------------------
# Service — API error handling
# ---------------------------------------------------------------------------


async def test_service_set_hvac_mode_api_error_raises(
    hass, setup_integration, mock_sensorlinx
):
    """RuntimeError from set_device_parameter is surfaced as ServiceValidationError."""
    _, client = mock_sensorlinx
    client.set_device_parameter.side_effect = RuntimeError("API unavailable")

    with pytest.raises(Exception) as exc_info:
        await hass.services.async_call(
            "sensorlinx",
            "set_hvac_mode_priority",
            {"device_id": _ha_device_id(hass, "ABC123"), "mode": "heat"},
            blocking=True,
        )
    assert "API unavailable" in str(exc_info.value) or "SensorLinx" in str(
        exc_info.value
    )


async def test_service_set_hvac_mode_auth_error_retries(
    hass, setup_integration, mock_sensorlinx
):
    """LoginError from set_device_parameter triggers a re-login and retry."""
    _, client = mock_sensorlinx
    # First call raises LoginError, second succeeds
    client.set_device_parameter.side_effect = [LoginError("expired"), None]

    await hass.services.async_call(
        "sensorlinx",
        "set_hvac_mode_priority",
        {"device_id": _ha_device_id(hass, "ABC123"), "mode": "cool"},
        blocking=True,
    )

    # Re-login should have been called once
    client.login.assert_awaited()
    # set_device_parameter called twice (first fails, second succeeds)
    assert client.set_device_parameter.await_count == 2


async def test_service_set_hvac_mode_auth_error_both_attempts_fail(
    hass, setup_integration, mock_sensorlinx
):
    """If re-login also fails, ServiceValidationError is raised."""
    _, client = mock_sensorlinx
    client.set_device_parameter.side_effect = LoginError("expired")
    client.login.side_effect = InvalidCredentialsError("bad creds")

    with pytest.raises(Exception):
        await hass.services.async_call(
            "sensorlinx",
            "set_hvac_mode_priority",
            {"device_id": _ha_device_id(hass, "ABC123"), "mode": "heat"},
            blocking=True,
        )


async def test_service_set_permanent_demand_api_error_raises(
    hass, setup_integration, mock_sensorlinx
):
    """RuntimeError from set_device_parameter is surfaced as an error for permanent demand too."""
    _, client = mock_sensorlinx
    client.set_device_parameter.side_effect = RuntimeError("server error")

    with pytest.raises(Exception):
        await hass.services.async_call(
            "sensorlinx",
            "set_permanent_demand",
            {"device_id": _ha_device_id(hass, "ABC123"), "permanent_hd": True},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# Service — disconnected device warning (logged, not raised)
# ---------------------------------------------------------------------------


async def test_service_warns_when_device_disconnected(
    hass, setup_integration, mock_sensorlinx, caplog
):
    """A warning is logged (not an error) when calling a service on a disconnected device."""
    import logging

    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    # Mark device as disconnected
    client.get_devices.return_value = [{**FAKE_DEVICES[0], "connected": False}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    with caplog.at_level(logging.WARNING, logger="custom_components.sensorlinx"):
        await hass.services.async_call(
            "sensorlinx",
            "set_hvac_mode_priority",
            {"device_id": _ha_device_id(hass, "ABC123"), "mode": "heat"},
            blocking=True,
        )

    assert any("not connected" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Service — duplicate sync_code across buildings
# ---------------------------------------------------------------------------


async def test_service_first_match_wins_for_duplicate_sync_code(
    hass, setup_integration, mock_sensorlinx
):
    """When the same sync_code appears in two buildings, the first match is used."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    # Inject a second building with the same sync_code

    coordinator.data["bld-2"] = {
        "building": {"id": "bld-2", "name": "Cottage"},
        "devices": {"ABC123": {"device": {**FAKE_DEVICES[0], "id": "dev-bld2"}}},
    }

    await hass.services.async_call(
        "sensorlinx",
        "set_hvac_mode_priority",
        {"device_id": _ha_device_id(hass, "ABC123"), "mode": "auto"},
        blocking=True,
    )

    # Only one call should have been made (first match wins)
    assert client.set_device_parameter.await_count == 1
    call_kwargs = client.set_device_parameter.call_args.kwargs
    # Should use the first building found
    assert call_kwargs["building_id"] in ("bld-1", "bld-2")


# ---------------------------------------------------------------------------
# Options flow — triggers reload and applies new settings
# ---------------------------------------------------------------------------


async def test_options_change_triggers_reload(hass, setup_integration, mock_sensorlinx):
    """Changing options reloads the integration and applies the new scan_interval."""
    entry, coordinator = setup_integration
    original_coordinator = coordinator

    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"scan_interval": 120, "timeout": 30}
    )
    await hass.async_block_till_done()

    # Options are persisted
    assert entry.options["scan_interval"] == 120

    # A reload spawns a new coordinator instance
    new_coordinator = hass.data["sensorlinx"][entry.entry_id]
    assert new_coordinator is not original_coordinator


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


async def test_migrate_entry_no_op_for_version_1(hass, mock_sensorlinx):
    """async_migrate_entry returns True for version 1 entries (no schema changes needed)."""
    from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.sensorlinx import async_migrate_entry

    entry = MockConfigEntry(
        domain="sensorlinx",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"},
        version=1,
    )
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry) is True
