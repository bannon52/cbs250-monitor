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
    CONF_HOST,
    EntityCategory,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import Cbs250ConfigEntry
from .const import DOMAIN
from .coordinator import Cbs250Coordinator, PortData


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
        key="link_speed",
        name="Link speed",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        suggested_display_precision=0,
        icon="mdi:speedometer",
        value_fn=lambda p: p.link_speed_mbps if p.oper_status == "up" else 0,
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
        icon="mdi:cable-data",
        value_fn=lambda p: p.cable_length_m,
    ),
    Cbs250PortSensorDescription(
        key="link_status",
        name="Link status",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:ethernet",
        value_fn=lambda p: p.oper_status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Cbs250ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator = entry.runtime_data
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.title,
        manufacturer="Cisco",
        model="CBS250 series",
        configuration_url=f"https://{entry.data[CONF_HOST]}",
    )

    entities: list[SensorEntity] = []
    for if_index, port in coordinator.data.ports.items():
        for description in PORT_SENSORS:
            if description.exists_fn(port):
                entities.append(
                    Cbs250PortSensor(coordinator, entry, description, if_index, device_info)
                )

    entities.append(
        Cbs250SwitchSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="total_poe_power",
                name="Total PoE power",
                native_unit_of_measurement=UnitOfPower.WATT,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            lambda d: d.total_poe_w,
            device_info,
        )
    )
    entities.append(
        Cbs250SwitchSensor(
            coordinator,
            entry,
            SensorEntityDescription(
                key="poe_budget",
                name="PoE budget",
                native_unit_of_measurement=UnitOfPower.WATT,
                device_class=SensorDeviceClass.POWER,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            lambda d: d.nominal_poe_w,
            device_info,
        )
    )

    async_add_entities(entities)


class Cbs250PortSensor(CoordinatorEntity[Cbs250Coordinator], SensorEntity):
    """A sensor for a single switch port."""

    entity_description: Cbs250PortSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Cbs250Coordinator,
        entry: Cbs250ConfigEntry,
        description: Cbs250PortSensorDescription,
        if_index: int,
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the port sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._if_index = if_index
        port = coordinator.data.ports[if_index]
        port_label = port.name or f"port{if_index}"
        self._attr_name = f"{port_label} {description.name}"
        base = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base}_{if_index}_{description.key}"
        self._attr_device_info = device_info

    @property
    def _port(self) -> PortData | None:
        return self.coordinator.data.ports.get(self._if_index)

    @property
    def available(self) -> bool:
        """Available while the coordinator succeeds and the port exists."""
        return super().available and self._port is not None

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        port = self._port
        if port is None:
            return None
        return self.entity_description.value_fn(port)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Attach port context to every sensor."""
        port = self._port
        if port is None:
            return None
        attrs: dict[str, Any] = {
            "port": port.name,
            "description": port.alias or None,
            "link_status": port.oper_status,
        }
        if self.entity_description.key == "poe_status" and port.poe_status_descr:
            attrs["status_detail"] = port.poe_status_descr
        return attrs


class Cbs250SwitchSensor(CoordinatorEntity[Cbs250Coordinator], SensorEntity):
    """A switch-level sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Cbs250Coordinator,
        entry: Cbs250ConfigEntry,
        description: SensorEntityDescription,
        value_fn: Callable[[Any], Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialise the switch sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._value_fn = value_fn
        base = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base}_{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self._value_fn(self.coordinator.data)
