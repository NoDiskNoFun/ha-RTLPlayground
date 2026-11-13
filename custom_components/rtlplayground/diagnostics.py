"""Diagnostics download: what the switch reported, without the token."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import RTLPlaygroundConfigEntry

TO_REDACT = {CONF_TOKEN, "sfp_serial", "serial"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RTLPlaygroundConfigEntry
) -> dict[str, Any]:
    data = entry.runtime_data.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "information": data.info,
        "ports": async_redact_data({n: asdict(p) for n, p in data.ports.items()}, TO_REDACT),
    }
