"""Tests for SensorLinx sensor entities."""

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .conftest import FAKE_DEVICES


async def test_demand_sensor_state(hass, setup_integration):
    """Demand sensor reflects dmd value from device."""
    state = hass.states.get("sensor.eco_controller_demand")
    assert state is not None
    assert state.state == "45"
    assert state.attributes["unit_of_measurement"] == "%"


async def test_temperature_sensor_state(hass, setup_integration):
    """Enabled temperature channels appear as sensor entities.

    HA converts native Fahrenheit values to Celsius (metric default in tests):
      120.5°F → ~49.2°C,  38.2°F → ~3.4°C

    target_temperature is also converted to match the display unit:
      130.0°F → ~54.4°C
    """
    tank = hass.states.get("sensor.eco_controller_tank")
    assert tank is not None
    assert float(tank.state) == pytest.approx(49.2, abs=0.1)
    # target_temperature must be in the same unit as native_value (Celsius in tests)
    assert tank.attributes.get("target_temperature") == pytest.approx(54.4, abs=0.1)
    assert tank.attributes.get("state") == "heating"

    outdoor = hass.states.get("sensor.eco_controller_outdoor")
    assert outdoor is not None
    assert float(outdoor.state) == pytest.approx(3.4, abs=0.1)


async def test_disabled_temperature_channel_excluded(hass, setup_integration):
    """Disabled temperature channels are not exposed as entities."""
    assert hass.states.get("sensor.eco_controller_unused") is None


async def test_temperature_activated_without_activated_state(
    hass, setup_integration, mock_sensorlinx
):
    """Temperature sensor with activated=True but no activatedState uses active/idle fallback."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    device = {
        **FAKE_DEVICES[0],
        "temperatures": [
            {"enabled": True, "title": "Tank", "current": 100.0, "activated": True},
            {"enabled": True, "title": "Outdoor", "current": 50.0, "activated": False},
        ],
    }
    client.get_devices.return_value = [device]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    tank = hass.states.get("sensor.eco_controller_tank")
    assert tank.attributes.get("state") == "active"

    outdoor = hass.states.get("sensor.eco_controller_outdoor")
    assert outdoor.attributes.get("state") == "idle"


async def test_temperature_missing_current_value(
    hass, setup_integration, mock_sensorlinx
):
    """Temperature sensor with None current value returns unknown state."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    device = {
        **FAKE_DEVICES[0],
        "temperatures": [{"enabled": True, "title": "Tank", "current": None}],
    }
    client.get_devices.return_value = [device]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.eco_controller_tank")
    assert state.state == "unknown"


async def test_temperature_no_target_no_state_attrs(
    hass, setup_integration, mock_sensorlinx
):
    """Temperature sensor without target/activatedState has no extra attributes."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    device = {
        **FAKE_DEVICES[0],
        "temperatures": [{"enabled": True, "title": "Tank", "current": 100.0}],
    }
    client.get_devices.return_value = [device]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.eco_controller_tank")
    assert "target_temperature" not in state.attributes
    assert "state" not in state.attributes


async def test_temperature_target_in_fahrenheit(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """target_temperature is not converted when HA unit system is imperial (°F)."""
    from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from .conftest import CONF_DATA

    hass.config.units = US_CUSTOMARY_SYSTEM

    _, client = mock_sensorlinx

    entry = MockConfigEntry(domain="sensorlinx", data=CONF_DATA, entry_id="test_f")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    tank = hass.states.get("sensor.eco_controller_tank")
    assert tank is not None
    # native_value 120.5°F — HA does not convert when unit matches native unit
    # target_temperature should pass through unchanged (130.0°F)
    assert tank.attributes.get("target_temperature") == pytest.approx(130.0, abs=0.1)


async def test_temperature_target_sensors_created(hass, setup_integration):
    """Target sensors are created for channels with non-null targets."""
    assert hass.states.get("sensor.eco_controller_tank_target") is not None
    assert hass.states.get("sensor.eco_controller_dhw_tank_target") is not None


async def test_temperature_target_sensor_states(hass, setup_integration):
    """Target sensor values are converted from °F to the HA display unit (°C in tests).

    Tank target: 130.0°F → ~54.4°C
    DHW Tank target: 119.0°F → ~48.3°C
    """
    tank_target = hass.states.get("sensor.eco_controller_tank_target")
    assert float(tank_target.state) == pytest.approx(54.4, abs=0.1)

    dhw_target = hass.states.get("sensor.eco_controller_dhw_tank_target")
    assert float(dhw_target.state) == pytest.approx(48.3, abs=0.1)


async def test_outdoor_has_no_target_sensor(hass, setup_integration):
    """Outdoor channel has no target, so no target sensor is created."""
    assert hass.states.get("sensor.eco_controller_outdoor_target") is None


async def test_demand_sensor_updates(hass, setup_integration, mock_sensorlinx):
    """Demand sensor updates when coordinator fetches new data."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "dmd": 80}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.eco_controller_demand").state == "80"


async def test_device_removed_when_device_disappears(
    hass, setup_integration, mock_sensorlinx
):
    """Entities are removed from the registry when their device disappears from the API.

    With stale cleanup enabled, a successful coordinator fetch with an empty device
    list triggers removal of the device and its entities from the registries, so
    hass.states returns None rather than STATE_UNAVAILABLE.
    """
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = []
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.eco_controller_demand") is None


async def test_hvac_priority_sensor(hass, setup_integration):
    """Priority sensor maps prior=0 to 'heat'."""
    state = hass.states.get("sensor.eco_controller_hvac_priority")
    assert state is not None
    assert state.state == "heat"


async def test_hvac_priority_sensor_updates(hass, setup_integration, mock_sensorlinx):
    """Priority sensor reflects updated prior values."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "prior": 1}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.eco_controller_hvac_priority").state == "cool"

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "prior": 2}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.eco_controller_hvac_priority").state == "auto"


async def test_wwsd_temp_sensor(hass, setup_integration):
    """WWSD temperature sensor converts 80°F to ~26.7°C in metric."""
    state = hass.states.get("sensor.eco_controller_wwsd_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(26.7, abs=0.1)


async def test_wwsd_temp_sentinel_returns_none(
    hass, setup_integration, mock_sensorlinx
):
    """WWSD=32 (sentinel for 'off') results in unknown state."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "wwsd": 32}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.eco_controller_wwsd_temperature").state == "unknown"


async def test_outdoor_reset_sensor(hass, setup_integration):
    """Outdoor reset sensor converts 45°F to ~7.2°C in metric."""
    state = hass.states.get("sensor.eco_controller_outdoor_reset_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(7.2, abs=0.1)


async def test_outdoor_reset_sentinel_returns_none(
    hass, setup_integration, mock_sensorlinx
):
    """dot=-41 (sentinel for 'off') results in unknown state."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "dot": -41}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.eco_controller_outdoor_reset_temperature").state
        == "unknown"
    )


async def test_min_tank_temp_sensor(hass, setup_integration):
    """Min tank temperature sensor converts 90°F to ~32.2°C in metric."""
    state = hass.states.get("sensor.eco_controller_min_tank_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(32.2, abs=0.1)


async def test_max_tank_temp_sensor(hass, setup_integration):
    """Max tank temperature sensor converts 105°F to ~40.6°C in metric."""
    state = hass.states.get("sensor.eco_controller_max_tank_temperature")
    assert state is not None
    assert float(state.state) == pytest.approx(40.6, abs=0.1)


async def test_heat_differential_sensor(hass, setup_integration):
    """Heat differential sensor reports raw °F delta value."""
    state = hass.states.get("sensor.eco_controller_heat_differential")
    assert state is not None
    assert float(state.state) == pytest.approx(3.0, abs=0.01)


async def test_dhw_differential_sensor(hass, setup_integration):
    """DHW differential sensor reports raw °F delta value."""
    state = hass.states.get("sensor.eco_controller_dhw_differential")
    assert state is not None
    assert float(state.state) == pytest.approx(3.0, abs=0.01)


async def test_device_info(hass, setup_integration):
    """Device info fields are populated from pysensorlinx dict keys."""
    entity_reg = er.async_get(hass)
    entity = entity_reg.async_get("sensor.eco_controller_demand")
    assert entity is not None

    device_reg = dr.async_get(hass)
    device = device_reg.async_get(entity.device_id)
    assert device.model == "ECO-0600"
    assert device.sw_version == "2.0.1"
    assert device.manufacturer == "HBX Controls"
    assert device.suggested_area == "Home"
