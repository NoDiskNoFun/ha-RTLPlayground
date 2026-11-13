"""Link state of the ports of an RTLPlayground switch."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PortData, RTLPlaygroundConfigEntry, RTLPlaygroundCoordinator
from .entity import RTLPlaygroundEntity


async def async_setup_entry(hass: HomeAssistant, entry: RTLPlaygroundConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        RTLPlaygroundLinkSensor(coordinator, port)
        for port in coordinator.data.ports.values()
    )


class RTLPlaygroundLinkSensor(RTLPlaygroundEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "port_up"

    def __init__(self, coordinator: RTLPlaygroundCoordinator, port: PortData) -> None:
        super().__init__(coordinator, "port_up", port)

    @property
    def is_on(self) -> bool | None:
        port = self.port_data
        if port is None or port.link is None:
            return None
        return port.link != "down"
