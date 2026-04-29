"""Shared fixtures for ha-sensorlinx tests."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import device_registry as dr

# ---------------------------------------------------------------------------
# Fake API data — mirrors what pysensorlinx.Sensorlinx returns
# ---------------------------------------------------------------------------

FAKE_BUILDINGS = [
    {
        "id": "bld-1",
        "name": "Home",
        "weather": {
            "weather": {
                "temp": 72,
                "feelsLike": 70,
                "min": 65,
                "max": 78,
                "pressure": 1013,
                "humidity": 55,
                "wind": 5.5,
                "windDir": 180,
                "clouds": 40,
                "snow": 0,
                "rain": 0,
                "description": "partly cloudy",
                "icon": "03d",
                "weatherId": 802,
            },
            "forecast": [
                {
                    "time": "2026-04-24T12:00:00Z",
                    "pop": 20,
                    "snow": 0,
                    "temp": 75,
                    "min": 68,
                    "max": 80,
                    "description": "cloudy",
                    "icon": "04d",
                    "weatherId": 804,
                }
            ],
        },
    }
]

FAKE_DEVICES = [
    {
        "syncCode": "ABC123",
        "name": "ECO Controller",
        "deviceType": "ECO-0600",
        "firmVer": "2.0.1",
        "connected": True,
        "dmd": 45,
        "prior": 0,
        "wwsd": 80,
        "dot": 45,
        "htDif": 3,
        "mbt": 90,
        "dbt": 105,
        "auxDif": 3,
        "dhwOn": True,
        "dhwT": 120,
        "cwsd": 75,
        "cdot": 90,
        "clDif": 8,
        "mst": 45,
        "dst": 60,
        "temperatures": [
            {
                "enabled": True,
                "title": "Tank",
                "current": 120.5,
                "target": 130.0,
                "activated": True,
                "activatedState": "heat",
            },
            {
                "enabled": True,
                "title": "Outdoor",
                "current": 38.2,
                "target": None,
                "activated": False,
            },
            {"enabled": False, "title": "Unused", "current": None},
            {
                "enabled": True,
                "title": "DHW Tank",
                "current": 119.5,
                "target": 119.0,
                "activated": False,
            },
        ],
        "demands": [
            {"title": "Heat", "activated": True},
            {"title": "Cool", "activated": False},
        ],
        "stages": [
            {
                "enabled": True,
                "title": "Stage 1",
                "activated": True,
                "runTime": "2h 15m",
            },
            {"enabled": True, "title": "Stage 2", "activated": False, "runTime": "0m"},
            {"enabled": False, "title": "Stage 3", "activated": False, "runTime": "0m"},
        ],
        "backup": {"enabled": True, "activated": False, "runTime": "0m"},
        "pumps": [
            {"title": "Supply Pump", "activated": True},
            {"title": "Load Pump", "activated": False},
        ],
        "reversingValve": {"activated": False},
        "relays": [True, False, True, False],
        "wsd": {
            "wwsd": {"title": "Warm Weather Shutdown", "activated": False},
            "cwsd": {"title": "Cold Weather Shutdown", "activated": False},
        },
    }
]

CONF_DATA = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "secret",
}


def ha_device_id(hass, sync_code: str) -> str:
    """Return the HA device registry ID for a SensorLinx sync_code."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device({("sensorlinx", sync_code)})
    assert device is not None, f"No HA device found for sync_code={sync_code}"
    return device.id


@pytest.fixture
def mock_client():
    """A pre-configured AsyncMock of pysensorlinx.Sensorlinx."""
    client = AsyncMock()
    client.get_buildings.return_value = FAKE_BUILDINGS
    client.get_devices.return_value = FAKE_DEVICES
    return client


@pytest.fixture
def mock_sensorlinx(mock_client):
    """Patch the Sensorlinx constructor everywhere the integration imports it."""
    with (
        patch(
            "custom_components.sensorlinx.Sensorlinx", return_value=mock_client
        ) as patched,
        patch(
            "custom_components.sensorlinx.config_flow.Sensorlinx",
            return_value=mock_client,
        ),
        patch(
            "custom_components.sensorlinx.coordinator.Sensorlinx",
            return_value=mock_client,
        ),
    ):
        yield patched, mock_client


@pytest.fixture
async def setup_integration(hass, mock_sensorlinx, enable_custom_integrations):
    """Set up the integration and return (entry, coordinator)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx

    entry = MockConfigEntry(
        domain="sensorlinx",
        data=CONF_DATA,
        entry_id="test_entry",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = hass.data["sensorlinx"][entry.entry_id]
    return entry, coordinator
