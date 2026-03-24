# ha-sensorlinx

A [Home Assistant](https://www.home-assistant.io/) custom integration for the [HBX SensorLinx](https://mobile.sensorlinx.co) building automation platform.

Uses the [sensorlinx](https://github.com/knobunc/sensorlinx) Python library to poll device data from the SensorLinx cloud API.

## Features

- Automatic discovery of all buildings and devices linked to your account
- **Sensor entities** for each device:
  - Overall system demand (%)
  - Temperature channels (supply, return, outdoor, etc.)
- **Binary sensor entities** for each device:
  - Cloud connectivity status
  - Demand channels (heat active, cool active, etc.)
- Polls every 60 seconds
- Automatic token re-authentication on expiry

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

## Entities

For each device, the integration creates:

| Entity | Type | Description |
|--------|------|-------------|
| `{device} Demand` | Sensor | Overall system demand, % |
| `{device} {channel}` | Sensor | Temperature per channel (°F) |
| `{device} Connected` | Binary Sensor | Cloud connectivity |
| `{device} {demand}` | Binary Sensor | Demand channel active (e.g. Heat, Cool) |

Temperature sensors include `target_temperature` and `state` (active/idle) as extra attributes.

## Device Types

The integration works with all SensorLinx device types: BTU, CPU, ECO, FLO, FLW, PRE, PRS, SGL, SNO, SUN, THM, ZON, ENG.

## Requirements

- Home Assistant 2024.1 or later
- A SensorLinx account with at least one building configured
- The [sensorlinx](https://github.com/knobunc/sensorlinx) library (installed automatically)

## Disclaimer

This integration is not affiliated with or endorsed by HBX Controls. It uses a reverse-engineered API. Use at your own risk.

## License

[MIT](LICENSE)
