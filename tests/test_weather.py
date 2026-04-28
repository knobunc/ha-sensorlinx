"""Tests for SensorLinx weather platform."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import CONF_DATA


async def test_weather_entity_created(hass, setup_integration):
    """Weather entity is created for building with weather data."""
    state = hass.states.get("weather.home_weather")
    assert state is not None


async def test_weather_current_conditions(hass, setup_integration):
    """Weather entity reflects current conditions from building data."""
    state = hass.states.get("weather.home_weather")
    assert state is not None
    # weatherId 802 → "cloudy"
    assert state.state == "cloudy"
    # Temperature 72°F → ~22.2°C (HA converts to metric in tests)
    assert float(state.attributes["temperature"]) == pytest.approx(22.2, abs=0.5)
    assert state.attributes["humidity"] == 55
    assert state.attributes["wind_bearing"] == 180


async def test_weather_forecast_hourly(hass, setup_integration):
    """Weather entity provides hourly forecast."""
    state = hass.states.get("weather.home_weather")
    assert state is not None

    forecast = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": "weather.home_weather", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    fc = forecast["weather.home_weather"]["forecast"]
    assert len(fc) == 1
    assert fc[0]["condition"] == "cloudy"


async def test_weather_not_created_without_data(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """No weather entity when building has no weather data."""
    _, client = mock_sensorlinx
    client.get_buildings.return_value = [{"id": "bld-1", "name": "Home"}]

    entry = MockConfigEntry(domain="sensorlinx", data=CONF_DATA, entry_id="test_no_wx")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("weather.home_weather") is None


async def test_weather_unavailable_when_data_removed(
    hass, setup_integration, mock_sensorlinx
):
    """Weather entity becomes unavailable when weather data disappears."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_buildings.return_value = [{"id": "bld-1", "name": "Home"}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("weather.home_weather")
    assert state is not None
    assert state.state == "unavailable"
