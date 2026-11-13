"""Base entity of the RTLPlayground integration.

The switch is one device. Every port is a device of its own, connected
through the switch, so renaming a port in Home Assistant renames all its
entities at once. Its default name is the port name set on the switch
(`port <n> name <text>`), or "Port <n>".
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import PortData, RTLPlaygroundCoordinator


def port_device_name(port: PortData) -> str:
    return port.name or f"Port {port.number}"


def switch_identifier(mac: str) -> tuple[str, str]:
    return (DOMAIN, mac)


def port_identifier(mac: str, number: int) -> tuple[str, str]:
    return (DOMAIN, f"{mac}_port_{number}")


class RTLPlaygroundEntity(CoordinatorEntity[RTLPlaygroundCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RTLPlaygroundCoordinator, key: str,
                 port: PortData | None = None) -> None:
        super().__init__(coordinator)
        self._port = None if port is None else port.number
        mac = format_mac(coordinator.config_entry.unique_id or "")
        info = coordinator.data.info
        if port is None:
            self._attr_unique_id = f"{mac}_{key}"
            mgmt = info.get("ip_address")
            self._attr_device_info = DeviceInfo(
                identifiers={switch_identifier(mac)},
                connections={(CONNECTION_NETWORK_MAC, mac)},
                name=info.get("hostname") or "RTLPlayground",
                manufacturer=MANUFACTURER,
                model=info.get("hw_ver"),
                hw_version=info.get("pcb_ver"),
                sw_version=info.get("sw_ver"),
                configuration_url=f"http://{mgmt}/" if mgmt else None,
            )
        else:
            self._attr_unique_id = f"{mac}_{key}_{port.number}"
            self._attr_device_info = DeviceInfo(
                identifiers={port_identifier(mac, port.number)},
                name=port_device_name(port),
                manufacturer=MANUFACTURER,
                model="SFP+ port" if port.is_sfp else "RJ45 port",
                via_device=switch_identifier(mac),
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
