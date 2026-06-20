"""Tests for SensorLinx number entities."""

import pytest
from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er
from pysensorlinx import Temperature, TemperatureDelta

from custom_components.sensorlinx.number import _NUMBER_ENTITIES, SensorLinxNumberEntity

from .conftest import CONF_DATA, FAKE_DEVICES

# ---------------------------------------------------------------------------
# All 12 numbers created
# ---------------------------------------------------------------------------


async def test_all_numbers_created(hass, setup_integration):
    expected = [
        "number.eco_controller_dhw_target_temperature",
        "number.eco_controller_dhw_differential",
        "number.eco_controller_min_tank_temperature",
        "number.eco_controller_max_tank_temperature",
        "number.eco_controller_heat_differential",
        "number.eco_controller_wwsd_temperature",
        "number.eco_controller_outdoor_reset_temperature",
        "number.eco_controller_cold_min_tank_temperature",
        "number.eco_controller_cold_max_tank_temperature",
        "number.eco_controller_cold_differential",
        "number.eco_controller_cwsd_temperature",
        "number.eco_controller_cold_outdoor_reset_temperature",
    ]
    for entity_id in expected:
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} was not created"


# ---------------------------------------------------------------------------
# Native values — temperature entities auto-convert to °C in metric test env
#
# HA auto-converts when device_class=TEMPERATURE:
#   120°F → 48.9°C, 90°F → 32.2°C, 105°F → 40.6°C, 80°F → 26.7°C
#   45°F → 7.2°C, 60°F → 15.6°C, 75°F → 23.9°C
#
# Delta entities (no device_class) remain in raw °F.
# ---------------------------------------------------------------------------


async def test_dhw_target_temp_value(hass, setup_integration):
    """120°F → ~49°C."""
    state = hass.states.get("number.eco_controller_dhw_target_temperature")
    assert float(state.state) == pytest.approx(49, abs=1)


async def test_dhw_differential_value(hass, setup_integration):
    """Delta — raw °F, no conversion."""
    state = hass.states.get("number.eco_controller_dhw_differential")
    assert float(state.state) == pytest.approx(3.0)


async def test_min_tank_temp_value(hass, setup_integration):
    """90°F → ~32°C."""
    state = hass.states.get("number.eco_controller_min_tank_temperature")
    assert float(state.state) == pytest.approx(32, abs=1)


async def test_max_tank_temp_value(hass, setup_integration):
    """105°F → ~41°C."""
    state = hass.states.get("number.eco_controller_max_tank_temperature")
    assert float(state.state) == pytest.approx(41, abs=1)


async def test_heat_differential_value(hass, setup_integration):
    """Delta — raw °F, no conversion."""
    state = hass.states.get("number.eco_controller_heat_differential")
    assert float(state.state) == pytest.approx(3.0)


async def test_wwsd_temp_value(hass, setup_integration):
    """80°F → ~27°C."""
    state = hass.states.get("number.eco_controller_wwsd_temperature")
    assert float(state.state) == pytest.approx(27, abs=1)


async def test_outdoor_reset_value(hass, setup_integration):
    """45°F → ~7°C."""
    state = hass.states.get("number.eco_controller_outdoor_reset_temperature")
    assert float(state.state) == pytest.approx(7, abs=1)


async def test_cold_min_tank_temp_value(hass, setup_integration):
    """45°F → ~7°C."""
    state = hass.states.get("number.eco_controller_cold_min_tank_temperature")
    assert float(state.state) == pytest.approx(7, abs=1)


async def test_cold_max_tank_temp_value(hass, setup_integration):
    """60°F → ~16°C."""
    state = hass.states.get("number.eco_controller_cold_max_tank_temperature")
    assert float(state.state) == pytest.approx(16, abs=1)


async def test_cold_differential_value(hass, setup_integration):
    """Delta — raw °F, no conversion."""
    state = hass.states.get("number.eco_controller_cold_differential")
    assert float(state.state) == pytest.approx(8.0)


async def test_cwsd_temp_value(hass, setup_integration):
    """75°F → ~24°C."""
    state = hass.states.get("number.eco_controller_cwsd_temperature")
    assert float(state.state) == pytest.approx(24, abs=1)


async def test_cold_outdoor_reset_value(hass, setup_integration):
    """90°F → ~32°C."""
    state = hass.states.get("number.eco_controller_cold_outdoor_reset_temperature")
    assert float(state.state) == pytest.approx(32, abs=1)


# ---------------------------------------------------------------------------
# Sentinel numbers return unknown when disabled
# ---------------------------------------------------------------------------


async def test_wwsd_temp_returns_unknown_at_sentinel(
    hass, setup_integration, mock_sensorlinx
):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "wwsd": 32}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("number.eco_controller_wwsd_temperature").state == "unknown"


async def test_outdoor_reset_returns_unknown_at_sentinel(
    hass, setup_integration, mock_sensorlinx
):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "dot": -41}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        hass.states.get("number.eco_controller_outdoor_reset_temperature").state
        == "unknown"
    )


async def test_cwsd_temp_returns_unknown_at_sentinel(
    hass, setup_integration, mock_sensorlinx
):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "cwsd": 32}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("number.eco_controller_cwsd_temperature").state == "unknown"


async def test_cold_outdoor_reset_returns_unknown_at_sentinel(
    hass, setup_integration, mock_sensorlinx
):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "cdot": -41}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        hass.states.get("number.eco_controller_cold_outdoor_reset_temperature").state
        == "unknown"
    )


# ---------------------------------------------------------------------------
# Set value — Temperature (service passes °C, entity receives native °F)
# ---------------------------------------------------------------------------


async def test_set_dhw_target_temp(hass, setup_integration, mock_sensorlinx):
    """set_value(54.4°C) → async_set_native_value(~130°F)."""
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.eco_controller_dhw_target_temperature", "value": 54.4},
        blocking=True,
    )

    client.set_device_parameter.assert_awaited_once()
    kw = client.set_device_parameter.call_args.kwargs
    assert isinstance(kw["dhw_target_temp"], Temperature)
    assert kw["dhw_target_temp"].to_fahrenheit() == pytest.approx(130.0, abs=0.2)


async def test_set_min_tank_temp(hass, setup_integration, mock_sensorlinx):
    """set_value(37.8°C) → async_set_native_value(~100°F)."""
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.eco_controller_min_tank_temperature", "value": 37.8},
        blocking=True,
    )

    kw = client.set_device_parameter.call_args.kwargs
    assert isinstance(kw["hot_tank_min_temp"], Temperature)
    assert kw["hot_tank_min_temp"].to_fahrenheit() == pytest.approx(100.0, abs=0.1)


# ---------------------------------------------------------------------------
# Set value — TemperatureDelta (no device_class, no conversion)
# ---------------------------------------------------------------------------


async def test_set_heat_differential(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.eco_controller_heat_differential", "value": 5},
        blocking=True,
    )

    kw = client.set_device_parameter.call_args.kwargs
    assert isinstance(kw["hot_tank_differential"], TemperatureDelta)
    assert kw["hot_tank_differential"].value == pytest.approx(5.0)


async def test_set_cold_differential(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.eco_controller_cold_differential", "value": 10},
        blocking=True,
    )

    kw = client.set_device_parameter.call_args.kwargs
    assert isinstance(kw["cold_tank_differential"], TemperatureDelta)
    assert kw["cold_tank_differential"].value == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Entity category
# ---------------------------------------------------------------------------


async def test_number_entity_category_is_config(hass, setup_integration):
    ent_reg = er.async_get(hass)

    for entity_id in [
        "number.eco_controller_dhw_target_temperature",
        "number.eco_controller_heat_differential",
        "number.eco_controller_min_tank_temperature",
    ]:
        entry = ent_reg.async_get(entity_id)
        assert entry is not None, f"{entity_id} not found"
        assert entry.entity_category == EntityCategory.CONFIG


# ---------------------------------------------------------------------------
# Min/max/step — converted to °C for temperature, raw °F for deltas
# ---------------------------------------------------------------------------


async def test_dhw_target_temp_min_max(hass, setup_integration):
    """min=33°F → ~0.6°C, max=180°F → ~82.2°C (HA rounds to step)."""
    state = hass.states.get("number.eco_controller_dhw_target_temperature")
    assert state.attributes["min"] == pytest.approx(0.6, abs=1.0)
    assert state.attributes["max"] == pytest.approx(82.2, abs=1.0)


async def test_cold_differential_min_max(hass, setup_integration):
    """Delta — raw °F, no conversion."""
    state = hass.states.get("number.eco_controller_cold_differential")
    assert state.attributes["min"] == pytest.approx(2)
    assert state.attributes["max"] == pytest.approx(100)


# ---------------------------------------------------------------------------
# Device gone
# ---------------------------------------------------------------------------


async def test_native_value_returns_none_when_device_gone(hass, setup_integration):
    _, coordinator = setup_integration

    entity = SensorLinxNumberEntity(coordinator, "bld-1", "ABC123", _NUMBER_ENTITIES[0])

    coordinator.data.clear()

    assert entity.native_value is None


# ---------------------------------------------------------------------------
# Number not created when device key absent
# ---------------------------------------------------------------------------


async def test_number_not_created_when_key_absent(
    hass, mock_sensorlinx, enable_custom_integrations
):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx
    device = {**FAKE_DEVICES[0]}
    device.pop("dhwT", None)
    client.get_devices.return_value = [device]

    entry = MockConfigEntry(
        domain="sensorlinx", data=CONF_DATA, entry_id="test_num_absent"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("number.eco_controller_dhw_target_temperature") is None


# ---------------------------------------------------------------------------
# State updates on coordinator refresh
# ---------------------------------------------------------------------------


async def test_number_updates_on_refresh(hass, setup_integration, mock_sensorlinx):
    """140°F → ~60°C."""
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "dhwT": 140}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("number.eco_controller_dhw_target_temperature")
    assert float(state.state) == pytest.approx(60, abs=1)
