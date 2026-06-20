"""Tests for SensorLinx switch entities."""

import pytest
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from pysensorlinx import Temperature

from custom_components.sensorlinx.switch import (
    _BOOL_SWITCHES,
    _SENTINEL_SWITCHES,
    SensorLinxBoolSwitch,
    SensorLinxDHWSwitch,
    SensorLinxSentinelSwitch,
)

from .conftest import CONF_DATA, FAKE_DEVICES

# ---------------------------------------------------------------------------
# DHW switch
# ---------------------------------------------------------------------------


async def test_dhw_switch_on(hass, setup_integration):
    state = hass.states.get("switch.eco_controller_dhw_enabled")
    assert state is not None
    assert state.state == "on"


async def test_dhw_switch_off(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "dhwOn": False}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("switch.eco_controller_dhw_enabled").state == "off"


async def test_dhw_switch_turn_on(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.eco_controller_dhw_enabled"},
        blocking=True,
    )

    client.set_device_parameter.assert_awaited_once()
    kw = client.set_device_parameter.call_args.kwargs
    assert kw["dhw_enabled"] is True


async def test_dhw_switch_turn_off(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.eco_controller_dhw_enabled"},
        blocking=True,
    )

    client.set_device_parameter.assert_awaited_once()
    kw = client.set_device_parameter.call_args.kwargs
    assert kw["dhw_enabled"] is False


async def test_dhw_switch_not_created_when_absent(
    hass, mock_sensorlinx, enable_custom_integrations
):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx
    device = {**FAKE_DEVICES[0]}
    device.pop("dhwOn", None)
    client.get_devices.return_value = [device]

    entry = MockConfigEntry(
        domain="sensorlinx", data=CONF_DATA, entry_id="test_dhw_absent"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("switch.eco_controller_dhw_enabled") is None


# ---------------------------------------------------------------------------
# Sentinel switches — WWSD
# ---------------------------------------------------------------------------


async def test_wwsd_switch_on(hass, setup_integration):
    """wwsd=80 (not sentinel 32) → on."""
    state = hass.states.get("switch.eco_controller_warm_weather_shutdown")
    assert state is not None
    assert state.state == "on"


async def test_wwsd_switch_off_at_sentinel(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "wwsd": 32}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("switch.eco_controller_warm_weather_shutdown").state == "off"


async def test_wwsd_switch_turn_off(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.eco_controller_warm_weather_shutdown"},
        blocking=True,
    )

    kw = client.set_device_parameter.call_args.kwargs
    assert kw["warm_weather_shutdown"] == "off"


async def test_wwsd_switch_turn_on(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.eco_controller_warm_weather_shutdown"},
        blocking=True,
    )

    kw = client.set_device_parameter.call_args.kwargs
    temp = kw["warm_weather_shutdown"]
    assert isinstance(temp, Temperature)
    assert temp.to_fahrenheit() == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# Sentinel switches — hot outdoor reset
# ---------------------------------------------------------------------------


async def test_hot_outdoor_reset_switch_on(hass, setup_integration):
    """dot=45 (not sentinel -41) → on."""
    state = hass.states.get("switch.eco_controller_hot_outdoor_reset")
    assert state is not None
    assert state.state == "on"


async def test_hot_outdoor_reset_switch_off_at_sentinel(
    hass, setup_integration, mock_sensorlinx
):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "dot": -41}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("switch.eco_controller_hot_outdoor_reset").state == "off"


# ---------------------------------------------------------------------------
# Sentinel switches — CWSD
# ---------------------------------------------------------------------------


async def test_cwsd_switch_on(hass, setup_integration):
    """cwsd=75 (not sentinel 32) → on."""
    state = hass.states.get("switch.eco_controller_cold_weather_shutdown")
    assert state is not None
    assert state.state == "on"


# ---------------------------------------------------------------------------
# Sentinel switches — cold outdoor reset
# ---------------------------------------------------------------------------


async def test_cold_outdoor_reset_switch_on(hass, setup_integration):
    """cdot=90 (not sentinel -41) → on."""
    state = hass.states.get("switch.eco_controller_cold_outdoor_reset")
    assert state is not None
    assert state.state == "on"


# ---------------------------------------------------------------------------
# Entity category
# ---------------------------------------------------------------------------


async def test_switch_entity_category_is_config(hass, setup_integration):
    ent_reg = er.async_get(hass)

    for entity_id in [
        "switch.eco_controller_dhw_enabled",
        "switch.eco_controller_warm_weather_shutdown",
        "switch.eco_controller_hot_outdoor_reset",
        "switch.eco_controller_cold_weather_shutdown",
        "switch.eco_controller_cold_outdoor_reset",
    ]:
        entry = ent_reg.async_get(entity_id)
        assert entry is not None, f"{entity_id} not found"
        assert entry.entity_category == EntityCategory.CONFIG


# ---------------------------------------------------------------------------
# Device disappears
# ---------------------------------------------------------------------------


async def test_is_on_returns_none_when_device_gone(hass, setup_integration):
    _, coordinator = setup_integration

    dhw = SensorLinxDHWSwitch(coordinator, "bld-1", "ABC123")
    sentinel = SensorLinxSentinelSwitch(
        coordinator, "bld-1", "ABC123", _SENTINEL_SWITCHES[0]
    )
    bool_sw = SensorLinxBoolSwitch(
        coordinator, "bld-1", "ABC123", _BOOL_SWITCHES[0]
    )

    coordinator.data.clear()

    assert dhw.is_on is None
    assert sentinel.is_on is None
    assert bool_sw.is_on is None


# ---------------------------------------------------------------------------
# Permanent demand switches
# ---------------------------------------------------------------------------


async def test_permanent_hd_off(hass, setup_integration):
    """permHD=False → off."""
    state = hass.states.get("switch.eco_controller_permanent_heat_demand")
    assert state is not None
    assert state.state == "off"


async def test_permanent_hd_on(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "permHD": True}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("switch.eco_controller_permanent_heat_demand").state == "on"


async def test_permanent_hd_turn_on(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.eco_controller_permanent_heat_demand"},
        blocking=True,
    )

    client.set_device_parameter.assert_awaited_once()
    kw = client.set_device_parameter.call_args.kwargs
    assert kw["permanent_hd"] is True


async def test_permanent_hd_turn_off(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.eco_controller_permanent_heat_demand"},
        blocking=True,
    )

    client.set_device_parameter.assert_awaited_once()
    kw = client.set_device_parameter.call_args.kwargs
    assert kw["permanent_hd"] is False


async def test_permanent_cd_off(hass, setup_integration):
    """permCD=False → off."""
    state = hass.states.get("switch.eco_controller_permanent_cool_demand")
    assert state is not None
    assert state.state == "off"


async def test_permanent_cd_turn_on(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.eco_controller_permanent_cool_demand"},
        blocking=True,
    )

    client.set_device_parameter.assert_awaited_once()
    kw = client.set_device_parameter.call_args.kwargs
    assert kw["permanent_cd"] is True


# ---------------------------------------------------------------------------
# All 5 switches created
# ---------------------------------------------------------------------------


async def test_all_switches_created(hass, setup_integration):
    expected = [
        "switch.eco_controller_dhw_enabled",
        "switch.eco_controller_warm_weather_shutdown",
        "switch.eco_controller_hot_outdoor_reset",
        "switch.eco_controller_cold_weather_shutdown",
        "switch.eco_controller_cold_outdoor_reset",
        "switch.eco_controller_permanent_heat_demand",
        "switch.eco_controller_permanent_cool_demand",
    ]
    for entity_id in expected:
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"
