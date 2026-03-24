from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from sensorlinx import SensorLinxClient
from sensorlinx.exceptions import AuthError, SensorLinxError

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SensorLinxCoordinator(DataUpdateCoordinator):
    """Polls all buildings and devices from the SensorLinx API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SensorLinxClient,
        entry_data: dict,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.client = client
        self._entry_data = entry_data

    async def _async_update_data(self) -> dict:
        try:
            return await self.hass.async_add_executor_job(self._fetch)
        except AuthError:
            # Token may have expired — try re-authenticating once.
            _LOGGER.debug("Auth error, attempting re-login")
            try:
                await self.hass.async_add_executor_job(
                    self.client.login,
                    self._entry_data[CONF_EMAIL],
                    self._entry_data[CONF_PASSWORD],
                )
                return await self.hass.async_add_executor_job(self._fetch)
            except AuthError as err:
                raise UpdateFailed(f"Authentication failed: {err}") from err
        except SensorLinxError as err:
            raise UpdateFailed(f"SensorLinx error: {err}") from err

    def _fetch(self) -> dict:
        """Synchronous fetch — called in executor thread."""
        data: dict = {}
        for building in self.client.list_buildings():
            devices: dict = {}
            for device in self.client.list_devices(building.id):
                try:
                    sample = self.client.history_sample(building.id, device.sync_code)
                except SensorLinxError:
                    sample = None
                devices[device.sync_code] = {"device": device, "sample": sample}
            data[building.id] = {"building": building, "devices": devices}
        return data
