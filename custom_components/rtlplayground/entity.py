"""Base entity of the RTLPlayground integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PortData, RTLPlaygroundCoordinator


def port_label(port: PortData) -> str:
    """'3', or '3 (NAS)' when the port has a name on the switch."""
    return f"{port.number} ({port.name})" if port.name else str(port.number)


class RTLPlaygroundEntity(CoordinatorEntity[RTLPlaygroundCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RTLPlaygroundCoordinator, key: str,
                 port: int | None = None) -> None:
        super().__init__(coordinator)
        self._port = port
        mac = format_mac(coordinator.config_entry.unique_id or "")
        self._attr_unique_id = f"{mac}_{key}" if port is None else f"{mac}_{key}_{port}"
        info = coordinator.data.info
        mgmt = info.get("ip_address")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            name=info.get("hostname") or "RTLPlayground",
            manufacturer=MANUFACTURER,
            model=info.get("hw_ver"),
            hw_version=info.get("pcb_ver"),
            sw_version=info.get("sw_ver"),
            configuration_url=f"http://{mgmt}/" if mgmt else None,
        )

    @property
    def port_data(self) -> PortData | None:
        if self._port is None or self.coordinator.data is None:
            return None
        return self.coordinator.data.ports.get(self._port)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return self._port is None or self.port_data is not None
