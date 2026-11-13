"""RTLPlayground switches through their read-only monitoring API."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RTLPlaygroundApi
from .coordinator import RTLPlaygroundConfigEntry, RTLPlaygroundCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: RTLPlaygroundConfigEntry) -> bool:
    api = RTLPlaygroundApi(async_get_clientsession(hass), entry.data[CONF_HOST],
                           entry.data[CONF_TOKEN])
    coordinator = RTLPlaygroundCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _options_updated(hass: HomeAssistant, entry: RTLPlaygroundConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RTLPlaygroundConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
