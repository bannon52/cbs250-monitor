# Changelog

## v0.4.1

### Fixed
- The card showed every port as disconnected, and hid upload and download, when the Link status sensors were disabled. This affected installs whose entities were first created under v0.2, where those sensors were disabled by default. The card now falls back to link speed, then to traffic, to work out whether a port is connected.
- Upload and download are no longer hidden on a port the card thinks is disconnected if it has traffic.
- Sensors disabled only by an older default (such as Link status from v0.2) are now re-enabled automatically on startup. Newer Home Assistant versions restore an entity's disabled state even after the integration is removed and re-added, so reinstalling didn't fix this. Sensors you disabled yourself are left alone, as is everything if you've turned off "Enable newly added entities" for the integration.

## v0.4.0

### Added
- **Dashboard card** (`custom:cbs250-switch-card`), installed and loaded automatically with the integration:
  - Front-panel view of the switch with each port lit by link state and speed, and a bolt on ports delivering PoE.
  - Summary of connected ports, PoE usage against the budget, and optional uplink throughput.
  - Port table with download, upload and PoE, including bars for relative usage.
  - Tap a jack or row for port details, and tap any value to open its history.
  - Follows your Home Assistant light or dark theme, with a compact layout on phones.
  - Keyboard accessible.
- Entities now carry translation keys, which the card uses to find each metric regardless of entity ID. Names and entity IDs are unchanged.

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
Existing entities keep their history and move onto the new port devices, but keep their old entity IDs. Removing and re-adding the integration does not change this on current Home Assistant versions, which restore entity IDs for returning entities. Rename any entity IDs you want to change from each entity's settings.

## v0.2.0
- Initial public release.
