"""Shared base entity for SensorLinx."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import SensorLinxCoordinator


class SensorLinxBaseEntity(CoordinatorEntity[SensorLinxCoordinator]):
    """Base class for all SensorLinx entities.

    Provides:
    - _attr_has_entity_name = True  (device name prepended automatically)
    - device_info property          (updated from coordinator on each poll)
    - _get_device()                 (safe access to current device dict)
    - available                     (False if device disappears from coordinator)
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
    ) -> None:
        """Initialise the base entity with its building and device identifiers."""
        super().__init__(coordinator)
        self._building_id = building_id
        self._sync_code = sync_code

    def _get_device(self) -> dict[str, Any] | None:
        """Return the current device dict, or None if it has disappeared."""
        try:
            return cast(
                dict[str, Any],
                self.coordinator.data[self._building_id]["devices"][self._sync_code][
                    "device"
                ],
            )
        except KeyError:
            return None

    @property
    def available(self) -> bool:
        """Return False if the coordinator failed or the device is no longer reported."""
        return super().available and self._get_device() is not None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Build DeviceInfo live from coordinator data so it stays current."""
        try:
            device = self.coordinator.data[self._building_id]["devices"][
                self._sync_code
            ]["device"]
            building = self.coordinator.data[self._building_id]["building"]
        except KeyError:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self._sync_code)},
            name=device.get("name") or self._sync_code,
            model=device.get("deviceType"),
            sw_version=device.get("firmVer"),
            manufacturer=MANUFACTURER,
            suggested_area=building.get("name"),
        )
