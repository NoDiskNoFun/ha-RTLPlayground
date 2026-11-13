"""RTLPlayground switches through their read-only monitoring API."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RTLPlaygroundApi
from .coordinator import RTLPlaygroundConfigEntry, RTLPlaygroundCoordinator
from .entity import port_device_name, port_identifier

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: RTLPlaygroundConfigEntry) -> bool:
    api = RTLPlaygroundApi(async_get_clientsession(hass), entry.data[CONF_HOST],
                           entry.data[CONF_TOKEN])
    coordinator = RTLPlaygroundCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _sync_port_names() -> None:
        """A port named or renamed on the switch renames its device. A name
        given in Home Assistant is kept: it overrides the device name."""
        if coordinator.data is None:
            return
        registry = dr.async_get(hass)
        mac = dr.format_mac(entry.unique_id or "")
        for port in coordinator.data.ports.values():
            device = registry.async_get_device(identifiers={port_identifier(mac, port.number)})
            name = port_device_name(port)
            if device is not None and device.name != name:
                registry.async_update_device(device.id, name=name)

    _sync_port_names()
    entry.async_on_unload(coordinator.async_add_listener(_sync_port_names))
    return True


async def _options_updated(hass: HomeAssistant, entry: RTLPlaygroundConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RTLPlaygroundConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
