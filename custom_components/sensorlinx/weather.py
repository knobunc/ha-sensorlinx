"""Weather platform for SensorLinx — building-level current conditions and forecast."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.weather import (
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SensorLinxCoordinator

_LOGGER = logging.getLogger(__name__)

_OWM_TO_HA: dict[int, str] = {}
for _code in range(200, 300):
    _OWM_TO_HA[_code] = "lightning-rainy"
for _code in range(300, 400):
    _OWM_TO_HA[_code] = "rainy"
for _code in range(500, 505):
    _OWM_TO_HA[_code] = "rainy"
_OWM_TO_HA[511] = "snowy"
for _code in range(520, 532):
    _OWM_TO_HA[_code] = "pouring"
for _code in range(600, 700):
    _OWM_TO_HA[_code] = "snowy"
for _code in range(700, 800):
    _OWM_TO_HA[_code] = "fog"
_OWM_TO_HA[800] = "sunny"
_OWM_TO_HA[801] = "partlycloudy"
for _code in range(802, 805):
    _OWM_TO_HA[_code] = "cloudy"


def _owm_condition(weather_id: int | None) -> str | None:
    if weather_id is None:
        return None
    return _OWM_TO_HA.get(weather_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SensorLinxCoordinator = hass.data[DOMAIN][entry.entry_id]

    _added: set[str] = set()

    @callback
    def _async_add_weather() -> None:
        new: list[WeatherEntity] = []
        _LOGGER.debug("Checking %d building(s) for weather data", len(coordinator.data))
        for building_id, building_data in coordinator.data.items():
            building = building_data["building"]
            has_weather = building.get("weather") is not None
            _LOGGER.debug(
                "Building %s: has_weather=%s, keys=%s",
                building_id,
                has_weather,
                list(building.keys()),
            )
            if not has_weather:
                continue
            uid = f"{building_id}_weather"
            if uid not in _added:
                _added.add(uid)
                new.append(
                    SensorLinxWeather(
                        coordinator,
                        building_id,
                        building.get("name", building_id),
                    )
                )
        if new:
            _LOGGER.debug("Adding %d weather entity/entities", len(new))
            async_add_entities(new)
        else:
            _LOGGER.debug("No new weather entities to add")

    _async_add_weather()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_weather))


class SensorLinxWeather(CoordinatorEntity[SensorLinxCoordinator], WeatherEntity):
    _attr_has_entity_name = True
    _attr_native_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.MILES_PER_HOUR
    _attr_supported_features = WeatherEntityFeature.FORECAST_HOURLY

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        building_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._building_id = building_id
        self._attr_unique_id = f"{building_id}_weather"
        self._attr_name = f"{building_name} Weather"

    def _weather(self) -> dict[str, Any] | None:
        try:
            return self.coordinator.data[self._building_id]["building"]["weather"][
                "weather"
            ]
        except (KeyError, TypeError):
            return None

    @property
    def available(self) -> bool:
        return super().available and self._weather() is not None

    @property
    def native_temperature(self) -> float | None:
        w = self._weather()
        return w.get("temp") if w else None

    @property
    def native_apparent_temperature(self) -> float | None:
        w = self._weather()
        return w.get("feelsLike") if w else None

    @property
    def humidity(self) -> int | None:
        w = self._weather()
        return w.get("humidity") if w else None

    @property
    def native_pressure(self) -> float | None:
        w = self._weather()
        return w.get("pressure") if w else None

    @property
    def native_wind_speed(self) -> float | None:
        w = self._weather()
        return w.get("wind") if w else None

    @property
    def wind_bearing(self) -> int | None:
        w = self._weather()
        return w.get("windDir") if w else None

    @property
    def cloud_coverage(self) -> int | None:
        w = self._weather()
        return w.get("clouds") if w else None

    @property
    def condition(self) -> str | None:
        w = self._weather()
        if w is None:
            return None
        return _owm_condition(w.get("weatherId"))

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        try:
            forecast_data = self.coordinator.data[self._building_id]["building"][
                "weather"
            ]["forecast"]
        except (KeyError, TypeError):
            return None
        if not isinstance(forecast_data, list):
            return None

        forecasts: list[Forecast] = []
        for period in forecast_data:
            time_str = period.get("time", "")
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                dt = datetime.now(tz=timezone.utc)
            forecasts.append(
                Forecast(
                    datetime=dt.isoformat(),
                    native_temperature=period.get("temp"),
                    native_templow=period.get("min"),
                    precipitation_probability=period.get("pop"),
                    condition=_owm_condition(period.get("weatherId")),
                )
            )
        return forecasts
