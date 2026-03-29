# ha-sensorlinx

[![CI](https://github.com/knobunc/ha-sensorlinx/actions/workflows/ci.yml/badge.svg)](https://github.com/knobunc/ha-sensorlinx/actions/workflows/ci.yml)

A [Home Assistant](https://www.home-assistant.io/) custom integration for the [HBX SensorLinx](https://mobile.sensorlinx.co) building automation platform.

Uses the [pysensorlinx](https://pypi.org/project/pysensorlinx/) Python library to poll device data from the SensorLinx cloud API.

See [CHANGELOG.md](CHANGELOG.md) for release history.

## Features

- Automatic discovery of all buildings and devices linked to your account
- **Sensor entities** for each device:
  - Overall system demand (%)
  - Temperature channels (supply, return, outdoor, etc.)
- **Binary sensor entities** for each device:
  - Cloud connectivity status
  - Demand channels (heat active, cool active, etc.)
  - Heat pump stages (enabled stages only), with `run_time` attribute
  - Backup heat, with `run_time` attribute
  - Supply and load pumps
  - Reversing valve
  - Relays (one per relay output)
  - Warm and cold weather shutdown
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

For each device, the integration creates:

| Entity | Type | Description |
|--------|------|-------------|
| `{device} Demand` | Sensor | Overall system demand (%) |
| `{device} {channel}` | Sensor | Temperature per enabled channel |
| `{device} Connected` | Binary Sensor | Cloud connectivity |
| `{device} {demand}` | Binary Sensor | Demand channel active (e.g. Heat, Cool) |
| `{device} Stage N` | Binary Sensor | Heat pump stage active (enabled stages only) |
| `{device} Backup Heat` | Binary Sensor | Backup heat active (when enabled) |
| `{device} Supply Pump` | Binary Sensor | Supply pump running |
| `{device} Load Pump` | Binary Sensor | Load pump running |
| `{device} Reversing Valve` | Binary Sensor | Reversing valve open (when present) |
| `{device} Relay N` | Binary Sensor | Relay output state |
| `{device} Warm Weather Shutdown` | Binary Sensor | WWSD active |
| `{device} Cold Weather Shutdown` | Binary Sensor | CWSD active |

Temperature sensors report in your Home Assistant unit system and include `target_temperature` and `state` (e.g. `heating`, `idle`) as extra state attributes when available.

Stage and backup heat sensors include a `run_time` attribute (e.g. `"2h 15m"`).

## Services

The integration registers two services for controlling SensorLinx devices. Both use the **HA device registry ID** to identify the target device — this is easiest to supply via the service call UI, which shows a device picker filtered to SensorLinx devices.

### `sensorlinx.set_hvac_mode_priority`

Set the HVAC mode priority for a device.

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `device_id` | Yes | HA device ID | The SensorLinx device to control |
| `mode` | Yes | `heat` / `cool` / `auto` | HVAC mode the controller should prioritise |

**Via the UI (recommended):** Go to **Developer Tools → Services**, pick `sensorlinx.set_hvac_mode_priority`, and use the device picker to select your device.

**Via YAML automation:** You need the device's HA device registry ID. Find it under **Settings → Devices & Services → SensorLinx → (your device) → URL** — it is the hex string at the end of the URL.

```yaml
service: sensorlinx.set_hvac_mode_priority
data:
  device_id: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
  mode: heat
```

### `sensorlinx.set_permanent_demand`

Enable or disable permanent heating and/or cooling demand. When permanent demand is on, the device always maintains the buffer tank target temperature regardless of external zone demand signals.

| Field | Required | Values | Description |
|-------|----------|--------|-------------|
| `device_id` | Yes | HA device ID | The SensorLinx device to control |
| `permanent_hd` | No | `true` / `false` | Always maintain hot tank target temperature |
| `permanent_cd` | No | `true` / `false` | Always maintain cold tank target temperature |

At least one of `permanent_hd` or `permanent_cd` must be supplied.

```yaml
service: sensorlinx.set_permanent_demand
data:
  device_id: "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
  permanent_hd: true
  permanent_cd: false
```

> **Note:** Both services log a warning (but still proceed) if the target device reports `connected: false`. The API call may fail silently on the device side in that case.

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
| `tests/test_sensor.py` | Demand and temperature sensor states, unit conversion, updates, device info |
| `tests/test_binary_sensor.py` | All binary sensor types: connected, demand, stages, backup, pumps, reversing valve, relays, weather shutdown |
| `tests/test_config_flow.py` | Config flow (auth errors, timeout, duplicate prevention), options flow, reauth form |
| `tests/test_integration.py` | Full stack: entity/device registry, availability, stale cleanup, live discovery, multi-entry, re-auth, services |
| `tests/test_unload.py` | Entry lifecycle: unload, client close, service registration/deregistration |
| `tests/test_diagnostics.py` | Diagnostics output, password redaction, poll settings |
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
