from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pysensorlinx import InvalidCredentialsError, LoginError, Sensorlinx

from .const import DEFAULT_TIMEOUT, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SensorLinxCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Polls all buildings and devices from the SensorLinx API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: Sensorlinx,
        entry_data: Mapping[str, Any],
        scan_interval: int = SCAN_INTERVAL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the coordinator with an authenticated API client."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({entry_data.get(CONF_EMAIL, 'unknown')})",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.entry_data: Mapping[str, Any] = entry_data
        self.timeout = timeout

    async def _async_update_data(self) -> dict[str, dict]:
        """Fetch data, retrying once on auth expiry.

        The entire operation — including any re-login and retry — is bounded by
        the configured timeout so the coordinator can never hang indefinitely.
        """
        try:
            async with asyncio.timeout(self.timeout):
                try:
                    return await self._fetch()
                except (InvalidCredentialsError, LoginError):
                    # Session may have expired — try re-authenticating once.
                    _LOGGER.debug("Auth error, attempting re-login")
                    await self.client.login(
                        username=self.entry_data[CONF_EMAIL],
                        password=self.entry_data[CONF_PASSWORD],
                    )
                    return await self._fetch()
        except TimeoutError as err:
            raise UpdateFailed(
                f"SensorLinx API timed out after {self.timeout}s"
            ) from err
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except LoginError as err:
            raise UpdateFailed(f"Re-authentication failed: {err}") from err
        except RuntimeError as err:
            raise UpdateFailed(f"SensorLinx error: {err}") from err

    async def _fetch(self) -> dict[str, dict]:
        """Fetch all buildings and their devices from the API."""
        data: dict[str, dict] = {}
        buildings = await self.client.get_buildings()
        if not buildings:
            _LOGGER.debug("No buildings returned from SensorLinx API")
            return data

        _LOGGER.debug("Fetching devices for %d building(s)", len(buildings))
        for building in buildings:
            building_id = building["id"]
            building_name = building.get("name", building_id)
            try:
                devices_list = await self.client.get_devices(building_id)
            except RuntimeError as err:
                _LOGGER.warning(
                    "Failed to fetch devices for building '%s' (%s): %s",
                    building_name,
                    building_id,
                    err,
                )
                devices_list = []

            devices: dict[str, dict] = {}
            for device in devices_list or []:
                sync_code = device.get("syncCode")
                if sync_code:
                    devices[sync_code] = {"device": device}
                    _LOGGER.debug(
                        "Discovered device '%s' (sync_code=%s, type=%s) in building '%s'",
                        device.get("name", sync_code),
                        sync_code,
                        device.get("deviceType"),
                        building_name,
                    )
                else:
                    _LOGGER.warning(
                        "Device in building '%s' has no syncCode, skipping: %s",
                        building_name,
                        device.get("name"),
                    )

            data[building_id] = {"building": building, "devices": devices}

        _LOGGER.debug(
            "Fetched %d building(s), %d total device(s)",
            len(data),
            sum(len(b["devices"]) for b in data.values()),
        )
        return data
