"""Tests for SensorLinxCoordinator."""

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pysensorlinx import InvalidCredentialsError, LoginError

from custom_components.sensorlinx.coordinator import SensorLinxCoordinator

from .conftest import CONF_DATA, FAKE_BUILDINGS, FAKE_DEVICES


async def _make_coordinator(hass, client):
    coordinator = SensorLinxCoordinator(hass, client, CONF_DATA)
    await coordinator.async_refresh()
    return coordinator


async def test_fetch_structures_data(hass, mock_client):
    """Coordinator data has expected building/device hierarchy."""
    coordinator = await _make_coordinator(hass, mock_client)

    assert "bld-1" in coordinator.data
    building_data = coordinator.data["bld-1"]
    assert building_data["building"]["name"] == "Home"
    assert "ABC123" in building_data["devices"]

    device = building_data["devices"]["ABC123"]["device"]
    assert device["dmd"] == 45
    assert device["connected"] is True
    assert len(device["temperatures"]) == 3
    assert len(device["stages"]) == 3
    assert len(device["pumps"]) == 2
    assert len(device["relays"]) == 4


async def test_fetch_skips_device_without_sync_code(hass, mock_client):
    """Devices missing syncCode are excluded from coordinator data."""
    mock_client.get_devices.return_value = [
        {"name": "No Code", "dmd": 10},
        {"syncCode": "XYZ", "name": "Valid", "dmd": 20},
    ]
    coordinator = await _make_coordinator(hass, mock_client)

    devices = coordinator.data["bld-1"]["devices"]
    assert "XYZ" in devices
    assert len(devices) == 1


async def test_fetch_empty_buildings(hass, mock_client):
    """Empty building list returns empty data dict."""
    mock_client.get_buildings.return_value = []
    coordinator = await _make_coordinator(hass, mock_client)
    assert coordinator.data == {}


async def test_fetch_none_buildings(hass, mock_client):
    """None from get_buildings returns empty data dict."""
    mock_client.get_buildings.return_value = None
    coordinator = await _make_coordinator(hass, mock_client)
    assert coordinator.data == {}


async def test_fetch_devices_runtime_error_skips_building(hass, mock_client):
    """RuntimeError from get_devices for one building returns empty devices, not UpdateFailed."""
    mock_client.get_buildings.return_value = [
        {"id": "bld-1", "name": "Home"},
        {"id": "bld-2", "name": "Cottage"},
    ]
    mock_client.get_devices.side_effect = [
        RuntimeError("No device data found."),
        FAKE_DEVICES,
    ]
    coordinator = await _make_coordinator(hass, mock_client)

    assert coordinator.last_update_success is True
    assert coordinator.data["bld-1"]["devices"] == {}
    assert "ABC123" in coordinator.data["bld-2"]["devices"]


async def test_auth_error_triggers_relogin(hass, mock_client):
    """On LoginError, coordinator re-authenticates and retries fetch."""
    mock_client.get_buildings.side_effect = [LoginError("expired"), FAKE_BUILDINGS]
    mock_client.get_devices.return_value = FAKE_DEVICES

    coordinator = await _make_coordinator(hass, mock_client)

    mock_client.login.assert_awaited_once()
    assert "bld-1" in coordinator.data


async def test_auth_error_relogin_fails_raises_config_entry_auth_failed(
    hass, mock_client
):
    """If re-auth also fails with bad credentials, ConfigEntryAuthFailed is raised."""
    mock_client.get_buildings.side_effect = InvalidCredentialsError("bad creds")
    mock_client.login.side_effect = InvalidCredentialsError("still bad")

    coordinator = SensorLinxCoordinator(hass, mock_client, CONF_DATA)
    await coordinator.async_refresh()
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)


async def test_runtime_error_raises_update_failed(hass, mock_client):
    """RuntimeError from get_buildings becomes UpdateFailed."""
    mock_client.get_buildings.side_effect = RuntimeError("network down")

    coordinator = SensorLinxCoordinator(hass, mock_client, CONF_DATA)
    await coordinator.async_refresh()
    assert isinstance(coordinator.last_exception, UpdateFailed)


async def test_multiple_buildings(hass, mock_client):
    """Coordinator handles multiple buildings."""
    mock_client.get_buildings.return_value = [
        {"id": "bld-1", "name": "Home"},
        {"id": "bld-2", "name": "Cottage"},
    ]
    mock_client.get_devices.return_value = FAKE_DEVICES

    coordinator = await _make_coordinator(hass, mock_client)

    assert "bld-1" in coordinator.data
    assert "bld-2" in coordinator.data
    assert mock_client.get_devices.await_count == 2


async def test_timeout_raises_update_failed(hass, mock_client):
    """A TimeoutError during fetch is converted to UpdateFailed."""
    import asyncio

    mock_client.get_buildings.side_effect = asyncio.TimeoutError()

    coordinator = SensorLinxCoordinator(hass, mock_client, CONF_DATA)
    await coordinator.async_refresh()
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert "timed out" in str(coordinator.last_exception).lower()


async def test_configurable_scan_interval(hass, mock_client):
    """Custom scan interval is applied to update_interval."""
    from datetime import timedelta

    coordinator = SensorLinxCoordinator(hass, mock_client, CONF_DATA, scan_interval=120)
    assert coordinator.update_interval == timedelta(seconds=120)
