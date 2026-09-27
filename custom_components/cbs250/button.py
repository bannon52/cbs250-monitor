"""Button platform for the CBS250 Monitor integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Cbs250ConfigEntry, switch_identifier
from .const import DOMAIN
from .coordinator import Cbs250Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Cbs250ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the rescan button."""
    async_add_entities([Cbs250RescanButton(entry.runtime_data, entry)])


class Cbs250RescanButton(CoordinatorEntity[Cbs250Coordinator], ButtonEntity):
    """Poll the switch now; new ports are picked up as part of the update."""

    _attr_has_entity_name = True
    _attr_name = "Rescan ports"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Cbs250Coordinator, entry: Cbs250ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator)
        switch_id = switch_identifier(entry)
        self._attr_unique_id = f"{switch_id}_rescan_ports"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, switch_id)})

    async def async_press(self) -> None:
        """Trigger an immediate poll."""
        await self.coordinator.async_refresh()
