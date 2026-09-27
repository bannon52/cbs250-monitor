"""Config flow for the CBS250 Monitor integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    get_cmd,
)

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .const import (
    CONF_COMMUNITY,
    CONF_ENABLE_CABLE_LENGTH,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    OID_BRIDGE_MAC,
    OID_SYS_NAME,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


async def _validate_connection(data: dict[str, Any]) -> dict[str, str]:
    """Check we can talk SNMP to the switch; return title and unique_id."""
    engine = SnmpEngine()
    try:
        target = await UdpTransportTarget.create(
            (data[CONF_HOST], data.get(CONF_PORT, DEFAULT_PORT)),
            timeout=5.0,
            retries=1,
        )
        auth = CommunityData(data[CONF_COMMUNITY], mpModel=1)

        err_ind, err_stat, _err_idx, var_binds = await get_cmd(
            engine,
            auth,
            target,
            ContextData(),
            ObjectType(ObjectIdentity(OID_SYS_NAME)),
        )
        if err_ind or err_stat:
            raise CannotConnect(str(err_ind or err_stat))
        sys_name = str(var_binds[0][1]) if var_binds else ""

        unique_id = data[CONF_HOST]
        err_ind, err_stat, _err_idx, var_binds = await get_cmd(
            engine,
            auth,
            target,
            ContextData(),
            ObjectType(ObjectIdentity(OID_BRIDGE_MAC)),
        )
        if not err_ind and not err_stat and var_binds:
            raw = var_binds[0][1]
            try:
                mac = ":".join(f"{b:02x}" for b in bytes(raw))
                if mac and mac != "00:00:00:00:00:00":
                    unique_id = mac
            except (TypeError, ValueError):
                pass

        return {
            "title": sys_name or f"CBS250 ({data[CONF_HOST]})",
            "unique_id": unique_id,
        }
    finally:
        try:
            engine.close_dispatcher()
        except AttributeError:
            dispatcher = getattr(engine, "transport_dispatcher", None)
            if dispatcher is not None:
                dispatcher.close_dispatcher()


class Cbs250ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CBS250 Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await _validate_connection(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating SNMP connection")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["unique_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return Cbs250OptionsFlow()


class Cbs250OptionsFlow(OptionsFlow):
    """Options flow: scan interval and cable-length polling."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL)),
                vol.Optional(
                    CONF_ENABLE_CABLE_LENGTH,
                    default=options.get(CONF_ENABLE_CABLE_LENGTH, True),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
