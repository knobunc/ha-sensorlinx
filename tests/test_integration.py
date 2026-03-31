"""Integration tests for the SensorLinx integration.

These tests exercise the full HA integration stack — entity registry,
device registry, config entry lifecycle, availability transitions, stale
cleanup, multi-entry setups, re-authentication flow, and service calls.
"""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, STATE_UNAVAILABLE
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pysensorlinx import InvalidCredentialsError

from .conftest import FAKE_BUILDINGS, FAKE_DEVICES
from .conftest import ha_device_id as _ha_device_id

# ---------------------------------------------------------------------------
# Entity registry state after setup
# ---------------------------------------------------------------------------


async def test_entity_registry_populated_after_setup(hass, setup_integration):
    """All expected entities are present in the entity registry after setup."""
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, setup_integration[0].entry_id)
    unique_ids = {e.unique_id for e in entries}

    # Sensor entities
    assert "ABC123_demand" in unique_ids
    assert "ABC123_temp_0" in unique_ids  # Tank (enabled)
    assert "ABC123_temp_1" in unique_ids  # Outdoor (enabled)
    assert "ABC123_temp_2" not in unique_ids  # Unused (disabled)

    # Binary sensor entities
    assert "ABC123_connected" in unique_ids
    assert "ABC123_demand_0" in unique_ids  # Heat
    assert "ABC123_demand_1" in unique_ids  # Cool
    assert "ABC123_stage_0" in unique_ids  # Stage 1 (enabled)
    assert "ABC123_stage_1" in unique_ids  # Stage 2 (enabled)
    assert "ABC123_stage_2" not in unique_ids  # Stage 3 (disabled)
    assert "ABC123_backup" in unique_ids
    assert "ABC123_pump_0" in unique_ids
    assert "ABC123_pump_1" in unique_ids
    assert "ABC123_reversing_valve" in unique_ids
    assert "ABC123_wsd_wwsd" in unique_ids
    assert "ABC123_wsd_cwsd" in unique_ids


async def test_device_registry_populated_after_setup(hass, setup_integration):
    """Device is registered with correct identifiers, model, and manufacturer."""
    entry, _ = setup_integration
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device({("sensorlinx", "ABC123")})

    assert device is not None
    assert device.name == "ECO Controller"
    assert device.model == "ECO-0600"
    assert device.sw_version == "2.0.1"
    assert device.manufacturer == "HBX Controls"
    assert device.suggested_area == "Home"


# ---------------------------------------------------------------------------
# Availability — coordinator failure
# ---------------------------------------------------------------------------


async def test_entities_unavailable_when_coordinator_fails(
    hass, setup_integration, mock_sensorlinx
):
    """All entities become unavailable when the coordinator update fails."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_buildings.side_effect = RuntimeError("network down")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.eco_controller_demand").state == STATE_UNAVAILABLE
    assert (
        hass.states.get("binary_sensor.eco_controller_connected").state
        == STATE_UNAVAILABLE
    )


async def test_entities_recover_after_coordinator_success(
    hass, setup_integration, mock_sensorlinx
):
    """Entities become available again once the coordinator succeeds."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    # Force a failure, then recover
    client.get_buildings.side_effect = RuntimeError("transient error")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    client.get_buildings.side_effect = None
    client.get_buildings.return_value = FAKE_BUILDINGS
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.eco_controller_demand").state != STATE_UNAVAILABLE


# ---------------------------------------------------------------------------
# Availability — device disappears from data
# ---------------------------------------------------------------------------


async def test_stale_cleanup_skipped_when_coordinator_fails(
    hass, setup_integration, mock_sensorlinx
):
    """Stale cleanup does NOT fire when the coordinator update itself fails.

    If the API is unreachable, devices should stay registered — they may simply
    be temporarily offline.  Only a *successful* update that omits a device
    should trigger removal.
    """
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    dev_reg = dr.async_get(hass)

    # Simulate a total API failure (coordinator update fails)
    client.get_buildings.side_effect = RuntimeError("network down")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Device must still be registered — coordinator failure ≠ device removed
    assert dev_reg.async_get_device({("sensorlinx", "ABC123")}) is not None


async def test_entity_removed_when_device_missing_from_data(
    hass, setup_integration, mock_sensorlinx
):
    """Entities are removed from the state machine when the stale cleanup fires.

    When the coordinator succeeds but a device is no longer in the response, the
    stale-cleanup listener removes it from both registries.  The state therefore
    becomes None rather than STATE_UNAVAILABLE (which is the coordinator-failure path).
    """
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    # Return an empty device list so the device disappears from the API
    client.get_devices.return_value = []
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Entity has been removed entirely (not just marked unavailable)
    assert hass.states.get("sensor.eco_controller_demand") is None
    assert hass.states.get("binary_sensor.eco_controller_connected") is None


async def test_entity_available_returns_true_when_device_present(
    hass, setup_integration
):
    """Entities report available when the device is in coordinator data."""
    entry, coordinator = setup_integration
    state = hass.states.get("sensor.eco_controller_demand")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


# ---------------------------------------------------------------------------
# Stale entity and device cleanup
# ---------------------------------------------------------------------------


async def test_stale_device_removed_after_coordinator_update(
    hass, setup_integration, mock_sensorlinx
):
    """Devices and their entities are removed from the registries after disappearing."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    # Confirm device exists before
    assert dev_reg.async_get_device({("sensorlinx", "ABC123")}) is not None

    # API returns no devices
    client.get_devices.return_value = []
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Device and its entities should be gone from registries
    assert dev_reg.async_get_device({("sensorlinx", "ABC123")}) is None
    entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    assert all(e.unique_id.startswith("ABC123") is False for e in entries)


async def test_new_device_added_automatically(hass, setup_integration, mock_sensorlinx):
    """New devices appearing in the API are automatically added without a reload."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    ent_reg = er.async_get(hass)
    initial_count = len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))

    # Add a second device with the same shape as the first
    new_device = {**FAKE_DEVICES[0], "syncCode": "NEW999", "name": "New Device"}
    client.get_devices.return_value = [FAKE_DEVICES[0], new_device]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Entity count should have grown — new entities added automatically
    new_count = len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))
    assert new_count > initial_count
    assert any(
        e.unique_id.startswith("NEW999")
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    )


async def test_device_reappears_after_stale_cleanup(
    hass, setup_integration, mock_sensorlinx
):
    """Entities are recreated automatically when a previously removed device comes back.

    This exercises the entity-registry check in the coordinator listener:
    stale cleanup removes the entities from the registry, so when the device
    reappears the listener sees no registered entity and creates a fresh one.
    """
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    dev_reg = dr.async_get(hass)

    # Step 1: device disappears → stale cleanup fires
    client.get_devices.return_value = []
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert dev_reg.async_get_device({("sensorlinx", "ABC123")}) is None
    assert hass.states.get("sensor.eco_controller_demand") is None

    # Step 2: device comes back → coordinator listener adds new entities
    client.get_devices.return_value = FAKE_DEVICES
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert dev_reg.async_get_device({("sensorlinx", "ABC123")}) is not None
    demand_state = hass.states.get("sensor.eco_controller_demand")
    assert demand_state is not None
    assert demand_state.state != STATE_UNAVAILABLE


# ---------------------------------------------------------------------------
# Manual device removal (async_remove_config_entry_device)
# ---------------------------------------------------------------------------


async def test_remove_config_entry_device_blocked_when_device_present(
    hass, setup_integration
):
    """Removing a device via the UI is blocked while it is still in the API."""
    entry, _ = setup_integration
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device({("sensorlinx", "ABC123")})
    assert device is not None

    from custom_components.sensorlinx import async_remove_config_entry_device

    result = await async_remove_config_entry_device(hass, entry, device)
    assert result is False


async def test_remove_config_entry_device_allowed_when_device_gone(
    hass, setup_integration, mock_sensorlinx
):
    """Removing a device via the UI is allowed once it has left the API."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    # Device disappears from API and stale cleanup fires
    client.get_devices.return_value = []
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Device should be gone from registry after cleanup, but simulate the case
    # where the user still has a stale DeviceEntry reference (e.g., before page
    # refresh).  Re-create a minimal stand-in with the same identifiers.
    from unittest.mock import MagicMock

    from custom_components.sensorlinx import async_remove_config_entry_device

    fake_device = MagicMock()
    fake_device.identifiers = {("sensorlinx", "ABC123")}

    # Coordinator data is now empty — removal should be allowed
    result = await async_remove_config_entry_device(hass, entry, fake_device)
    assert result is True


# ---------------------------------------------------------------------------
# Multi-entry (two independent accounts)
# ---------------------------------------------------------------------------


async def test_two_entries_are_independent(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """Two config entries each register their own devices independently."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx

    # First account
    device_a = {**FAKE_DEVICES[0], "syncCode": "AAA111", "name": "Device A"}
    # Second account
    device_b = {**FAKE_DEVICES[0], "syncCode": "BBB222", "name": "Device B"}

    client.get_devices.side_effect = [
        [device_a],  # first entry setup
        [device_b],  # second entry setup
    ]

    entry_a = MockConfigEntry(
        domain="sensorlinx",
        data={CONF_EMAIL: "a@example.com", CONF_PASSWORD: "pass"},
        entry_id="entry_a",
        unique_id="a@example.com",
    )
    entry_b = MockConfigEntry(
        domain="sensorlinx",
        data={CONF_EMAIL: "b@example.com", CONF_PASSWORD: "pass"},
        entry_id="entry_b",
        unique_id="b@example.com",
    )
    # Set up sequentially — add and await each entry individually so the
    # integration has time to complete setup before the second entry is added.
    entry_a.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_b.entry_id)
    await hass.async_block_till_done()

    dev_reg = dr.async_get(hass)
    assert dev_reg.async_get_device({("sensorlinx", "AAA111")}) is not None
    assert dev_reg.async_get_device({("sensorlinx", "BBB222")}) is not None

    ent_reg = er.async_get(hass)
    a_ids = {e.unique_id for e in er.async_entries_for_config_entry(ent_reg, "entry_a")}
    b_ids = {e.unique_id for e in er.async_entries_for_config_entry(ent_reg, "entry_b")}
    assert a_ids.isdisjoint(b_ids), "Entries share entity unique IDs — they should not"


# ---------------------------------------------------------------------------
# Re-authentication flow
# ---------------------------------------------------------------------------


async def test_reauth_flow_success(hass, setup_integration, mock_sensorlinx):
    """Re-auth flow updates credentials and reloads the entry."""
    entry, _ = setup_integration

    with patch("custom_components.sensorlinx.config_flow._authenticate", AsyncMock()):
        result = await hass.config_entries.flow.async_init(
            "sensorlinx",
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "newpassword"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "newpassword"


async def test_reauth_flow_invalid_credentials(
    hass, setup_integration, mock_sensorlinx
):
    """Re-auth flow shows error when credentials are invalid."""
    entry, _ = setup_integration

    with patch(
        "custom_components.sensorlinx.config_flow._authenticate",
        AsyncMock(side_effect=InvalidCredentialsError("bad")),
    ):
        result = await hass.config_entries.flow.async_init(
            "sensorlinx",
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "wrong"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_reauth_flow_timeout(hass, setup_integration, mock_sensorlinx):
    """Re-auth flow shows cannot_connect when the API times out."""
    entry, _ = setup_integration

    with patch(
        "custom_components.sensorlinx.config_flow._authenticate",
        AsyncMock(side_effect=TimeoutError()),
    ):
        result = await hass.config_entries.flow.async_init(
            "sensorlinx",
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pass"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


# ---------------------------------------------------------------------------
# Service calls
# ---------------------------------------------------------------------------


async def test_service_set_hvac_mode(hass, setup_integration, mock_sensorlinx):
    """set_hvac_mode_priority service calls the API and triggers a refresh."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    await hass.services.async_call(
        "sensorlinx",
        "set_hvac_mode_priority",
        {"device_id": _ha_device_id(hass, "ABC123"), "mode": "heat"},
        blocking=True,
    )

    client.set_device_parameter.assert_awaited_once()
    call_kwargs = client.set_device_parameter.call_args.kwargs
    assert call_kwargs["hvac_mode_priority"] == "heat"
    assert call_kwargs["building_id"] == "bld-1"


async def test_service_set_hvac_mode_unknown_device(hass, setup_integration):
    """set_hvac_mode_priority raises when the device_id is not in the registry."""
    from homeassistant.exceptions import ServiceValidationError

    with pytest.raises((ServiceValidationError, Exception)):
        await hass.services.async_call(
            "sensorlinx",
            "set_hvac_mode_priority",
            {"device_id": "00000000000000000000000000000000", "mode": "cool"},
            blocking=True,
        )


async def test_service_set_permanent_demand(hass, setup_integration, mock_sensorlinx):
    """set_permanent_demand service calls the API with the correct parameters."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    await hass.services.async_call(
        "sensorlinx",
        "set_permanent_demand",
        {
            "device_id": _ha_device_id(hass, "ABC123"),
            "permanent_hd": True,
            "permanent_cd": False,
        },
        blocking=True,
    )

    client.set_device_parameter.assert_awaited_once()
    call_kwargs = client.set_device_parameter.call_args.kwargs
    assert call_kwargs["permanent_hd"] is True
    assert call_kwargs["permanent_cd"] is False
    assert call_kwargs["building_id"] == "bld-1"


async def test_service_set_permanent_demand_requires_at_least_one_flag(
    hass, setup_integration
):
    """set_permanent_demand raises when neither permanent_hd nor permanent_cd is given."""
    from homeassistant.exceptions import ServiceValidationError

    with pytest.raises((ServiceValidationError, Exception)):
        await hass.services.async_call(
            "sensorlinx",
            "set_permanent_demand",
            {"device_id": _ha_device_id(hass, "ABC123")},
            blocking=True,
        )
