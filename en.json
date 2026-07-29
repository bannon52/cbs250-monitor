"""The CBS250 Monitor integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import Cbs250Coordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type Cbs250ConfigEntry = ConfigEntry[Cbs250Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: Cbs250ConfigEntry) -> bool:
    """Set up CBS250 Monitor from a config entry."""
    coordinator = Cbs250Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: Cbs250ConfigEntry) -> None:
    """Reload on options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: Cbs250ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown_engine()
    return unload_ok
