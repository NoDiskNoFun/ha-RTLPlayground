"""Sensors of an RTLPlayground switch."""

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
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LINK_OPTIONS
from .coordinator import PortData, RTLPlaygroundConfigEntry, RTLPlaygroundCoordinator, SwitchData, parse_temp
from .entity import RTLPlaygroundEntity, port_label


@dataclass(frozen=True, kw_only=True)
class SwitchSensorDescription(SensorEntityDescription):
    value: Callable[[SwitchData], Any]


@dataclass(frozen=True, kw_only=True)
class PortSensorDescription(SensorEntityDescription):
    value: Callable[[PortData], Any]
    sfp_only: bool = False
    counters: bool = False


SWITCH_SENSORS: tuple[SwitchSensorDescription, ...] = (
    SwitchSensorDescription(
        key="chip_temperature",
        translation_key="chip_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda d: parse_temp(d.info.get("chip_temp")),
    ),
    SwitchSensorDescription(
        key="boot_time",
        translation_key="boot_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda d: d.boot_time,
    ),
)

PORT_SENSORS: tuple[PortSensorDescription, ...] = (
    PortSensorDescription(
        key="link",
        translation_key="link",
        device_class=SensorDeviceClass.ENUM,
        options=LINK_OPTIONS,
        value=lambda p: p.link,
    ),
    PortSensorDescription(
        key="rx_rate",
        translation_key="rx_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
        counters=True,
        value=lambda p: p.rx_rate,
    ),
    PortSensorDescription(
        key="tx_rate",
        translation_key="tx_rate",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.BITS_PER_SECOND,
        suggested_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
        counters=True,
        value=lambda p: p.tx_rate,
    ),
    PortSensorDescription(
        key="rx_bytes",
        translation_key="rx_bytes",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        counters=True,
        value=lambda p: p.rx_bytes,
    ),
    PortSensorDescription(
        key="tx_bytes",
        translation_key="tx_bytes",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        counters=True,
        value=lambda p: p.tx_bytes,
    ),
    PortSensorDescription(
        key="rx_errors",
        translation_key="rx_errors",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda p: p.rx_errors,
    ),
    PortSensorDescription(
        key="tx_errors",
        translation_key="tx_errors",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda p: p.tx_errors,
    ),
    PortSensorDescription(
        key="macs",
        translation_key="macs",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda p: p.macs,
    ),
    PortSensorDescription(
        key="sfp_module",
        translation_key="sfp_module",
        entity_category=EntityCategory.DIAGNOSTIC,
        sfp_only=True,
        value=lambda p: p.sfp.get("module"),
    ),
    PortSensorDescription(
        key="sfp_temperature",
        translation_key="sfp_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        sfp_only=True,
        value=lambda p: p.sfp.get("temperature"),
    ),
    PortSensorDescription(
        key="sfp_rx_power",
        translation_key="sfp_rx_power",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        sfp_only=True,
        value=lambda p: p.sfp.get("rxpower"),
    ),
    PortSensorDescription(
        key="sfp_tx_power",
        translation_key="sfp_tx_power",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        sfp_only=True,
        value=lambda p: p.sfp.get("txpower"),
    ),
    PortSensorDescription(
        key="sfp_voltage",
        translation_key="sfp_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        sfp_only=True,
        value=lambda p: p.sfp.get("voltage"),
    ),
    PortSensorDescription(
        key="sfp_tx_bias",
        translation_key="sfp_tx_bias",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        sfp_only=True,
        value=lambda p: p.sfp.get("tx_bias"),
    ),
)


async def async_setup_entry(hass: HomeAssistant, entry: RTLPlaygroundConfigEntry,
                            async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    mac = format_mac(entry.unique_id or "")
    entities: list[SensorEntity] = [
        RTLPlaygroundSwitchSensor(coordinator, d) for d in SWITCH_SENSORS
    ]
    for port in coordinator.data.ports.values():
        for d in PORT_SENSORS:
            if d.sfp_only and not port.is_sfp:
                continue
            if d.counters and not coordinator.counters_enabled:
                # Switched off in the options: no leftovers either
                stale = registry.async_get_entity_id("sensor", DOMAIN, f"{mac}_{d.key}_{port.number}")
                if stale:
                    registry.async_remove(stale)
                continue
            entities.append(RTLPlaygroundPortSensor(coordinator, d, port))
    async_add_entities(entities)


class RTLPlaygroundSwitchSensor(RTLPlaygroundEntity, SensorEntity):
    entity_description: SwitchSensorDescription

    def __init__(self, coordinator: RTLPlaygroundCoordinator,
                 description: SwitchSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator.data)


class RTLPlaygroundPortSensor(RTLPlaygroundEntity, SensorEntity):
    entity_description: PortSensorDescription

    def __init__(self, coordinator: RTLPlaygroundCoordinator,
                 description: PortSensorDescription, port: PortData) -> None:
        super().__init__(coordinator, description.key, port.number)
        self.entity_description = description
        self._attr_translation_placeholders = {"port": port_label(port)}

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        # An empty SFP slot has nothing to report
        if self.entity_description.sfp_only:
            return self.native_value is not None
        return True

    @property
    def native_value(self) -> Any:
        port = self.port_data
        return None if port is None else self.entity_description.value(port)
