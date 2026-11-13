"""Polls the switch through its read-only monitoring API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import math
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import RTLPlaygroundApi, RTLPlaygroundAuthError, RTLPlaygroundError, hex_int
from .const import (
    CONF_COUNTERS,
    COUNTER_IN_OCTETS,
    COUNTER_OUT_OCTETS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LINK_STATES,
)

_LOGGER = logging.getLogger(__name__)

type RTLPlaygroundConfigEntry = ConfigEntry[RTLPlaygroundCoordinator]


@dataclass
class PortData:
    """What the switch reports about one physical port."""

    number: int
    name: str = ""
    is_sfp: bool = False
    link: str | None = None          # a LINK_STATES value
    tx_frames: int | None = None
    rx_frames: int | None = None
    tx_errors: int | None = None
    rx_errors: int | None = None
    macs: int | None = None
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    rx_rate: float | None = None     # bit/s
    tx_rate: float | None = None
    sfp: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwitchData:
    info: dict[str, Any]
    ports: dict[int, PortData]
    boot_time: datetime | None = None


def parse_temp(text: Any) -> float | None:
    """'47.3 C' -> 47.3"""
    if not isinstance(text, str):
        return None
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def sfp_values(port: dict[str, Any]) -> dict[str, Any]:
    """Digital diagnostics of an SFP module (SFF-8472, internally calibrated).

    Empty if the slot is empty or the module has no diagnostics. Modules that
    are externally calibrated would need their calibration constants applied,
    so their raw readings are not reported."""
    out: dict[str, Any] = {}
    model = port.get("sfp_model")
    if model is None:
        return out
    vendor = (port.get("sfp_vendor") or "").strip()
    out["module"] = " ".join(x for x in (vendor, model.strip()) if x) or None
    out["serial"] = (port.get("sfp_serial") or "").strip() or None
    options = hex_int(port.get("sfp_options")) or 0
    if not options & 0x40 or options & 0x10 or "sfp_temp" not in port:
        return out

    temp = hex_int(port.get("sfp_temp"))
    if temp is not None:
        if temp >= 0x8000:
            temp -= 0x10000
        out["temperature"] = round(temp / 256, 1)
    vcc = hex_int(port.get("sfp_vcc"))
    if vcc is not None:
        out["voltage"] = round(vcc / 10000, 3)
    bias = hex_int(port.get("sfp_txbias"))
    if bias is not None:
        out["tx_bias"] = round(bias * 0.002, 2)
    for key in ("txpower", "rxpower"):
        raw = hex_int(port.get(f"sfp_{key}"))
        if raw is not None:
            # 0.1 uW units; no light at all reads 0, shown as -40 dBm
            mw = raw / 10000
            out[key] = round(10 * math.log10(mw), 2) if mw > 0 else -40.0
    return out


def link_state(text: Any) -> str | None:
    if not isinstance(text, str):
        return None
    # The simulator adds a duplex suffix, the firmware does not
    return LINK_STATES.get(text.split("-")[0].upper())


class RTLPlaygroundCoordinator(DataUpdateCoordinator[SwitchData]):
    """One poll: information.json, ports.json, traffic.json and, if enabled,
    counters.json of every port, one request after the other."""

    config_entry: RTLPlaygroundConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RTLPlaygroundConfigEntry,
                 api: RTLPlaygroundApi) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.api = api
        self._last_bytes: dict[int, tuple[float, int | None, int | None]] = {}

    @property
    def counters_enabled(self) -> bool:
        return self.config_entry.options.get(CONF_COUNTERS, True)

    async def _async_update_data(self) -> SwitchData:
        try:
            info = await self.api.information()
            ports_raw = await self.api.ports()
            traffic = await self.api.traffic()
            ports: dict[int, PortData] = {}
            for p in ports_raw:
                n = p.get("port")
                if not isinstance(n, int):
                    continue
                ports[n] = PortData(
                    number=n,
                    name=str(p.get("name") or ""),
                    is_sfp=bool(p.get("isSFP")),
                    sfp=sfp_values(p) if p.get("isSFP") else {},
                )
            for t in traffic:
                port = ports.get(t.get("port"))
                if port is None:
                    continue
                port.link = link_state(t.get("link"))
                port.tx_frames = hex_int(t.get("txG"))
                port.rx_frames = hex_int(t.get("rxG"))
                port.tx_errors = hex_int(t.get("txB"))
                port.rx_errors = hex_int(t.get("rxB"))
                port.macs = hex_int(t.get("macs"))
            if self.counters_enabled:
                for n, port in ports.items():
                    counters = await self.api.counters(n)
                    if len(counters) > COUNTER_OUT_OCTETS:
                        port.rx_bytes = counters[COUNTER_IN_OCTETS]
                        port.tx_bytes = counters[COUNTER_OUT_OCTETS]
                    self._rates(port)
        except RTLPlaygroundAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except RTLPlaygroundError as err:
            raise UpdateFailed(str(err)) from err

        return SwitchData(info=info, ports=ports, boot_time=self._boot_time(info))

    def _rates(self, port: PortData) -> None:
        """Throughput from the difference of the byte counters."""
        now = time.monotonic()
        last = self._last_bytes.get(port.number)
        self._last_bytes[port.number] = (now, port.rx_bytes, port.tx_bytes)
        if last is None:
            return
        dt = now - last[0]
        if dt <= 0:
            return
        for attr, old, new in (("rx_rate", last[1], port.rx_bytes),
                               ("tx_rate", last[2], port.tx_bytes)):
            # A counter that went backwards was reset (reboot): no rate
            if old is not None and new is not None and new >= old:
                setattr(port, attr, round((new - old) * 8 / dt, 1))

    def _boot_time(self, info: dict[str, Any]) -> datetime | None:
        uptime = hex_int(info.get("uptime"))
        if uptime is None:
            return None
        boot = dt_util.utcnow() - timedelta(seconds=uptime)
        previous = self.data.boot_time if self.data else None
        # Keep the value steady: polling jitter is not a reboot
        if previous is not None and abs((boot - previous).total_seconds()) < 60:
            return previous
        return boot.replace(microsecond=0)
