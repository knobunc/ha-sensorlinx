"""Select entities for SensorLinx device controls."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SensorLinxCoordinator
from .entity import SensorLinxBaseEntity

PARALLEL_UPDATES = 1

_PRIORITY_MAP: dict[int, str] = {0: "heat", 1: "cool", 2: "auto"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SensorLinx select entities from a config entry."""
    coordinator: SensorLinxCoordinator = hass.data[DOMAIN][entry.entry_id]

    _added_uids: set[str] = set()

    @callback
    def _async_add_selects() -> None:
        ent_reg = er.async_get(hass)
        new_entities: list[SelectEntity] = []

        def _needs(uid: str) -> bool:
            if uid not in _added_uids:
                _added_uids.add(uid)
                return True
            return ent_reg.async_get_entity_id("select", DOMAIN, uid) is None

        for building_id, building_data in coordinator.data.items():
            for sync_code, device_data in building_data["devices"].items():
                device = device_data["device"]

                if "prior" in device:
                    uid = f"{sync_code}_priority_select"
                    if _needs(uid):
                        new_entities.append(
                            SensorLinxPrioritySelect(
                                coordinator, building_id, sync_code
                            )
                        )

        if new_entities:
            async_add_entities(new_entities)

    _async_add_selects()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_selects))


class SensorLinxPrioritySelect(SensorLinxBaseEntity, SelectEntity):
    """HVAC demand priority selector (heat / cool / auto)."""

    _attr_translation_key = "priority_select"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = ["heat", "cool", "auto"]
    _attr_icon = "mdi:hvac"

    def __init__(
        self,
        coordinator: SensorLinxCoordinator,
        building_id: str,
        sync_code: str,
    ) -> None:
        super().__init__(coordinator, building_id, sync_code)
        self._attr_unique_id = f"{sync_code}_priority_select"

    @property
    def current_option(self) -> str | None:
        device = self._get_device()
        if device is None:
            return None
        prior = device.get("prior")
        return _PRIORITY_MAP.get(prior) if prior is not None else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_device_parameter(
            self._building_id,
            self._api_device_id,
            hvac_mode_priority=option,
        )
