# Changelog

All notable changes to this project will be documented in this file.

## [0.9.1] - 2026-04-28

### Fixed
- **Debug logging via UI** — added `loggers` entry to `manifest.json` so the HA "Enable debug logging" button targets the correct Python logger (`custom_components.sensorlinx`).

## [0.9.0] - 2026-04-28

### Added
- **Activated state sensor** — new `SensorLinxActivatedStateSensor` exposes the `activatedState` field from temperature channels (e.g. "heating", "cooling", "satisfied") as a text sensor. Unique ID: `{sync_code}_temp_state_{index}`.

### Changed
- **Diagnostic entity category** — HVAC priority, all config temperature sensors (WWSD, outdoor reset, min/max tank, DHW target, CWSD, cold outdoor reset, cold min/max tank), all config delta sensors (heat differential, DHW differential, cold differential), and DHW enabled binary sensor are now `EntityCategory.DIAGNOSTIC`, placing them in the Diagnostic section of the device card.
- **Demand sensor names** — demand binary sensors renamed from "Heat", "Cool", "DHW" to "Heat Demand", "Cool Demand", "DHW Demand" for clarity.
- **Demand sensor device class** — removed `BinarySensorDeviceClass.RUNNING` from demand sensors since they represent a call for demand, not equipment running.

## [0.7.0] - 2026-04-27

### Added
- **Weather platform** — building-level `WeatherEntity` exposing current conditions (temperature, humidity, pressure, wind, cloud coverage) and hourly forecast from the SensorLinx API. OWM condition IDs mapped to HA condition strings. Unique ID: `{building_id}_weather`.
- **DHW sensors** — `SensorLinxDHWEnabledSensor` binary sensor (`dhwOn`) and `dhw_target_temp` config temperature sensor (`dhwT`).
- **Cold tank config sensors** — five new sensors for cold-side configuration: `cwsd_temp` (sentinel 32 = off), `cold_outdoor_reset` (sentinel -41 = off), `cold_min_tank_temp`, `cold_max_tank_temp`, `cold_differential`.
- **6 new services** — `set_hot_tank_config`, `set_cold_tank_config`, `set_dhw_config`, `set_backup_config`, `set_staging_config`, `set_system_config`. Services group related device parameter setters; temperature fields accept °F values or `"off"` where applicable.
- **Diagnostics** — added `has_weather` (building-level), `dhw_enabled`, and `has_cold_tank` (device-level) to diagnostics output.

### Changed
- **pysensorlinx requirement** bumped from `>=0.1.9` to `>=0.2.3`.

## [0.6.7] - 2026-04-03

### Fixed
- **Ruff formatting** — `sensor.py`, `tests/test_sensor.py`, and `tests/test_unload.py` reformatted to satisfy `ruff format --check` in CI.

## [0.6.6] - 2026-04-03

### Fixed
- **Sensors unavailable after reload** — On integration reload, the entity registry still held entries from the previous setup session. Both sensor platforms were checking the entity registry to avoid duplicate entities; every entity was skipped, leaving HA with registry entries but no backing objects — displayed as unavailable. Platforms now track added UIDs in a per-session set and only fall back to the registry check to handle re-appearance after stale device cleanup.

## [0.6.5] - 2026-03-31

### Added
- **Configuration setting sensors** — Seven new sensor entities expose device configuration values as read-only HA sensors: HVAC Priority (`prior`, enum: heat/cool/auto), WWSD Temperature (`wwsd`, °F; returns unavailable when set to sentinel value 32), Outdoor Reset Temperature (`dot`, °F; returns unavailable when set to sentinel value -41), Min Tank Temperature (`mbt`), Max Tank Temperature (`dbt`), Heat Differential (`htDif`, °F delta), DHW Differential (`auxDif`, °F delta). Temperature sensors auto-convert to the user's preferred unit via HA; delta sensors report raw °F values.

## [0.6.4] - 2026-03-31

### Added
- **Temperature target sensors** — A `SensorLinxTemperatureTargetSensor` entity (unique ID `{sync_code}_temp_target_{index}`) is created for every enabled temperature channel that has a non-null live `target` value (e.g. "Tank Target", "DHW Tank Target"). Values are in native °F and auto-converted by HA to the user's preferred unit.

## [0.6.3] - 2026-03-31

### Removed
- **Relay binary sensors** — `SensorLinxRelayBinarySensor` and all associated translation strings removed. The SensorLinx API exposes relay data in the raw device payload but `pysensorlinx` has no getter for it; relay state is not reliably interpretable without library support.

## [0.6.2] - 2026-03-31

### Fixed
- **CI dependency resolution** — replaced `uv` with plain `pip` in the tests job; `uv`'s strict resolver could not reconcile `pysensorlinx`'s `aiohttp` requirement with the pre-release `homeassistant` pins inside `pytest-homeassistant-custom-component`. Split into two install steps: framework first, then integration deps.
- **`pytest>=8.0` constraint removed** from `requirements_test.txt` — `pytest-homeassistant-custom-component` pins its own pytest version; our constraint caused an unsatisfiable resolution.
- **`mypy` step removed from CI** — `mypy` was dropped from `requirements_test.txt` to avoid conflicts with `phcc`'s pinned `mypy-dev`; the orphaned CI step now removed.

## [0.6.1] - 2026-03-28

### Fixed
- **CI lint job missing `mypy`** — `mypy` was invoked but not installed in the lint job; added to the `pip install` step alongside `ruff`.
- **`manifest.json` key order** — hassfest requires `domain`, `name`, then alphabetical; `issue_tracker` moved before `requirements`.
- **HACS validation errors** — removed disallowed `category` key from `hacs.json`; added `brand/icon.png` at the path HACS expects; set repository description and topics (`home-assistant`, `hacs`, `hacs-integration`, `homeassistant-custom-component`).

## [0.6.0] - 2026-03-28

### Added
- **`pyproject.toml`** — consolidates `pytest`, `ruff`, and `mypy` configuration; `pytest.ini` removed.
- **`pytest-cov` coverage reporting** — `--cov` flag added to test run; coverage summary printed after every `pytest` run and in CI.
- **`ruff format` enforcement** — Black-compatible formatter applied to all source files; `ruff format --check` added to the CI lint job so formatting drift fails CI.
- **`mypy` type checking** — `mypy custom_components/sensorlinx` added to CI lint job; caught and fixed two latent type errors (see Fixed).
- **Dependabot for GitHub Actions** — `.github/dependabot.yml` schedules weekly updates to CI action pins.
- **Pre-commit hooks** — `.pre-commit-config.yaml` runs `ruff` (with `--fix`) and `ruff-format` on every local commit.
- **`CONTRIBUTING.md`** — contributor guide covering setup, test commands, linting, and project conventions.
- **`Final` type annotations on constants** — all entries in `const.py` annotated with `typing.Final`.
- **20 new tests** — targeted coverage tests for login error paths during setup, service edge cases (non-SensorLinx device, missing sync code, API timeout), and all defensive `is_on`/`extra_state_attributes` guard branches in binary sensor entities.

### Changed
- **Import ordering enforced** — `ruff` isort (`I` rule set) added; all import blocks sorted consistently across the codebase.
- **`README.md`** — added link to `CHANGELOG.md` in the introduction.

### Fixed
- **`coordinator.py` type error** — `entry_data` parameter type widened from `dict[str, str]` to `Mapping[str, Any]`; `ConfigEntry.data` is a `MappingProxyType`, not a plain `dict`, causing mypy to reject the call in `async_setup_entry`.
- **`entity.py` type error** — `_get_device()` return type was inferred as `Any` due to untyped nested dict access; a `cast(dict[str, Any], ...)` now satisfies `warn_return_any`.

## [0.5.0] - 2026-03-27

### Added
- **Service strings in `strings.json`** — names and descriptions for `set_hvac_mode_priority` and `set_permanent_demand` are now defined in `strings.json` / `translations/en.json`, enabling community translations. `services.yaml` retains only field selectors.
- **`requirements_test.txt`** — pins `pytest`, `pytest-asyncio`, `pytest-homeassistant-custom-component`, and `pysensorlinx` so contributors can run `pip install -r requirements_test.txt` instead of remembering individual packages.
- **`AGENTS.md` / `CLAUDE.md`** — AI agent guide documenting project layout, coordinator data shape, entity unique ID conventions, key constraints, and step-by-step checklists for adding new entity types and services. `CLAUDE.md` is a symlink to `AGENTS.md`.
- **GitHub Actions CI** — `.github/workflows/ci.yml` runs the test suite on Python 3.12 and 3.13, `hassfest` (HA integration structure validation), and HACS validation on every push and pull request.
- **HACS icon** — `custom_components/sensorlinx/images/icon.png` added using the `mdi:thermostat` icon in HA primary blue (#41BDF5) at 256×256 px.

### Changed
- **`_attr_translation_key` for static entity names** — `Demand`, `Connected`, `Backup Heat`, and `Reversing Valve` entities now use `_attr_translation_key` instead of hardcoded `_attr_name`, following the recommended HA pattern for translatable entity names.
- **`Relay N` uses translation placeholder** — relay entities now use `_attr_translation_key = "relay"` with `_attr_translation_placeholders = {"index": str(n)}` and `"name": "Relay {index}"` in strings.json, making relay names translatable like all other static entity names.
- **`quality_scale: gold`** — bumped from `silver` in `manifest.json`; the integration now meets gold criteria (entity translations, coordinator, config/options/reauth flows, diagnostics, unique IDs, device registry, service descriptions, comprehensive tests).
- **`_warn_if_disconnected` merged into `_find_device`** — the connectivity warning is now issued during the same coordinator scan that locates the device, eliminating a redundant full iteration on every service call.
- **`services.yaml` `required: true` restored** — `device_id` and `mode` fields were inadvertently stripped of `required: true` when service strings were moved to `strings.json`; the HA UI now correctly marks them as required.

### Fixed
- **Client leaked when first coordinator refresh fails** — if `async_config_entry_first_refresh()` raised during setup (e.g. network error on first poll), `client.close()` was never called. The client is now closed before re-raising.

## [0.4.0] - 2026-03-27

### Added
- **`NumberSelector` for options form** — polling interval and API timeout fields now render as proper bounded number inputs in the HA UI instead of plain text boxes.
- **Reauth flow timeout handling** — `TimeoutError` during re-authentication now shows the `cannot_connect` error instead of propagating as an unhandled exception.

### Changed
- **Coordinator name includes account email** — log lines now read `"sensorlinx (user@example.com)"` rather than the bare `"sensorlinx"` domain, making multi-account setups distinguishable in logs.
- **Public coordinator attributes** — `_entry_data` and `_timeout` renamed to `entry_data` and `timeout`; `services.py` no longer reaches into private state.
- **`SensorLinxCoordinator` generic type** — declared as `DataUpdateCoordinator[dict[str, dict]]`; type checkers now see `coordinator.data` as `dict[str, dict]` rather than `Any`.
- **`CONF_EMAIL`/`CONF_PASSWORD` import moved to module level** in `services.py`; previously imported inside `_call_with_reauth` on every service call.

### Fixed
- **Coordinator re-login path was unguarded** — only the initial `_fetch()` was inside `asyncio.timeout`; a hung re-login or retry fetch could block the coordinator indefinitely. All three operations (fetch, re-login, retry) now share a single timeout.
- **`async_setup_entry` login was unguarded** — initial `client.login()` during setup now wrapped in `asyncio.timeout`; a hung login raises `ConfigEntryNotReady` with a clear message.
- **`_authenticate` (config flow) was unguarded** — both the user and re-auth flows now wrap login in `asyncio.timeout`; a hung API call shows `cannot_connect` instead of freezing the flow UI.
- **`async_remove_config_entry_device` not implemented** — without it, a manually deleted device would reappear on the next poll (live discovery). Now returns `False` for devices still present in the API, blocking the removal with a clear UI message.
- **`Connected` binary sensor category** — set to `EntityCategory.DIAGNOSTIC` so it appears in the Diagnostic section of the device card rather than alongside operational sensors.
- **`target_temperature` attribute returned raw °F regardless of user unit** — the extra attribute is now converted to the HA display unit via `TemperatureConverter` so it matches the sensor's displayed value.
- **Options flow saved floats instead of ints** — `NumberSelector` submits `float` from the UI; values are now coerced to `int` before being stored in `entry.options`.
- **Diagnostics missing poll settings** — `scan_interval` and `timeout` from `entry.options` are now included in the coordinator section of the diagnostics download.

## [0.3.0] - 2026-03-20

### Added
- **Live device discovery** — new devices appearing in the SensorLinx API are automatically registered as entities without requiring an integration reload or HA restart.
- **Device re-appearance** — entities for a device that previously disappeared and was cleaned up are recreated automatically when the device comes back.
- **`async_migrate_entry`** — migration stub added; provides a safe landing pad for future config-entry schema changes without breaking existing installations.
- **`PARALLEL_UPDATES = 0`** — declared on both sensor and binary sensor platforms, signalling to HA that these platforms use a coordinator and do not poll individually.

### Changed
- **Services now use HA device selector** — `set_hvac_mode_priority` and `set_permanent_demand` now accept `device_id` (the HA device registry UUID shown in the device UI) instead of a raw `sync_code` string. The UI shows a filtered device picker; YAML automations must be updated to use the device registry ID.
- **Temperature display precision** — temperature sensors now declare `suggested_display_precision = 1` (one decimal place); demand sensors declare `suggested_display_precision = 0` (integer %).
- **`_needs()` helper** — moved outside the inner device loop in the binary sensor platform setup for clarity.

## [0.2.0] - 2026-03-13

### Added
- **Stale entity cleanup** — devices and their entities are automatically removed from the HA registry when they are no longer returned by the SensorLinx API.
- **Re-authentication flow** — when credentials expire, HA surfaces a re-authentication prompt instead of silently failing.
- **Service calls** — two new services for writing back to devices:
  - `sensorlinx.set_hvac_mode_priority` — set heat / cool / auto priority.
  - `sensorlinx.set_permanent_demand` — enable or disable permanent heating/cooling demand.
- **API timeout option** — configurable per-request timeout (10–120 s, default 30 s) to prevent coordinator hangs on slow or dead API connections.
- **Service error handling** — service calls retry once on session expiry (same behaviour as coordinator polling) and surface API errors as `ServiceValidationError`.
- **Diagnostics support** — download diagnostics from Settings → Devices & Services → SensorLinx → Download diagnostics. Passwords are redacted automatically.
- **`quality_scale: silver`** added to manifest.
- Entity name translations in `strings.json` / `translations/en.json`.
- Comprehensive logging throughout coordinator, entity setup, and integration lifecycle.

### Changed
- **Entity unique IDs** are now based on device `syncCode` rather than config entry IDs, making them portable across reinstalls. Existing entity customisations will need to be re-applied on upgrade from 0.1.x.
- `entity.available` now returns `False` when the device disappears from coordinator data (not just when the coordinator update fails).
- Binary sensors use `_safe_bool` / `_get_list_item` helpers to guard all list index accesses and handle unexpected `None` values without raising.
- Type annotations tightened throughout coordinator, services, and binary sensor helpers.

### Fixed
- Relay binary sensors now correctly handle both plain-boolean and dict relay values.
- Reversing valve, backup heat, and weather shutdown sensors return `None` (unknown) instead of raising when the data shape is unexpected.

## [0.1.0] - 2026-03-06

### Added
- Initial Home Assistant integration for HBX SensorLinx building automation platform.
- Automatic discovery of all buildings and devices linked to the SensorLinx account.
- Sensor entities: system demand (%) and per-channel temperature readings.
- Binary sensor entities: connected, demand channels, heat pump stages, backup heat, pumps, reversing valve, relays, warm/cold weather shutdown.
- Configurable poll interval (30–3600 s, default 60 s).
- Automatic re-authentication on session expiry during polling.
- Config flow with email/password validation and duplicate-entry prevention.
- Options flow for adjusting poll interval without re-entering credentials.
- `DataUpdateCoordinator`-based architecture with graceful per-building error handling.
- `suggested_area` set from building name for automatic HA area assignment.
