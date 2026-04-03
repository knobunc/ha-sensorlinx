"""Tests for config entry lifecycle: setup, unload, and service registration."""

from homeassistant.config_entries import ConfigEntryState

from custom_components.sensorlinx.services import (
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PERMANENT_DEMAND,
)

from .conftest import CONF_DATA, FAKE_DEVICES

# ---------------------------------------------------------------------------
# Unload entry
# ---------------------------------------------------------------------------


async def test_setup_closes_client_when_first_refresh_fails(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """If async_config_entry_first_refresh raises, client.close() is still called."""
    from homeassistant.config_entries import ConfigEntryState
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx
    client.get_buildings.side_effect = RuntimeError("first poll failed")

    entry = MockConfigEntry(domain="sensorlinx", data=CONF_DATA, entry_id="test_leak")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    client.close.assert_awaited_once()


async def test_unload_entry_closes_client(hass, setup_integration, mock_sensorlinx):
    """Unloading an entry calls client.close()."""
    _, client = mock_sensorlinx
    entry, _ = setup_integration

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    client.close.assert_awaited_once()


async def test_unload_entry_marks_entities_unavailable(hass, setup_integration):
    """After unload, HA keeps entity states as unavailable (restored=True) for later restoration."""
    from homeassistant.const import STATE_UNAVAILABLE

    entry, _ = setup_integration

    assert hass.states.get("sensor.eco_controller_demand").state != STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # HA preserves states as unavailable after platform unload for state restoration
    demand_state = hass.states.get("sensor.eco_controller_demand")
    assert demand_state is not None
    assert demand_state.state == STATE_UNAVAILABLE


async def test_unload_entry_sets_state_not_loaded(hass, setup_integration):
    """Entry state is NOT_LOADED after a successful unload."""
    entry, _ = setup_integration

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_services_registered_after_setup(hass, setup_integration):
    """Services are registered when at least one entry is set up."""
    assert hass.services.has_service("sensorlinx", SERVICE_SET_HVAC_MODE)
    assert hass.services.has_service("sensorlinx", SERVICE_SET_PERMANENT_DEMAND)


async def test_services_unregistered_after_last_entry_unloaded(hass, setup_integration):
    """Services are removed once the last config entry is unloaded."""
    entry, _ = setup_integration

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service("sensorlinx", SERVICE_SET_HVAC_MODE)
    assert not hass.services.has_service("sensorlinx", SERVICE_SET_PERMANENT_DEMAND)


async def test_sensors_available_after_reload(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """Sensors must be re-created (not stuck unavailable) after an integration reload.

    The reload path unloads the entry and calls async_setup_entry again with a fresh
    coordinator. A stale entity-registry check would skip creating entity objects on
    the second setup because the registry entries from the first setup still exist.
    This test asserts that sensors are live and not STATE_UNAVAILABLE after reload.
    """
    from homeassistant.const import STATE_UNAVAILABLE
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from .conftest import CONF_DATA

    _, client = mock_sensorlinx

    entry = MockConfigEntry(domain="sensorlinx", data=CONF_DATA, entry_id="test_reload")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.eco_controller_demand").state != STATE_UNAVAILABLE

    # Reload the entry (same as pressing Reload in the UI)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.eco_controller_demand")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_services_not_unregistered_when_one_entry_remains(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """Services stay registered when only one of two entries is unloaded."""
    from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx
    client.get_devices.return_value = FAKE_DEVICES

    entry_a = MockConfigEntry(
        domain="sensorlinx",
        data={CONF_EMAIL: "a@example.com", CONF_PASSWORD: "pass"},
        entry_id="entry_svc_a",
        unique_id="a@example.com",
    )
    entry_b = MockConfigEntry(
        domain="sensorlinx",
        data={CONF_EMAIL: "b@example.com", CONF_PASSWORD: "pass"},
        entry_id="entry_svc_b",
        unique_id="b@example.com",
    )
    entry_a.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    entry_b.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry_b.entry_id)
    await hass.async_block_till_done()

    # Unload first entry — second is still loaded, services should remain
    assert await hass.config_entries.async_unload(entry_a.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("sensorlinx", SERVICE_SET_HVAC_MODE)
    assert hass.services.has_service("sensorlinx", SERVICE_SET_PERMANENT_DEMAND)
