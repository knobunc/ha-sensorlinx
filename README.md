# ha-sensorlinx

[![CI](https://github.com/knobunc/ha-sensorlinx/actions/workflows/ci.yml/badge.svg)](https://github.com/knobunc/ha-sensorlinx/actions/workflows/ci.yml)

A [Home Assistant](https://www.home-assistant.io/) custom integration for the [HBX SensorLinx](https://mobile.sensorlinx.co) building automation platform.

Uses the [pysensorlinx](https://pypi.org/project/pysensorlinx/) Python library to poll device data from the SensorLinx cloud API.

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Features

- Automatic discovery of all buildings and devices linked to your account
- **Sensor entities** for each device:
  - Overall system demand (%)
  - Temperature channels (supply, return, outdoor, etc.) with target and operational state
  - HVAC priority, config temperatures, and differentials (diagnostic)
- **Binary sensor entities** for each device:
  - Cloud connectivity status
  - Demand channels (heat active, cool active, etc.)
  - Heat pump stages (enabled stages only), with `run_time` attribute
  - Backup heat, with `run_time` attribute
  - Supply and load pumps
  - Reversing valve
  - Warm and cold weather shutdown
- **Switch entities** for each device:
  - DHW enabled, permanent heat demand, permanent cool demand
  - Warm/cold weather shutdown and hot/cold outdoor reset toggles
- **Number entities** for each device:
  - DHW target temperature and differential
  - Hot tank min/max temperatures, heat differential, WWSD and outdoor reset temperatures
  - Cold tank min/max temperatures, cold differential, CWSD and cold outdoor reset temperatures
- **Select entities** for each device:
  - Demand priority (heat / cool / auto)
- **Weather entity** per building:
  - Current conditions (temperature, humidity, pressure, wind, cloud coverage)
  - Hourly forecast
- **8 service calls** for writing device parameters
- Configurable poll interval (30–3600 seconds, default 60)
- Automatic re-authentication on session expiry
- Diagnostics support (Settings → Devices & Services → SensorLinx → Download diagnostics)

## Installation

### Via HACS (recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations** → **Custom repositories**
3. Add `https://github.com/knobunc/ha-sensorlinx` with category **Integration**
4. Search for "SensorLinx" and install it
5. Restart Home Assistant

### Manual

Copy the `custom_components/sensorlinx` directory into your Home Assistant config:

```
<config>/custom_components/sensorlinx/
```

Restart Home Assistant.

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **HBX SensorLinx**
3. Enter your SensorLinx account email and password

All buildings and devices associated with your account will be discovered automatically.

### Options

After setup, you can adjust the following via **Settings** → **Devices & Services** → **SensorLinx** → **Configure**:

| Option | Default | Range | Description |
|--------|---------|-------|-------------|
| Polling interval | 60 s | 30–3600 s | How often to fetch device data from the SensorLinx cloud |
| API timeout | 30 s | 10–120 s | How long to wait for an API response before treating it as a failure |

## Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `{device} Demand` | Overall system demand (%) |
| `{device} {channel}` | Temperature per enabled channel |
| `{device} {channel} Target` | Target (setpoint) temperature per channel |
| `{device} {channel} State` | Operational state (Heat, Cool, Satisfied, Off) |
| `{device} HVAC Priority` | Current priority mode (diagnostic) |
| `{device} WWSD Temperature` | Warm weather shutdown setpoint (diagnostic) |
| `{device} Outdoor Reset Temperature` | Hot outdoor reset setpoint (diagnostic) |
| `{device} Min/Max Tank Temperature` | Hot tank min/max setpoints (diagnostic) |
| `{device} Heat Differential` | Hot tank differential (diagnostic) |
| `{device} DHW Target Temperature` | DHW setpoint (diagnostic) |
| `{device} DHW Differential` | DHW differential (diagnostic) |
| `{device} CWSD Temperature` | Cold weather shutdown setpoint (diagnostic) |
| `{device} Cold Outdoor Reset Temperature` | Cold outdoor reset setpoint (diagnostic) |
| `{device} Cold Min/Max Tank Temperature` | Cold tank min/max setpoints (diagnostic) |
| `{device} Cold Differential` | Cold tank differential (diagnostic) |

Temperature sensors report in your Home Assistant unit system and include `target_temperature` and `operation` (e.g. `Heat`, `Idle`) as extra state attributes when available.

### Binary sensors

| Entity | Description |
|--------|-------------|
| `{device} Connected` | Cloud connectivity (diagnostic) |
| `{device} {demand} Demand` | Demand channel active (e.g. Heat Demand, Cool Demand) |
| `{device} Stage N` | Heat pump stage active (enabled stages only; `run_time` attribute) |
| `{device} Backup Heat` | Backup heat active (`run_time` attribute) |
| `{device} {pump}` | Pump running (Supply Pump, Load Pump) |
| `{device} Reversing Valve` | Reversing valve open (diagnostic) |
| `{device} Warm/Cold Weather Shutdown` | WWSD/CWSD active |

### Switches (config)

| Entity | Description |
|--------|-------------|
| `{device} DHW Enabled` | Toggle domestic hot water demand |
| `{device} Permanent Heat Demand` | Always maintain hot tank target temperature |
| `{device} Permanent Cool Demand` | Always maintain cold tank target temperature |
| `{device} Warm Weather Shutdown` | Enable/disable WWSD |
| `{device} Hot Outdoor Reset` | Enable/disable hot outdoor reset |
| `{device} Cold Weather Shutdown` | Enable/disable CWSD |
| `{device} Cold Outdoor Reset` | Enable/disable cold outdoor reset |

### Numbers (config)

| Entity | Description |
|--------|-------------|
| `{device} DHW Target Temperature` | DHW tank setpoint |
| `{device} DHW Differential` | DHW differential |
| `{device} Min/Max Tank Temperature` | Hot tank min/max setpoints |
| `{device} Heat Differential` | Hot tank differential |
| `{device} WWSD Temperature` | Warm weather shutdown threshold |
| `{device} Outdoor Reset Temperature` | Hot outdoor reset design temperature |
| `{device} Cold Min/Max Tank Temperature` | Cold tank min/max setpoints |
| `{device} Cold Differential` | Cold tank differential |
| `{device} CWSD Temperature` | Cold weather shutdown threshold |
| `{device} Cold Outdoor Reset Temperature` | Cold outdoor reset design temperature |

Temperature numbers auto-convert between °F and °C. Differential numbers are always in °F.

### Selects (config)

| Entity | Description |
|--------|-------------|
| `{device} Demand Priority` | HVAC mode priority (Heat / Cool / Auto) |

### Weather

| Entity | Description |
|--------|-------------|
| `{building} Weather` | Current conditions and hourly forecast |

## Services

The integration registers eight services for controlling SensorLinx devices. All use the **HA device registry ID** to identify the target device — easiest to supply via the service call UI, which shows a device picker filtered to SensorLinx devices.

> **Note:** Most parameters also have corresponding switch, number, or select entities that provide direct UI controls. Services are useful for automations or for setting multiple parameters atomically.

> **Tip:** All services log a warning (but still proceed) if the target device reports `connected: false`. The API call may fail silently on the device side in that case.

### `sensorlinx.set_hvac_mode_priority`

Set the HVAC mode priority for a device.

| Field | Required | Values |
|-------|----------|--------|
| `device_id` | Yes | HA device ID |
| `mode` | Yes | `heat` / `cool` / `auto` |

### `sensorlinx.set_permanent_demand`

Enable or disable permanent heating and/or cooling demand. At least one of `permanent_hd` or `permanent_cd` must be supplied.

| Field | Required | Values |
|-------|----------|--------|
| `device_id` | Yes | HA device ID |
| `permanent_hd` | No | `true` / `false` |
| `permanent_cd` | No | `true` / `false` |

### `sensorlinx.set_hot_tank_config`

Configure hot tank parameters. At least one optional field must be provided. Temperature values are in °F; use `"off"` to disable WWSD or outdoor reset.

| Field | Required | Values |
|-------|----------|--------|
| `device_id` | Yes | HA device ID |
| `warm_weather_shutdown` | No | °F (34–180) or `"off"` |
| `outdoor_reset` | No | °F (-40–127) or `"off"` |
| `differential` | No | °F (2–100) |
| `min_temp` | No | °F (2–180) |
| `max_temp` | No | °F (2–180) |

### `sensorlinx.set_cold_tank_config`

Configure cold tank parameters. Same structure as hot tank config.

| Field | Required | Values |
|-------|----------|--------|
| `device_id` | Yes | HA device ID |
| `cold_weather_shutdown` | No | °F (33–119) or `"off"` |
| `outdoor_reset` | No | °F (0–119) or `"off"` |
| `differential` | No | °F (2–100) |
| `min_temp` | No | °F (2–180) |
| `max_temp` | No | °F (2–180) |

### `sensorlinx.set_dhw_config`

Configure domestic hot water parameters.

| Field | Required | Values |
|-------|----------|--------|
| `device_id` | Yes | HA device ID |
| `enabled` | No | `true` / `false` |
| `target_temp` | No | °F (33–180) |
| `differential` | No | °F (2–100) |

### `sensorlinx.set_backup_config`

Configure backup heater parameters.

| Field | Required | Values |
|-------|----------|--------|
| `device_id` | Yes | HA device ID |
| `lag_time` | No | minutes (1–240) or `"off"` |
| `temp` | No | °F (2–100) or `"off"` |
| `differential` | No | °F (2–100) or `"off"` |
| `only_outdoor_temp` | No | °F (-40–127) or `"off"` |
| `only_tank_temp` | No | °F (33–200) or `"off"` |

### `sensorlinx.set_staging_config`

Configure heat pump staging parameters.

| Field | Required | Values |
|-------|----------|--------|
| `device_id` | Yes | HA device ID |
| `number_of_stages` | No | 1–4 |
| `two_stage` | No | `true` / `false` |
| `stage_on_lag_time` | No | minutes (1–240) |
| `stage_off_lag_time` | No | seconds (1–240) |
| `rotate_cycles` | No | cycles (1–240) or `"off"` |
| `rotate_time` | No | hours (1–240) or `"off"` |
| `off_staging` | No | `true` / `false` |

### `sensorlinx.set_system_config`

Configure general system parameters.

| Field | Required | Values |
|-------|----------|--------|
| `device_id` | Yes | HA device ID |
| `weather_shutdown_lag_time` | No | hours (0–240) |
| `heat_cool_switch_delay` | No | seconds (30–600) |
| `wide_priority_differential` | No | `true` / `false` |

### YAML example

```yaml
service: sensorlinx.set_hvac_mode_priority
data:
  device_id: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
  mode: heat
```

Find the device registry ID under **Settings → Devices & Services → SensorLinx → (your device) → URL** — it is the hex string at the end of the URL.

## Device Types

The integration works with all SensorLinx device types: BTU, CPU, ECO, FLO, FLW, PRE, PRS, SGL, SNO, SUN, THM, ZON, ENG.

## Upgrading

### From v0.2.x or v0.3.x

The services `sensorlinx.set_hvac_mode_priority` and `sensorlinx.set_permanent_demand` previously accepted a `sync_code` field (a raw device identifier string). As of v0.3.0 this was replaced with `device_id` (the HA device registry UUID). **Any YAML automations using the old `sync_code` field must be updated.**

Replace:
```yaml
service: sensorlinx.set_hvac_mode_priority
data:
  sync_code: "ABC123"
  mode: heat
```

With:
```yaml
service: sensorlinx.set_hvac_mode_priority
data:
  device_id: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
  mode: heat
```

Find the device registry ID under **Settings → Devices & Services → SensorLinx → (your device) → URL** — it is the hex string at the end of the URL.

### From v0.1.x

- Unique IDs for all entities have changed to be based on device sync codes rather than config entry IDs. This makes them portable across reinstalls, but HA will treat them as new entities on first upgrade. You may need to re-assign any entity customizations or dashboard cards.

## Requirements

- Home Assistant 2024.1 or later
- A SensorLinx account with at least one building configured
- [pysensorlinx](https://pypi.org/project/pysensorlinx/) (installed automatically by HA)

## Development

### Setup

```bash
git clone https://github.com/knobunc/ha-sensorlinx
cd ha-sensorlinx
pip install -r requirements_test.txt
```

### Running tests

```bash
pytest -q
```

The test suite uses `pytest-homeassistant-custom-component` to run a real (in-memory) Home Assistant instance. `pysensorlinx` is mocked throughout — no SensorLinx account or network access is required.

### Test structure

| File | What it covers |
|------|----------------|
| `tests/conftest.py` | Shared fixtures and helpers: fake API data, mocked `Sensorlinx` client, `setup_integration`, `ha_device_id` |
| `tests/test_coordinator.py` | Data fetching, building/device hierarchy, auth retry, timeout, error handling |
| `tests/test_sensor.py` | Demand, temperature, target, state, priority, and config sensors |
| `tests/test_binary_sensor.py` | All binary sensor types: connected, demand, stages, backup, pumps, reversing valve, weather shutdown |
| `tests/test_switch.py` | DHW, sentinel (WWSD, outdoor reset, CWSD, cold outdoor reset), and permanent demand switches |
| `tests/test_number.py` | All 12 number entities: values, unit conversion, sentinels, set_value |
| `tests/test_select.py` | Priority select: read state, select_option, absent key |
| `tests/test_config_flow.py` | Config flow (auth errors, timeout, duplicate prevention), options flow, reauth form |
| `tests/test_integration.py` | Full stack: entity/device registry, availability, stale cleanup, live discovery, multi-entry, re-auth, services |
| `tests/test_unload.py` | Entry lifecycle: unload, client close, service registration/deregistration |
| `tests/test_diagnostics.py` | Diagnostics output, password redaction, poll settings |
| `tests/test_weather.py` | Weather entity: current conditions, hourly forecast, condition mapping |
| `tests/test_edge_cases.py` | Options boundaries, service API errors, auth retry, duplicate sync codes, migration |

### Adding a test

Most tests follow this pattern:

```python
async def test_something(hass, setup_integration, mock_sensorlinx):
    _, client = mock_sensorlinx
    entry, coordinator = setup_integration

    # Update what the mock API returns
    client.get_devices.return_value = [{...}]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.my_device_demand")
    assert state.state == "75"
```

## Disclaimer

This integration is not affiliated with or endorsed by HBX Controls. It uses a reverse-engineered API. Use at your own risk.

## License

[MIT](LICENSE)
