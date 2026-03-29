# Contributing to ha-sensorlinx

## Development setup

```bash
git clone https://github.com/knobunc/ha-sensorlinx
cd ha-sensorlinx
pip install -r requirements_test.txt
pre-commit install   # optional but recommended
```

## Running the test suite

```bash
pytest -q                        # all tests with coverage summary
pytest -q tests/test_sensor.py   # single file
```

Tests run against a real in-memory Home Assistant instance. No SensorLinx account
or network access is required — `pysensorlinx` is fully mocked.

## Linting and formatting

```bash
ruff check .          # lint
ruff format .         # auto-format (Black-compatible)
mypy custom_components/sensorlinx   # type checking
```

All three run automatically in CI. With `pre-commit install`, ruff runs on every
`git commit` so issues are caught locally first.

## Making changes

### Adding a new entity

1. Add the entity class to `sensor.py` or `binary_sensor.py`
2. Add a `_needs(uid)` check and `async_add_entities` call in the platform's
   `_async_add_*` callback
3. Add the unique ID pattern to the table in `AGENTS.md`
4. If the entity has a static name: add `_attr_translation_key`, then add the
   string to both `strings.json` and `translations/en.json`
5. Add tests in the appropriate `tests/test_*.py` file

### Adding a new service

1. Add handler and schema in `services.py`
2. Register in `async_register_services` and unregister in `async_unregister_services`
3. Add field selectors to `services.yaml`
4. Add name, description, and field strings to `strings.json` → `services`, and
   mirror to `translations/en.json`
5. Add happy-path tests in `tests/test_integration.py` and error-path tests in
   `tests/test_edge_cases.py`

## Changelog and versioning

Every meaningful change must be recorded in `CHANGELOG.md` under `[Unreleased]`
before the session ends. When bumping the version:

1. Rename `[Unreleased]` → `[X.Y.Z] - YYYY-MM-DD` in `CHANGELOG.md`
2. Update `"version"` in `custom_components/sensorlinx/manifest.json` to match
3. Commit both files together: `git add manifest.json CHANGELOG.md && git commit -m "Release vX.Y.Z"`

## Key conventions

- **Temperatures** — `pysensorlinx` always returns °F. Use `FAHRENHEIT` as
  `native_unit_of_measurement`; HA handles display conversion automatically.
  Extra attributes that expose temperatures (e.g. `target_temperature`) must be
  manually converted via `TemperatureConverter`.
- **Entity names** — static names use `_attr_translation_key` (not `_attr_name`).
  Numbered entities (e.g. Relay N) use `_attr_translation_placeholders`.
- **Service device IDs** — services accept HA device registry UUIDs, not
  `sync_code`. Use `_sync_code_from_device_id()` in `services.py` to resolve.
- **Import ordering** — ruff enforces isort. Run `ruff check --fix .` to sort
  imports automatically.
