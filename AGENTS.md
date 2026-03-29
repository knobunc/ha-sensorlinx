# Agent Guide — ha-sensorlinx

## Running tests

```bash
pytest -q          # all tests
pytest -q tests/test_sensor.py   # single file
```

Tests run in-process with a real (in-memory) Home Assistant instance.
No network access or SensorLinx account required — `pysensorlinx` is fully mocked.

Install test dependencies once:
```bash
pip install -r requirements_test.txt
```

## Project layout

```
custom_components/sensorlinx/
  __init__.py        # entry setup/teardown, stale cleanup, async_remove_config_entry_device
  coordinator.py     # DataUpdateCoordinator — polls buildings + devices, handles re-auth
  entity.py          # SensorLinxBaseEntity (base class, device_info, availability)
  sensor.py          # Demand (%) + temperature channel sensors
  binary_sensor.py   # Connected, demand, stages, backup, pumps, valve, relays, WSD
  config_flow.py     # User + reauth + options flows
  services.py        # set_hvac_mode_priority, set_permanent_demand
  diagnostics.py     # async_get_config_entry_diagnostics
  const.py           # domain, defaults, config key names
  strings.json       # UI strings + entity/service translations (source of truth)
  translations/en.json  # mirrors strings.json exactly
  services.yaml      # field selectors only (names/descriptions live in strings.json)
  images/
    icon.png         # HACS integration icon (256x256, mdi:thermostat in #41BDF5)
tests/
  conftest.py        # FAKE_BUILDINGS, FAKE_DEVICES, fixtures, ha_device_id() helper
  test_coordinator.py
  test_sensor.py
  test_binary_sensor.py
  test_config_flow.py
  test_integration.py
  test_unload.py
  test_diagnostics.py
  test_edge_cases.py
```

## Coordinator data shape

```python
coordinator.data = {
    "<building_id>": {
        "building": {"id": "...", "name": "..."},
        "devices": {
            "<sync_code>": {"device": { ...raw API dict... }},
        },
    }
}
```

## Entity unique ID conventions

| Entity | Unique ID pattern |
|--------|-------------------|
| Demand sensor | `{sync_code}_demand` |
| Temperature sensor | `{sync_code}_temp_{index}` |
| Connected | `{sync_code}_connected` |
| Demand channel | `{sync_code}_demand_{index}` |
| Stage | `{sync_code}_stage_{index}` |
| Backup heat | `{sync_code}_backup` |
| Pump | `{sync_code}_pump_{index}` |
| Reversing valve | `{sync_code}_reversing_valve` |
| Relay | `{sync_code}_relay_{index}` |
| Weather shutdown | `{sync_code}_wsd_{wsd_key}` |

## Key constraints

- **pysensorlinx always returns temperatures in °F.** `native_unit_of_measurement` is
  always `FAHRENHEIT`. HA auto-converts to the user's display unit. `extra_state_attributes`
  that expose temperatures (e.g. `target_temperature`) must be manually converted via
  `TemperatureConverter` using `hass.config.units.temperature_unit`.

- **Static entity names use `_attr_translation_key`**, not `_attr_name`. Translation
  strings live in `strings.json` → `entity.*`. Numbered entities (e.g. relays) use
  `_attr_translation_placeholders = {"index": str(n)}` with `"name": "Relay {index}"`
  in strings.json. Dynamic names from API `title` fields still use
  `self._attr_name = title` in `__init__`.

- **Service fields use `device_id`** (HA device registry UUID), not `sync_code`. The
  `_sync_code_from_device_id()` helper in `services.py` resolves the UUID back to a
  sync code via `device_entry.identifiers`.

- **`conftest.py` (root) pre-imports `custom_components.sensorlinx`** before tests
  run. This is required because `custom_components` is a namespace package — without
  an explicit import, `mock.patch("custom_components.sensorlinx.X")` raises
  `AttributeError` when resolving the path.

- **Live device discovery** uses `ent_reg.async_get_entity_id()` (not a local set) so
  that devices removed by stale cleanup and later re-appearing are correctly re-added.

## Versioning and changelog discipline

**Every meaningful change must be recorded in `CHANGELOG.md` before the session ends.**
Add entries to the `[Unreleased]` section (create it if absent) under `Added`, `Changed`,
or `Fixed` as appropriate. When bumping the version:

1. Rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD` in `CHANGELOG.md`
2. Update `"version"` in `custom_components/sensorlinx/manifest.json` to match
3. Commit **both files together**:
   ```
   git add custom_components/sensorlinx/manifest.json CHANGELOG.md
   git commit -m "Release vX.Y.Z"
   ```

Do not bump the version without a CHANGELOG entry, and do not add CHANGELOG entries
without checking whether the version should also be bumped.

## Adding a new entity type

1. Add entity class to `sensor.py` or `binary_sensor.py`
2. Add `_needs(uid)` check and `async_add_entities` call in the platform's
   `_async_add_*` callback
3. Add unique ID entry to the table above
4. If the entity has a static name: add a `_attr_translation_key`, add the
   corresponding entry to `strings.json` and `translations/en.json`
5. Add tests in the appropriate `tests/test_*.py` file

## Adding a new service

1. Add handler and schema in `services.py`
2. Register in `async_register_services` and unregister in `async_unregister_services`
3. Add field selectors to `services.yaml`
4. Add name, description, and field strings to `strings.json` → `services` and mirror
   to `translations/en.json`
5. Add tests in `tests/test_integration.py` (happy path) and `tests/test_edge_cases.py`
   (error paths)
