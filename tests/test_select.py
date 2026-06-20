"""Tests for SensorLinx select entities."""

from homeassistant.const import EntityCategory
from homeassistant.helpers import entity_registry as er

from custom_components.sensorlinx.select import SensorLinxPrioritySelect

from .conftest import CONF_DATA, FAKE_DEVICES


async def test_priority_select_created(hass, setup_integration):
    state = hass.states.get("select.eco_controller_demand_priority")
    assert state is not None


async def test_priority_select_reads_heat(hass, setup_integration):
    """prior=0 → heat."""
    state = hass.states.get("select.eco_controller_demand_priority")
    assert state.state == "heat"


async def test_priority_select_reads_cool(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "prior": 1}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("select.eco_controller_demand_priority").state == "cool"


async def test_priority_select_reads_auto(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    _, coordinator = setup_integration

    client.get_devices.return_value = [{**FAKE_DEVICES[0], "prior": 2}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("select.eco_controller_demand_priority").state == "auto"


async def test_priority_select_option(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.eco_controller_demand_priority", "option": "cool"},
        blocking=True,
    )

    client.set_device_parameter.assert_awaited_once()
    kw = client.set_device_parameter.call_args.kwargs
    assert kw["hvac_mode_priority"] == "cool"


async def test_priority_select_entity_category(hass, setup_integration):
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("select.eco_controller_demand_priority")
    assert entry is not None
    assert entry.entity_category == EntityCategory.CONFIG


async def test_priority_select_device_gone(hass, setup_integration):
    _, coordinator = setup_integration

    entity = SensorLinxPrioritySelect(coordinator, "bld-1", "ABC123")
    coordinator.data.clear()

    assert entity.current_option is None


async def test_priority_select_not_created_when_absent(
    hass, mock_sensorlinx, enable_custom_integrations
):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    _, client = mock_sensorlinx
    device = {**FAKE_DEVICES[0]}
    device.pop("prior", None)
    client.get_devices.return_value = [device]

    entry = MockConfigEntry(
        domain="sensorlinx", data=CONF_DATA, entry_id="test_select_absent"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("select.eco_controller_demand_priority") is None
