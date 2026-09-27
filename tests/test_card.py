"""Dashboard card support."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.cbs250 import CARD_URL, _async_register_card
from custom_components.cbs250.const import DOMAIN

SW = "aa:bb:cc:dd:ee:ff"
CARD = Path(__file__).parent.parent / "custom_components" / DOMAIN / "frontend" / "cbs250-switch-card.js"


async def test_card_file_ships_with_integration():
    assert CARD.is_file()
    assert 'customElements.define("cbs250-switch-card"' in CARD.read_text()


async def test_entities_expose_keys_for_card(hass: HomeAssistant, switch, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ent_reg = er.async_get(hass)
    expected = {
        f"{SW}_3_rx_throughput": "rx_throughput",
        f"{SW}_3_tx_throughput": "tx_throughput",
        f"{SW}_3_poe_power": "poe_power",
        f"{SW}_3_link_status": "link_status",
        f"{SW}_total_poe_power": "total_poe_power",
        f"{SW}_ports_up": "ports_up",
        f"{SW}_poe_budget": "poe_budget",
    }
    for unique_id, key in expected.items():
        eid = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert ent_reg.async_get(eid).translation_key == key, unique_id
    # Keys don't disturb the explicit friendly names
    assert hass.states.get("sensor.gi3_poe_power").attributes["friendly_name"] == "gi3 PoE power"
    assert hass.states.get("sensor.rack_switch_total_poe_power").attributes["friendly_name"] == "Rack Switch Total PoE power"


async def test_card_registered_when_frontend_loaded(hass: HomeAssistant):
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.config.components.add("frontend")
    with patch("homeassistant.components.frontend.add_extra_js_url") as add_js:
        await _async_register_card(hass)
    paths = hass.http.async_register_static_paths.call_args[0][0]
    assert paths[0].url_path == CARD_URL
    assert Path(paths[0].path) == CARD
    url = add_js.call_args[0][1]
    assert url.startswith(f"{CARD_URL}?v=")


async def test_card_skipped_without_frontend(hass: HomeAssistant):
    """Headless setups (and these tests) shouldn't fail."""
    assert await async_setup_component(hass, DOMAIN, {})
