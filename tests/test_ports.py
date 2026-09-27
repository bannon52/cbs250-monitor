"""Per-port device behaviour."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.cbs250 import async_remove_config_entry_device
from custom_components.cbs250.const import DOMAIN

from .conftest import make_port

SW = "aa:bb:cc:dd:ee:ff"


def port_device(hass, idx):
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, f"{SW}_port_{idx}")})


async def setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def refresh(hass, entry):
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()


async def test_only_qualifying_ports_get_devices(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    assert port_device(hass, 1) is not None  # labelled
    assert port_device(hass, 2) is not None  # linked
    assert port_device(hass, 3) is not None  # PoE delivering
    assert port_device(hass, 4) is None      # nothing
    assert port_device(hass, 17) is None     # empty uplink


async def test_devices_link_to_switch_and_names(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    dev_reg = dr.async_get(hass)
    sw = dev_reg.async_get_device(identifiers={(DOMAIN, SW)})
    assert sw is not None and sw.name == "Rack Switch"
    d1 = port_device(hass, 1)
    assert d1.via_device_id == sw.id
    assert d1.name == "Front Camera"
    assert d1.model == "Port gi1"
    assert port_device(hass, 2).name == "gi2"
    # All devices belong to the one config entry
    assert len(dr.async_entries_for_config_entry(dev_reg, entry.entry_id)) == 4


async def test_readable_entity_ids(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    ent_reg = er.async_get(hass)
    eid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"{SW}_1_poe_power")
    assert eid == "sensor.gi1_poe_power"
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, f"{SW}_1_rx_throughput") == "sensor.gi1_download"
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, f"{SW}_1_tx_throughput") == "sensor.gi1_upload"
    assert hass.states.get("sensor.gi3_poe_power").state == "6.2"


async def test_friendly_names_use_description(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    assert hass.states.get("sensor.gi1_poe_power").attributes["friendly_name"] == "Front Camera PoE power"
    assert hass.states.get("sensor.gi2_download").attributes["friendly_name"] == "gi2 Download"


async def test_new_port_added_without_reload(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    assert port_device(hass, 4) is None
    switch.data.ports[4] = make_port(4, up=True, poe=3.1)
    await refresh(hass, entry)
    assert port_device(hass, 4) is not None
    assert hass.states.get("sensor.gi4_poe_power").state == "3.1"


async def test_rescan_button(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    switch.data.ports[4] = make_port(4, alias="Garage AP")
    polls = switch.polls
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.rack_switch_rescan_ports"}, blocking=True
    )
    await hass.async_block_till_done()
    assert switch.polls == polls + 1
    assert port_device(hass, 4).name == "Garage AP"


async def test_unplugged_port_is_kept(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    # gi2 only qualified because it was linked; unplug it.
    switch.data.ports[2] = make_port(2)
    await refresh(hass, entry)
    assert port_device(hass, 2) is not None
    assert hass.states.get("sensor.gi2_link_status").state == "down"
    assert hass.states.get("sensor.gi2_link_speed").state == "0"

    # Survives a reload / HA restart too.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert port_device(hass, 2) is not None
    assert hass.states.get("sensor.gi2_link_status").state == "down"


async def test_label_change_renames_device(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    switch.data.ports[1] = make_port(1, alias="Driveway Camera")
    await refresh(hass, entry)
    assert port_device(hass, 1).name == "Driveway Camera"
    # Entity ID stays tied to the port; friendly name follows the label
    state = hass.states.get("sensor.gi1_poe_power")
    assert state.attributes["friendly_name"] == "Driveway Camera PoE power"


async def test_swapping_devices_between_ports(hass: HomeAssistant, switch, entry):
    """Move the camera from gi1 to gi3 and relabel both ports on the switch."""
    await setup(hass, entry)
    switch.data.ports[1] = make_port(1, alias="Spare")
    switch.data.ports[3] = make_port(3, alias="Front Camera", poe=6.2)
    await refresh(hass, entry)
    assert port_device(hass, 1).name == "Spare"
    assert port_device(hass, 3).name == "Front Camera"
    assert hass.states.get("sensor.gi3_poe_power").attributes["friendly_name"] == "Front Camera PoE power"
    assert hass.states.get("sensor.gi1_poe_power").attributes["friendly_name"] == "Spare PoE power"


async def test_clearing_description_falls_back_to_port(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    switch.data.ports[1] = make_port(1, alias="")
    await refresh(hass, entry)
    assert port_device(hass, 1).name == "gi1"
    assert hass.states.get("sensor.gi1_poe_power").attributes["friendly_name"] == "gi1 PoE power"


async def test_user_rename_wins(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    dev_reg = dr.async_get(hass)
    dev_reg.async_update_device(port_device(hass, 1).id, name_by_user="My Cam")
    switch.data.ports[1] = make_port(1, alias="Something Else")
    await refresh(hass, entry)
    assert port_device(hass, 1).name_by_user == "My Cam"


async def test_device_removal_rules(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    dev_reg = dr.async_get(hass)
    sw = dev_reg.async_get_device(identifiers={(DOMAIN, SW)})
    assert await async_remove_config_entry_device(hass, entry, port_device(hass, 1)) is True
    assert await async_remove_config_entry_device(hass, entry, sw) is False


async def test_deleted_idle_port_stays_gone(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    switch.data.ports[2] = make_port(2)  # unplug gi2, no label
    await refresh(hass, entry)
    dev_reg = dr.async_get(hass)
    dev_reg.async_update_device(port_device(hass, 2).id, remove_config_entry_id=entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert port_device(hass, 2) is None
    # ...but plugging it back in brings it back
    switch.data.ports[2] = make_port(2, up=True)
    await refresh(hass, entry)
    assert port_device(hass, 2) is not None


async def test_switch_summary_sensors(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    total = hass.states.get("sensor.rack_switch_total_poe_power")
    assert total.state == "6.0"
    assert total.attributes["ports"] == {"gi3": 6.2}
    switch.data.ports[3] = make_port(3, alias="Office AP", poe=6.2)
    await refresh(hass, entry)
    total = hass.states.get("sensor.rack_switch_total_poe_power")
    assert total.attributes["ports"] == {"Office AP (gi3)": 6.2}
    ports_up = hass.states.get("sensor.rack_switch_ports_up")
    assert ports_up.state == "1"
    assert ports_up.attributes["total_ports"] == 5
    assert hass.states.get("sensor.rack_switch_poe_budget").state == "120.0"


async def test_diagnostics_disabled_by_default(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    ent_reg = er.async_get(hass)
    for key in ("cable_length", "poe_voltage", "poe_current"):
        eid = ent_reg.async_get_entity_id("sensor", DOMAIN, f"{SW}_3_{key}")
        assert ent_reg.async_get(eid).disabled_by is not None, key
    # Non-PoE uplink never gets PoE sensors (would only exist if it qualified)


async def test_unload(hass: HomeAssistant, switch, entry):
    await setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_old_default_disabled_sensors_are_reenabled(hass: HomeAssistant, switch, entry):
    """v0.2 disabled link status by default; HA restores that on re-add."""
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    stale = ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{SW}_2_link_status", config_entry=entry,
        suggested_object_id="gi2_link_status",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    mine = ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{SW}_3_link_status", config_entry=entry,
        suggested_object_id="gi3_link_status",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    still_off = ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{SW}_3_cable_length", config_entry=entry,
        suggested_object_id="gi3_cable_length",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert ent_reg.async_get(stale.entity_id).disabled_by is None
    assert hass.states.get("sensor.gi2_link_status").state == "up"
    # User's own choice is respected
    assert ent_reg.async_get(mine.entity_id).disabled_by is er.RegistryEntryDisabler.USER
    # Sensors still disabled by default stay disabled
    assert ent_reg.async_get(still_off.entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_respects_disable_new_entities_preference(hass: HomeAssistant, switch, entry):
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, pref_disable_new_entities=True)
    ent_reg = er.async_get(hass)
    stale = ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{SW}_2_link_status", config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert ent_reg.async_get(stale.entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION
