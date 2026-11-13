"""Config flow: the switch's API address and token."""

from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .api import RTLPlaygroundApi, RTLPlaygroundAuthError, RTLPlaygroundError
from .const import (
    CONF_COUNTERS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


class CannotConnect(Exception):
    pass


class InvalidAuth(Exception):
    pass


class InvalidToken(Exception):
    pass


async def _validate(hass, host: str, token: str) -> dict[str, Any]:
    token = token.strip().lower()
    if not TOKEN_RE.match(token):
        raise InvalidToken
    api = RTLPlaygroundApi(async_get_clientsession(hass), host, token)
    try:
        info = await api.information()
    except RTLPlaygroundAuthError as err:
        raise InvalidAuth from err
    except RTLPlaygroundError as err:
        _LOGGER.debug("Cannot reach %s: %s", host, err)
        raise CannotConnect from err
    if not info.get("mac_address"):
        raise CannotConnect
    return info


class RTLPlaygroundConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            token = user_input[CONF_TOKEN].strip().lower()
            try:
                info = await _validate(self.hass, host, token)
            except InvalidToken:
                errors[CONF_TOKEN] = "invalid_token"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(format_mac(info["mac_address"]))
                self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_TOKEN: token})
                return self.async_create_entry(
                    title=info.get("hostname") or "RTLPlayground",
                    data={CONF_HOST: host, CONF_TOKEN: token},
                )
        schema = vol.Schema({
            vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
            vol.Required(CONF_TOKEN): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip().lower()
            try:
                info = await _validate(self.hass, entry.data[CONF_HOST], token)
            except InvalidToken:
                errors[CONF_TOKEN] = "invalid_token"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(format_mac(info["mac_address"]))
                self._abort_if_unique_id_mismatch(reason="wrong_switch")
                return self.async_update_reload_and_abort(entry, data_updates={CONF_TOKEN: token})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            description_placeholders={"host": entry.data[CONF_HOST]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> RTLPlaygroundOptionsFlow:
        return RTLPlaygroundOptionsFlow()


class RTLPlaygroundOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema({
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
            vol.Required(CONF_COUNTERS, default=options.get(CONF_COUNTERS, True)): bool,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
