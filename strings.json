"""DataUpdateCoordinator for the CBS250 Monitor integration."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    bulk_walk_cmd,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_COMMUNITY,
    CONF_ENABLE_CABLE_LENGTH,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    IF_OPER_STATUS,
    OID_IF_ALIAS,
    OID_IF_HC_IN_OCTETS,
    OID_IF_HC_OUT_OCTETS,
    OID_IF_HIGH_SPEED,
    OID_IF_NAME,
    OID_IF_OPER_STATUS,
    OID_IF_TYPE,
    OID_PETH_MAIN_TABLE,
    OID_PETH_PORT_DETECTION,
    OID_RL_PHY_GET_RESULT,
    OID_RL_POE_CURRENT,
    OID_RL_POE_POWER,
    OID_RL_POE_STATUS_DESCR,
    OID_RL_POE_VOLTAGE,
    PETH_DETECTION_STATUS,
    PHY_TEST_CABLE_LENGTH,
)

_LOGGER = logging.getLogger(__name__)

ETHERNET_CSMACD = 6


@dataclass
class PortData:
    """State of a single switch port."""

    if_index: int
    name: str = ""
    alias: str = ""
    oper_status: str = "unknown"
    link_speed_mbps: int | None = None
    rx_mbps: float | None = None
    tx_mbps: float | None = None
    poe_capable: bool = False
    poe_power_w: float | None = None
    poe_voltage_v: float | None = None
    poe_current_ma: int | None = None
    poe_status: str | None = None
    poe_status_descr: str | None = None
    cable_length_m: int | None = None


@dataclass
class SwitchData:
    """State of the whole switch."""

    ports: dict[int, PortData] = field(default_factory=dict)
    total_poe_w: float | None = None
    nominal_poe_w: float | None = None


class Cbs250Coordinator(DataUpdateCoordinator[SwitchData]):
    """Polls the CBS250 over SNMP and computes throughput rates."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.data[CONF_HOST]}",
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._host: str = entry.data[CONF_HOST]
        self._port: int = entry.data.get(CONF_PORT, 161)
        self._community: str = entry.data[CONF_COMMUNITY]
        self._enable_cable_length: bool = entry.options.get(
            CONF_ENABLE_CABLE_LENGTH, True
        )
        self._engine: SnmpEngine | None = None
        self._target: UdpTransportTarget | None = None
        self._auth = CommunityData(self._community, mpModel=1)  # SNMP v2c
        # Previous octet counters for rate calculation:
        # if_index -> (monotonic_ts, in_octets, out_octets)
        self._prev_counters: dict[int, tuple[float, int, int]] = {}

    async def _ensure_engine(self) -> None:
        if self._engine is None:
            self._engine = SnmpEngine()
        if self._target is None:
            self._target = await UdpTransportTarget.create(
                (self._host, self._port), timeout=5.0, retries=1
            )

    async def async_shutdown_engine(self) -> None:
        """Close the SNMP engine dispatcher."""
        if self._engine is not None:
            try:
                self._engine.close_dispatcher()
            except AttributeError:
                dispatcher = getattr(self._engine, "transport_dispatcher", None)
                if dispatcher is not None:
                    dispatcher.close_dispatcher()
            self._engine = None
            self._target = None

    async def _walk(self, base_oid: str) -> dict[str, Any]:
        """Walk an SNMP subtree, returning {index_suffix: value}."""
        await self._ensure_engine()
        results: dict[str, Any] = {}
        prefix_len = len(base_oid) + 1
        async for err_ind, err_stat, _err_idx, var_binds in bulk_walk_cmd(
            self._engine,
            self._auth,
            self._target,
            ContextData(),
            0,
            25,
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        ):
            if err_ind:
                raise UpdateFailed(f"SNMP error walking {base_oid}: {err_ind}")
            if err_stat:
                _LOGGER.debug("SNMP status %s walking %s", err_stat, base_oid)
                break
            for oid, value in var_binds:
                oid_str = str(oid)
                if not oid_str.startswith(base_oid):
                    continue
                results[oid_str[prefix_len:]] = value
        return results

    @staticmethod
    def _as_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    async def _async_update_data(self) -> SwitchData:
        """Fetch all data from the switch."""
        try:
            return await self._fetch()
        except UpdateFailed:
            raise
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"SNMP timeout talking to {self._host}") from err
        except Exception as err:  # noqa: BLE001 - surface as UpdateFailed
            raise UpdateFailed(f"SNMP error: {err}") from err

    async def _fetch(self) -> SwitchData:
        data = SwitchData()

        # --- Interface discovery / basics -------------------------------
        if_types = await self._walk(OID_IF_TYPE)
        if not if_types:
            raise UpdateFailed("Switch returned no interfaces (check community/ACL)")

        eth_indexes = {
            int(idx)
            for idx, val in if_types.items()
            if self._as_int(val) == ETHERNET_CSMACD
        }

        if_names = await self._walk(OID_IF_NAME)
        if_alias = await self._walk(OID_IF_ALIAS)
        if_oper = await self._walk(OID_IF_OPER_STATUS)
        if_speed = await self._walk(OID_IF_HIGH_SPEED)
        in_octets = await self._walk(OID_IF_HC_IN_OCTETS)
        out_octets = await self._walk(OID_IF_HC_OUT_OCTETS)

        now = time.monotonic()

        for if_index in sorted(eth_indexes):
            key = str(if_index)
            port = PortData(if_index=if_index)
            port.name = str(if_names.get(key, f"port{if_index}"))
            port.alias = str(if_alias.get(key, "")) if key in if_alias else ""
            oper = self._as_int(if_oper.get(key))
            port.oper_status = IF_OPER_STATUS.get(oper, "unknown")
            port.link_speed_mbps = self._as_int(if_speed.get(key))

            # Throughput from HC octet counter deltas
            cur_in = self._as_int(in_octets.get(key))
            cur_out = self._as_int(out_octets.get(key))
            prev = self._prev_counters.get(if_index)
            if (
                prev is not None
                and cur_in is not None
                and cur_out is not None
            ):
                prev_ts, prev_in, prev_out = prev
                dt = now - prev_ts
                d_in = cur_in - prev_in
                d_out = cur_out - prev_out
                if dt > 0 and d_in >= 0 and d_out >= 0:
                    port.rx_mbps = round((d_in * 8) / dt / 1_000_000, 3)
                    port.tx_mbps = round((d_out * 8) / dt / 1_000_000, 3)
            if cur_in is not None and cur_out is not None:
                self._prev_counters[if_index] = (now, cur_in, cur_out)

            data.ports[if_index] = port

        # --- PoE: standard detection status + CISCOSB power values ------
        poe_detection = await self._walk(OID_PETH_PORT_DETECTION)
        poe_power = await self._walk(OID_RL_POE_POWER)
        poe_voltage = await self._walk(OID_RL_POE_VOLTAGE)
        poe_current = await self._walk(OID_RL_POE_CURRENT)
        poe_descr = await self._walk(OID_RL_POE_STATUS_DESCR)

        for suffix, value in poe_power.items():
            # suffix = "group.port"; group is 1 on a non-stacked unit and
            # the PoE port index matches ifIndex on CBS switches.
            parts = suffix.split(".")
            if len(parts) != 2:
                continue
            if_index = int(parts[1])
            port = data.ports.get(if_index)
            if port is None:
                continue
            port.poe_capable = True
            mw = self._as_int(value)
            port.poe_power_w = round(mw / 1000, 2) if mw is not None else None
            mv = self._as_int(poe_voltage.get(suffix))
            port.poe_voltage_v = round(mv / 1000, 1) if mv is not None else None
            port.poe_current_ma = self._as_int(poe_current.get(suffix))
            if suffix in poe_descr:
                port.poe_status_descr = str(poe_descr[suffix])
            det = self._as_int(poe_detection.get(suffix))
            if det is not None:
                port.poe_status = PETH_DETECTION_STATUS.get(det, f"unknown_{det}")

        # --- PoE totals (pethMainPseTable: col.group) -------------------
        main_pse = await self._walk(OID_PETH_MAIN_TABLE)
        nominal = self._as_int(main_pse.get("2.1"))
        consumed = self._as_int(main_pse.get("4.1"))
        data.nominal_poe_w = float(nominal) if nominal is not None else None
        data.total_poe_w = float(consumed) if consumed is not None else None

        # --- Cable length (passive VCT read, no TDR triggered) ---------
        if self._enable_cable_length:
            try:
                phy_results = await self._walk(OID_RL_PHY_GET_RESULT)
            except UpdateFailed:
                phy_results = {}
            for suffix, value in phy_results.items():
                parts = suffix.split(".")
                if len(parts) != 2 or int(parts[1]) != PHY_TEST_CABLE_LENGTH:
                    continue
                if_index = int(parts[0])
                port = data.ports.get(if_index)
                if port is None:
                    continue
                length = self._as_int(value)
                # 0 / negative generally means "no result" (link down, etc.)
                port.cable_length_m = length if length and length > 0 else None

        return data
