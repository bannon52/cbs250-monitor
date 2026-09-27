"""Sensor platform for the CBS250 Monitor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Cbs250ConfigEntry, port_identifier, switch_identifier
from .const import DOMAIN
from .coordinator import Cbs250Coordinator, PortData, SwitchData


# ---------------------------------------------------------------------------
# Port discovery helpers
# ---------------------------------------------------------------------------

def port_qualifies(port: PortData) -> bool:
    """A port earns a device if it's labelled, linked, or powering something."""
    return (
        bool(port.alias.strip())
        or port.oper_status == "up"
        or port.poe_status == "delivering_power"
    )


def port_label(port: PortData) -> str:
    """Stable physical port name, e.g. 'gi5'."""
    return port.name or f"port{port.if_index}"


def port_device_name(port: PortData) -> str:
    """Friendly device name: the switch description if set, else the port."""
    return port.alias.strip() or port_label(port)


def port_summary_name(port: PortData) -> str:
    """'Front Camera (gi5)' for compact lists like the PoE breakdown."""
    alias = port.alias.strip()
    label = port_label(port)
    return f"{alias} ({label})" if alias else label


# ---------------------------------------------------------------------------
# Descriptions
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class Cbs250PortSensorDescription(SensorEntityDescription):
    """Describes a per-port sensor."""

    value_fn: Callable[[PortData], Any]
    exists_fn: Callable[[PortData], bool] = lambda port: True


PORT_SENSORS: tuple[Cbs250PortSensorDescription, ...] = (
    Cbs250PortSensorDescription(
        key="rx_throughput",
        name="Download",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:download-network",
        value_fn=lambda p: p.rx_mbps,
    ),
    Cbs250PortSensorDescription(
        key="tx_throughput",
        name="Upload",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:upload-network",
        value_fn=lambda p: p.tx_mbps,
    ),
    Cbs250PortSensorDescription(
        key="poe_power",
        name="PoE power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda p: p.poe_power_w,
        exists_fn=lambda p: p.poe_capable,
    ),
    Cbs250PortSensorDescription(
        key="link_status",
        name="Link status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:ethernet",
        value_fn=lambda p: p.oper_status,
    ),
    Cbs250PortSensorDescription(
        key="link_speed",
        name="Link speed",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        icon="mdi:speedometer",
        value_fn=lambda p: p.link_speed_mbps if p.oper_status == "up" else 0,
    ),
    Cbs250PortSensorDescription(
        key="poe_status",
        name="PoE status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:power-plug",
        value_fn=lambda p: p.poe_status,
        exists_fn=lambda p: p.poe_capable,
    ),
    Cbs250PortSensorDescription(
        key="cable_length",
        name="Cable length",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:cable-data",
        value_fn=lambda p: p.cable_length_m,
    ),
    Cbs250PortSensorDescription(
        key="poe_voltage",
        name="PoE voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda p: p.poe_voltage_v,
        exists_fn=lambda p: p.poe_capable,
    ),
    Cbs250PortSensorDescription(
        key="poe_current",
        name="PoE current",
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda p: p.poe_current_ma,
        exists_fn=lambda p: p.poe_capable,
    ),
)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: Cbs250ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch sensors now, and port sensors as ports are discovered."""
    coordinator = entry.runtime_data
    dev_reg = dr.async_get(hass)
    switch_id = switch_identifier(entry)
    port_prefix = f"{switch_id}_port_"

    async_add_entities(
        [
            Cbs250TotalPoeSensor(coordinator, entry),
            Cbs250PoeBudgetSensor(coordinator, entry),
            Cbs250PortsUpSensor(coordinator, entry),
        ]
    )

    # Ports that already have a device stay forever (until the user deletes
    # them), even if they're currently unplugged and unlabelled.
    remembered: set[int] = set()
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        for domain, ident in device.identifiers:
            if domain == DOMAIN and ident.startswith(port_prefix):
                try:
                    remembered.add(int(ident[len(port_prefix):]))
                except ValueError:
                    continue

    added: set[int] = set()
    last_names: dict[int, str] = {}

    @callback
    def _sync_ports() -> None:
        """Add newly qualifying ports; keep device names in step with labels."""
        data: SwitchData | None = coordinator.data
        if data is None:
            return

        new_entities: list[SensorEntity] = []
        for if_index, port in data.ports.items():
            if if_index in added:
                continue
            if if_index not in remembered and not port_qualifies(port):
                continue
            added.add(if_index)
            for description in PORT_SENSORS:
                if description.exists_fn(port):
                    new_entities.append(
                        Cbs250PortSensor(coordinator, entry, description, port)
                    )

        if new_entities:
            async_add_entities(new_entities)

        # Follow port description changes made on the switch. A name the
        # user set in HA (name_by_user) always wins, as HA displays that.
        for if_index in added:
            port = data.ports.get(if_index)
            if port is None:
                continue
            name = port_device_name(port)
            if last_names.get(if_index) == name:
                continue
            last_names[if_index] = name
            device = dev_reg.async_get_device(
                identifiers={(DOMAIN, port_identifier(entry, if_index))}
            )
            if device is not None and device.name != name:
                dev_reg.async_update_device(device.id, name=name)

    _sync_ports()
    entry.async_on_unload(coordinator.async_add_listener(_sync_ports))


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

class Cbs250PortSensor(CoordinatorEntity[Cbs250Coordinator], SensorEntity):
    """A sensor belonging to one port device."""

    entity_description: Cbs250PortSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Cbs250Coordinator,
        entry: Cbs250ConfigEntry,
        description: Cbs250PortSensorDescription,
        port: PortData,
    ) -> None:
        """Initialise the port sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._if_index = port.if_index
        # Lets the dashboard card find each metric regardless of entity ID.
        self._attr_translation_key = description.key
        switch_id = switch_identifier(entry)
        # Unique ID format unchanged from v0.2 so existing history carries over.
        self._attr_unique_id = f"{switch_id}_{port.if_index}_{description.key}"
        label = port_label(port)
        # Entity IDs follow the physical port (sensor.gi5_poe_power) so they
        # never change when devices are moved or ports are relabelled. The
        # friendly name comes from the device name, i.e. the description.
        # Only applies when first registered; existing IDs are left alone.
        self.entity_id = f"sensor.{slugify(label)}_{slugify(str(description.name))}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, port_identifier(entry, port.if_index))},
            name=port_device_name(port),
            manufacturer="Cisco",
            model=f"Port {label}",
            via_device=(DOMAIN, switch_id),
        )

    @property
    def _port(self) -> PortData | None:
        return self.coordinator.data.ports.get(self._if_index)

    @property
    def available(self) -> bool:
        """Available while polling succeeds and the port still exists."""
        return super().available and self._port is not None

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        port = self._port
        return None if port is None else self.entity_description.value_fn(port)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Only the PoE status carries extra detail now; the device holds the rest."""
        if self.entity_description.key != "poe_status":
            return None
        port = self._port
        if port is None or not port.poe_status_descr:
            return None
        return {"status_detail": port.poe_status_descr}


class _Cbs250SwitchSensor(CoordinatorEntity[Cbs250Coordinator], SensorEntity):
    """Base for sensors on the switch device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Cbs250Coordinator, entry: Cbs250ConfigEntry) -> None:
        """Initialise."""
        super().__init__(coordinator)
        switch_id = switch_identifier(entry)
        self._attr_unique_id = f"{switch_id}_{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, switch_id)})


class Cbs250TotalPoeSensor(_Cbs250SwitchSensor):
    """Total PoE draw, with a per-port breakdown as an attribute."""

    entity_description = SensorEntityDescription(
        key="total_poe_power",
        translation_key="total_poe_power",
        name="Total PoE power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    )
    # Live for dashboards and floorplans, but kept out of the recorder so the
    # changing breakdown doesn't write a new attributes row every poll.
    _unrecorded_attributes = frozenset({"ports"})

    @property
    def native_value(self) -> float | None:
        """Return total PoE consumption."""
        return self.coordinator.data.total_poe_w

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Per-port watts for ports currently drawing power."""
        breakdown = {
            port_summary_name(p): p.poe_power_w
            for p in self.coordinator.data.ports.values()
            if p.poe_power_w
        }
        return {"ports": breakdown}


class Cbs250PoeBudgetSensor(_Cbs250SwitchSensor):
    """Nominal PoE budget of the switch."""

    entity_description = SensorEntityDescription(
        key="poe_budget",
        translation_key="poe_budget",
        name="PoE budget",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    @property
    def native_value(self) -> float | None:
        """Return the PoE budget."""
        return self.coordinator.data.nominal_poe_w


class Cbs250PortsUpSensor(_Cbs250SwitchSensor):
    """Count of ports with an active link."""

    entity_description = SensorEntityDescription(
        key="ports_up",
        translation_key="ports_up",
        name="Ports up",
        icon="mdi:ethernet",
        state_class=SensorStateClass.MEASUREMENT,
    )

    @property
    def native_value(self) -> int:
        """Return number of linked ports."""
        return sum(
            1 for p in self.coordinator.data.ports.values() if p.oper_status == "up"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Total port count for 'x / y' displays."""
        return {"total_ports": len(self.coordinator.data.ports)}
