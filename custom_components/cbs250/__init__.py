"""The CBS250 Monitor integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import DOMAIN
from .coordinator import Cbs250Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Port sensors that are enabled by default in the current version. Older
# versions disabled some of these by default, and Home Assistant restores that
# state even after the integration is removed and re-added.
ENABLED_BY_DEFAULT_KEYS = (
    "rx_throughput",
    "tx_throughput",
    "poe_power",
    "link_status",
    "link_speed",
    "poe_status",
)

CARD_FILENAME = "cbs250-switch-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"

type Cbs250ConfigEntry = ConfigEntry[Cbs250Coordinator]


def switch_identifier(entry: ConfigEntry) -> str:
    """Stable identifier for the switch itself."""
    return entry.unique_id or entry.entry_id


def port_identifier(entry: ConfigEntry, if_index: int) -> str:
    """Stable identifier for one port device."""
    return f"{switch_identifier(entry)}_port_{if_index}"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card so it's available without adding a resource."""
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Register the card's static path and load it on every dashboard."""
    if hass.http is None or "frontend" not in hass.config.components:
        return
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    card_path = Path(__file__).parent / "frontend" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), True)]
    )
    # Version in the URL busts the browser cache on each update.
    version = (await async_get_integration(hass, DOMAIN)).version
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")
    _LOGGER.debug("Registered dashboard card at %s", CARD_URL)


async def async_setup_entry(hass: HomeAssistant, entry: Cbs250ConfigEntry) -> bool:
    """Set up CBS250 Monitor from a config entry."""
    _async_enable_stale_defaults(hass, entry)

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


def _async_enable_stale_defaults(hass: HomeAssistant, entry: Cbs250ConfigEntry) -> None:
    """Re-enable sensors that were disabled only by an old default.

    Only entities disabled by the integration are touched. Entities the user
    disabled (disabled_by=USER) are left alone, as is everything when the user
    has turned off "Enable newly added entities" for this entry.
    """
    if entry.pref_disable_new_entities:
        return
    ent_reg = er.async_get(hass)
    prefix = f"{switch_identifier(entry)}_"
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg_entry.disabled_by is not er.RegistryEntryDisabler.INTEGRATION:
            continue
        if not reg_entry.unique_id.startswith(prefix):
            continue
        if any(reg_entry.unique_id.endswith(f"_{key}") for key in ENABLED_BY_DEFAULT_KEYS):
            ent_reg.async_update_entity(reg_entry.entity_id, disabled_by=None)
            _LOGGER.info("Re-enabled %s (disabled by an older default)", reg_entry.entity_id)


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
