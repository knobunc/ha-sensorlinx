"""Tests for SensorLinx binary sensor entities."""

from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er

from .conftest import FAKE_DEVICES

# ---------------------------------------------------------------------------
# Connected sensor
# ---------------------------------------------------------------------------


async def test_connected_sensor_on(hass, setup_integration):
    state = hass.states.get("binary_sensor.eco_controller_connected")
    assert state is not None
    assert state.state == "on"


async def test_connected_sensor_is_diagnostic(hass, setup_integration):
    """Connected sensor is classified as DIAGNOSTIC (appears in device Diagnostic section)."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("binary_sensor.eco_controller_connected")
    assert entry is not None
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


async def test_connected_sensor_off(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "connected": False}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.eco_controller_connected").state == "off"


async def test_connected_sensor_none_value(hass, setup_integration, mock_sensorlinx):
    """connected=None results in unknown state."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "connected": None}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.eco_controller_connected").state == "unknown"


# ---------------------------------------------------------------------------
# Demand channels
# ---------------------------------------------------------------------------


async def test_demand_active_sensors(hass, setup_integration):
    assert hass.states.get("binary_sensor.eco_controller_heat_demand").state == "on"
    assert hass.states.get("binary_sensor.eco_controller_cool_demand").state == "off"


async def test_demand_sensors_update(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [
        {
            **FAKE_DEVICES[0],
            "demands": [
                {"title": "Heat", "activated": False},
                {"title": "Cool", "activated": True},
            ],
        }
    ]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.eco_controller_heat_demand").state == "off"
    assert hass.states.get("binary_sensor.eco_controller_cool_demand").state == "on"


# ---------------------------------------------------------------------------
# Heat pump stages
# ---------------------------------------------------------------------------


async def test_stage_sensors_created_for_enabled_stages(hass, setup_integration):
    """Only enabled stages get binary sensor entities."""
    assert hass.states.get("binary_sensor.eco_controller_stage_1") is not None
    assert hass.states.get("binary_sensor.eco_controller_stage_2") is not None
    assert hass.states.get("binary_sensor.eco_controller_stage_3") is None  # disabled


async def test_stage_sensor_state(hass, setup_integration):
    assert hass.states.get("binary_sensor.eco_controller_stage_1").state == "on"
    assert hass.states.get("binary_sensor.eco_controller_stage_2").state == "off"


async def test_stage_sensor_run_time_attribute(hass, setup_integration):
    state = hass.states.get("binary_sensor.eco_controller_stage_1")
    assert state.attributes.get("run_time") == "2h 15m"


async def test_stage_sensors_update(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [
        {
            **FAKE_DEVICES[0],
            "stages": [
                {
                    "enabled": True,
                    "title": "Stage 1",
                    "activated": False,
                    "runTime": "0m",
                },
                {
                    "enabled": True,
                    "title": "Stage 2",
                    "activated": True,
                    "runTime": "1h",
                },
            ],
        }
    ]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.eco_controller_stage_1").state == "off"
    assert hass.states.get("binary_sensor.eco_controller_stage_2").state == "on"


# ---------------------------------------------------------------------------
# Backup heat
# ---------------------------------------------------------------------------


async def test_backup_sensor_created_when_enabled(hass, setup_integration):
    assert hass.states.get("binary_sensor.eco_controller_backup_heat") is not None


async def test_backup_sensor_state(hass, setup_integration):
    assert hass.states.get("binary_sensor.eco_controller_backup_heat").state == "off"


async def test_backup_sensor_run_time_attribute(hass, setup_integration):
    state = hass.states.get("binary_sensor.eco_controller_backup_heat")
    assert state.attributes.get("run_time") == "0m"


async def test_backup_sensor_not_created_when_disabled(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """No backup entity when backup.enabled is False."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from .conftest import CONF_DATA

    _, client = mock_sensorlinx
    client.get_devices.return_value = [
        {
            **FAKE_DEVICES[0],
            "backup": {"enabled": False, "activated": False, "runTime": "0m"},
        }
    ]

    entry = MockConfigEntry(domain="sensorlinx", data=CONF_DATA, entry_id="test2")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.eco_controller_backup_heat") is None


# ---------------------------------------------------------------------------
# Pumps
# ---------------------------------------------------------------------------


async def test_pump_sensors_created(hass, setup_integration):
    assert hass.states.get("binary_sensor.eco_controller_supply_pump") is not None
    assert hass.states.get("binary_sensor.eco_controller_load_pump") is not None


async def test_pump_sensor_states(hass, setup_integration):
    assert hass.states.get("binary_sensor.eco_controller_supply_pump").state == "on"
    assert hass.states.get("binary_sensor.eco_controller_load_pump").state == "off"


# ---------------------------------------------------------------------------
# Reversing valve
# ---------------------------------------------------------------------------


async def test_reversing_valve_sensor_created(hass, setup_integration):
    assert hass.states.get("binary_sensor.eco_controller_reversing_valve") is not None


async def test_reversing_valve_state(hass, setup_integration):
    assert (
        hass.states.get("binary_sensor.eco_controller_reversing_valve").state == "off"
    )


async def test_reversing_valve_not_created_when_absent(
    hass, mock_sensorlinx, enable_custom_integrations
):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from .conftest import CONF_DATA

    _, client = mock_sensorlinx
    device = {**FAKE_DEVICES[0]}
    device.pop("reversingValve", None)
    client.get_devices.return_value = [device]

    entry = MockConfigEntry(domain="sensorlinx", data=CONF_DATA, entry_id="test3")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.eco_controller_reversing_valve") is None


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Weather shutdown
# ---------------------------------------------------------------------------


async def test_wsd_sensors_created(hass, setup_integration):
    assert (
        hass.states.get("binary_sensor.eco_controller_warm_weather_shutdown")
        is not None
    )
    assert (
        hass.states.get("binary_sensor.eco_controller_cold_weather_shutdown")
        is not None
    )


async def test_wsd_sensors_off_by_default(hass, setup_integration):
    assert (
        hass.states.get("binary_sensor.eco_controller_warm_weather_shutdown").state
        == "off"
    )
    assert (
        hass.states.get("binary_sensor.eco_controller_cold_weather_shutdown").state
        == "off"
    )


# ---------------------------------------------------------------------------
# Defensive None / unexpected-shape guards (direct entity property tests)
# ---------------------------------------------------------------------------

from custom_components.sensorlinx.binary_sensor import (  # noqa: E402
    SensorLinxBackupBinarySensor,
    SensorLinxConnectedSensor,
    SensorLinxDemandActiveSensor,
    SensorLinxPumpBinarySensor,
    SensorLinxReversingValveBinarySensor,
    SensorLinxStageBinarySensor,
    SensorLinxWeatherShutdownBinarySensor,
)


async def test_all_is_on_return_none_when_device_gone(hass, setup_integration):
    """is_on returns None for every entity class when coordinator data is cleared."""
    _, coordinator = setup_integration

    entities = [
        SensorLinxConnectedSensor(coordinator, "bld-1", "ABC123"),
        SensorLinxDemandActiveSensor(coordinator, "bld-1", "ABC123", 0, "Heat"),
        SensorLinxStageBinarySensor(coordinator, "bld-1", "ABC123", 0, "Stage 1"),
        SensorLinxBackupBinarySensor(coordinator, "bld-1", "ABC123"),
        SensorLinxPumpBinarySensor(coordinator, "bld-1", "ABC123", 0, "Pump"),
        SensorLinxReversingValveBinarySensor(coordinator, "bld-1", "ABC123"),
        SensorLinxWeatherShutdownBinarySensor(
            coordinator, "bld-1", "ABC123", "wwsd", "WWSD"
        ),
    ]
    coordinator.data.clear()

    for entity in entities:
        assert entity.is_on is None, f"{type(entity).__name__}.is_on should be None"


async def test_stage_and_backup_extra_state_attributes_empty_when_device_gone(
    hass, setup_integration
):
    """extra_state_attributes returns {} when coordinator data is gone."""
    _, coordinator = setup_integration
    stage = SensorLinxStageBinarySensor(coordinator, "bld-1", "ABC123", 0, "Stage 1")
    backup = SensorLinxBackupBinarySensor(coordinator, "bld-1", "ABC123")

    coordinator.data.clear()

    assert stage.extra_state_attributes == {}
    assert backup.extra_state_attributes == {}


def _replace_device(coordinator, **overrides):
    """Return a fresh device dict with overridden fields, without mutating FAKE_DEVICES."""
    original = coordinator.data["bld-1"]["devices"]["ABC123"]["device"]
    fresh = {**original, **overrides}
    coordinator.data["bld-1"]["devices"]["ABC123"]["device"] = fresh
    return fresh


async def test_demand_is_on_returns_none_for_non_dict_item(hass, setup_integration):
    """is_on returns None when a demand entry is not a dict."""
    _, coordinator = setup_integration
    entity = SensorLinxDemandActiveSensor(coordinator, "bld-1", "ABC123", 0, "Heat")
    _replace_device(coordinator, demands=["not_a_dict"])
    assert entity.is_on is None


async def test_stage_is_on_returns_none_for_non_dict_item(hass, setup_integration):
    """is_on returns None when a stage entry is not a dict."""
    _, coordinator = setup_integration
    entity = SensorLinxStageBinarySensor(coordinator, "bld-1", "ABC123", 0, "Stage 1")
    _replace_device(coordinator, stages=["not_a_dict"])
    assert entity.is_on is None


async def test_stage_extra_state_attributes_empty_for_non_dict_item(
    hass, setup_integration
):
    """extra_state_attributes returns {} when the stage entry is not a dict."""
    _, coordinator = setup_integration
    entity = SensorLinxStageBinarySensor(coordinator, "bld-1", "ABC123", 0, "Stage 1")
    _replace_device(coordinator, stages=["not_a_dict"])
    assert entity.extra_state_attributes == {}


async def test_backup_is_on_returns_none_for_non_dict(hass, setup_integration):
    """is_on returns None when the backup field is not a dict."""
    _, coordinator = setup_integration
    entity = SensorLinxBackupBinarySensor(coordinator, "bld-1", "ABC123")
    _replace_device(coordinator, backup="not_a_dict")
    assert entity.is_on is None


async def test_pump_is_on_returns_none_for_non_dict_item(hass, setup_integration):
    """is_on returns None when a pump entry is not a dict."""
    _, coordinator = setup_integration
    entity = SensorLinxPumpBinarySensor(coordinator, "bld-1", "ABC123", 0, "Pump")
    _replace_device(coordinator, pumps=["not_a_dict"])
    assert entity.is_on is None


async def test_reversing_valve_is_on_returns_none_for_non_dict(hass, setup_integration):
    """is_on returns None when reversingValve is not a dict."""
    _, coordinator = setup_integration
    entity = SensorLinxReversingValveBinarySensor(coordinator, "bld-1", "ABC123")
    _replace_device(coordinator, reversingValve="not_a_dict")
    assert entity.is_on is None


async def test_wsd_is_on_returns_none_for_non_dict_entry(hass, setup_integration):
    """is_on returns None when a WSD entry is not a dict."""
    _, coordinator = setup_integration
    entity = SensorLinxWeatherShutdownBinarySensor(
        coordinator, "bld-1", "ABC123", "wwsd", "WWSD"
    )
    wsd = {**coordinator.data["bld-1"]["devices"]["ABC123"]["device"]["wsd"]}
    wsd["wwsd"] = "not_a_dict"
    _replace_device(coordinator, wsd=wsd)
    assert entity.is_on is None


async def test_wsd_sensor_activates(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [
        {
            **FAKE_DEVICES[0],
            "wsd": {
                "wwsd": {"title": "Warm Weather Shutdown", "activated": True},
                "cwsd": {"title": "Cold Weather Shutdown", "activated": False},
            },
        }
    ]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.eco_controller_warm_weather_shutdown").state
        == "on"
    )
    assert (
        hass.states.get("binary_sensor.eco_controller_cold_weather_shutdown").state
        == "off"
    )


async def test_wsd_sensors_not_created_when_absent(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """No WSD entities when device has no wsd key."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from .conftest import CONF_DATA

    _, client = mock_sensorlinx
    device = {**FAKE_DEVICES[0]}
    device.pop("wsd", None)
    client.get_devices.return_value = [device]

    entry = MockConfigEntry(domain="sensorlinx", data=CONF_DATA, entry_id="test4")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.eco_controller_warm_weather_shutdown") is None
    assert hass.states.get("binary_sensor.eco_controller_cold_weather_shutdown") is None


# ---------------------------------------------------------------------------
# DHW enabled
# ---------------------------------------------------------------------------


async def test_dhw_enabled_sensor_on(hass, setup_integration):
    """DHW enabled sensor reflects dhwOn=True as on."""
    state = hass.states.get("binary_sensor.eco_controller_dhw_enabled")
    assert state is not None
    assert state.state == "on"


async def test_dhw_enabled_sensor_off(hass, setup_integration, mock_sensorlinx):
    """DHW enabled sensor reflects dhwOn=False as off."""
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "dhwOn": False}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.eco_controller_dhw_enabled").state == "off"


async def test_dhw_enabled_not_created_when_absent(
    hass, mock_sensorlinx, enable_custom_integrations
):
    """No DHW enabled entity when device has no dhwOn key."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from .conftest import CONF_DATA

    _, client = mock_sensorlinx
    device = {**FAKE_DEVICES[0]}
    device.pop("dhwOn", None)
    client.get_devices.return_value = [device]

    entry = MockConfigEntry(domain="sensorlinx", data=CONF_DATA, entry_id="test_dhw")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.eco_controller_dhw_enabled") is None
