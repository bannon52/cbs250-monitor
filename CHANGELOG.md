# Changelog

## v0.3.0

### Changed
- **Each port in use is now its own device**, linked to the switch.
- **Entity IDs follow the physical port** (`sensor.gi5_poe_power`, `sensor.gi5_download`) and never change when you move things around.
- **Friendly names follow the port description** on the switch (`Front Camera PoE power`), falling back to the port name. The device page shows the port as its model.
- Only ports with a description, an active link, or PoE delivery get a device. Unused ports no longer create entities.
- Link speed and link status are now diagnostic entities. Cable length is disabled by default.
- Per-port entities no longer repeat port name, description and link status as attributes; the device holds that now.

### Added
- New ports are detected automatically on each poll, with no reload needed.
- **Rescan ports** button on the switch device to check immediately.
- Port devices are remembered across restarts and are never removed automatically when something is unplugged.
- Changing a port description on the switch updates the device and sensor friendly names on the next poll. Names set in Home Assistant take priority.
- Port devices can be deleted from the UI. The switch device is protected.
- **Ports up** sensor on the switch.
- Total PoE power now includes a live per-port breakdown in its `ports` attribute, keyed like `Front Camera (gi5)` (not recorded, to keep the database lean).

### Upgrading from v0.2
Existing entities keep their history and move onto the new port devices, but keep their old entity IDs. To get the new port-based IDs, remove the integration and add it again after updating.

## v0.2.0
- Initial public release.
