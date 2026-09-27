"""The CBS250 Monitor integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import Cbs250Coordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

type Cbs250ConfigEntry = ConfigEntry[Cbs250Coordinator]


def switch_identifier(entry: ConfigEntry) -> str:
    """Stable identifier for the switch itself."""
    return entry.unique_id or entry.entry_id


def port_identifier(entry: ConfigEntry, if_index: int) -> str:
    """Stable identifier for one port device."""
    return f"{switch_identifier(entry)}_port_{if_index}"


async def async_setup_entry(hass: HomeAssistant, entry: Cbs250ConfigEntry) -> bool:
    """Set up CBS250 Monitor from a config entry."""
    coordinator = Cbs250Coordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # Register the switch up front so port devices can link to it via_device.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, switch_identifier(entry))},
        name=entry.title,
        manufacturer="Cisco",
        model="CBS250 series",
        configuration_url=f"https://{entry.data[CONF_HOST]}",
    )

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


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: Cbs250ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow port devices to be deleted from the UI; protect the switch itself."""
    return (DOMAIN, switch_identifier(entry)) not in device_entry.identifiers
