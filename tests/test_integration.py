"""Config flow and entities against the firmware simulator."""

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: F401
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rtlplayground.api import RTLPlaygroundApi, RTLPlaygroundAuthError
from custom_components.rtlplayground.const import DOMAIN
from custom_components.rtlplayground.coordinator import sfp_values
from custom_components.rtlplayground.diagnostics import async_get_config_entry_diagnostics

from .conftest import TOKEN

MAC = "1c:2a:a3:23:00:02"


async def _flow(hass, host, token):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: host, CONF_TOKEN: token})


async def test_flow_creates_entry(hass: HomeAssistant, simulator) -> None:
    result = await _flow(hass, simulator, TOKEN.upper())
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RTLPlayground-sim"
    assert result["data"] == {CONF_HOST: simulator, CONF_TOKEN: TOKEN}
    assert result["result"].unique_id == MAC


async def test_flow_errors(hass: HomeAssistant, simulator) -> None:
    result = await _flow(hass, simulator, "f" * 32)
    assert result["errors"] == {"base": "invalid_auth"}
    result = await _flow(hass, simulator, "nope")
    assert result["errors"] == {CONF_TOKEN: "invalid_token"}
    result = await _flow(hass, "127.0.0.1:1", TOKEN)
    assert result["errors"] == {"base": "cannot_connect"}


async def _setup(hass, simulator, options=None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MAC, title="sim",
                            data={CONF_HOST: simulator, CONF_TOKEN: TOKEN},
                            options=options or {})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities(hass: HomeAssistant, simulator) -> None:
    entry = await _setup(hass, simulator)
    assert entry.state is config_entries.ConfigEntryState.LOADED

    temp = hass.states.get("sensor.rtlplayground_sim_chip_temperature")
    assert temp is not None and 40 <= float(temp.state) <= 80
    assert temp.attributes["unit_of_measurement"] == "°C"

    # The simulator: odd ports linked, port 1 at 10G, port 6 an SFP slot
    assert hass.states.get("binary_sensor.port_1_connected").state == "on"
    assert hass.states.get("binary_sensor.port_2_connected").state == "off"
    assert hass.states.get("sensor.port_1_link_speed").state == "10g"
    assert hass.states.get("sensor.port_2_link_speed").state == "down"
    assert hass.states.get("sensor.port_3_link_speed").state == "100m"

    sfp = hass.states.get("sensor.port_6_sfp_temperature")
    assert sfp is not None and 40 <= float(sfp.state) <= 42
    assert hass.states.get("sensor.port_6_sfp_module").state == "OEM 10G-SFP+"
    assert float(hass.states.get("sensor.port_6_sfp_transmit_power").state) < 0
    # rx power 0 in the simulator: no light
    assert float(hass.states.get("sensor.port_6_sfp_receive_power").state) == -40.0
    assert hass.states.get("sensor.port_1_sfp_temperature") is None

    assert hass.states.get("sensor.rtlplayground_sim_last_boot") is not None

    # Throughput after a second poll
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data.ports[1].rx_bytes is not None
    rate = hass.states.get("sensor.port_1_receive_rate")
    assert rate is not None and rate.state not in ("unknown", "unavailable")

    reg = er.async_get(hass)
    rx = reg.async_get("sensor.port_1_received")
    assert rx is not None and rx.disabled_by is not None


async def test_counters_off(hass: HomeAssistant, simulator) -> None:
    await _setup(hass, simulator, {"counters": False, "scan_interval": 30})
    assert hass.states.get("sensor.port_1_receive_rate") is None
    assert hass.states.get("sensor.port_1_link_speed") is not None


async def test_wrong_token_starts_reauth(hass: HomeAssistant, simulator) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MAC, title="sim",
                            data={CONF_HOST: simulator, CONF_TOKEN: "e" * 32})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert any(f["context"]["source"] == config_entries.SOURCE_REAUTH for f in flows)

    flow = next(f for f in flows if f["context"]["source"] == config_entries.SOURCE_REAUTH)
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {CONF_TOKEN: TOKEN})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == TOKEN


async def test_diagnostics_redact_token(hass: HomeAssistant, simulator) -> None:
    entry = await _setup(hass, simulator)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert TOKEN not in str(diag)
    assert diag["information"]["api"]["token_set"] is True


async def test_api_is_read_only(simulator) -> None:
    """What the integration talks to refuses anything but reading."""
    async with aiohttp.ClientSession() as session:
        hdr = {"Authorization": f"Bearer {TOKEN}"}
        async with session.post(f"http://{simulator}/cmd", data="api off", headers=hdr) as r:
            assert r.status == 405
        async with session.get(f"http://{simulator}/cmd_log", headers=hdr) as r:
            assert r.status == 404
        api = RTLPlaygroundApi(session, simulator, "0" * 32)
        with pytest.raises(RTLPlaygroundAuthError):
            await api.information()


def test_sfp_conversion() -> None:
    v = sfp_values({"sfp_vendor": "FS", "sfp_model": "SFP-10GSR-85", "sfp_options": "0x68",
                    "sfp_temp": "0x2640", "sfp_vcc": "0x83bd", "sfp_txbias": "0x0bb8",
                    "sfp_txpower": "0x1390", "sfp_rxpower": "0x09c0"})
    assert v["module"] == "FS SFP-10GSR-85"
    assert v["temperature"] == 38.2          # 0x2640 / 256 = 38.25
    assert v["voltage"] == 3.373             # 0x83bd * 100 uV
    assert v["tx_bias"] == 6.0               # 0x0bb8 * 2 uA
    assert v["txpower"] == -3.0              # 5008 * 0.1 uW = 0.5008 mW
    assert v["rxpower"] == -6.03             # 2496 * 0.1 uW = 0.2496 mW
    # Negative temperatures are two's complement
    assert sfp_values({"sfp_model": "x", "sfp_options": "0x68", "sfp_temp": "0xfb00"})["temperature"] == -5.0
    # Externally calibrated: raw values are not reported
    assert "temperature" not in sfp_values({"sfp_model": "x", "sfp_options": "0x58", "sfp_temp": "0x2640"})
    # Empty slot
    assert sfp_values({"isSFP": True, "enabled": False}) == {}


async def test_options_flow(hass: HomeAssistant, simulator) -> None:
    entry = await _setup(hass, simulator)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"scan_interval": 60, "counters": False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval.total_seconds() == 60
    assert hass.states.get("sensor.port_1_receive_rate") is None


async def test_firmware_wire_format(socket_enabled) -> None:
    """The firmware answers HTTP/1.1 without Content-Length and closes the
    connection; a refused token gets its exact 401."""
    import asyncio

    async def handle(reader, writer):
        req = await reader.readuntil(b"\r\n\r\n")
        if f"Bearer {TOKEN}".encode() in req:
            writer.write(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Type: application/json\r\n\r\n"
                         b'{"mac_address":"1c:2a:a3:23:00:02","chip_temp":"47.3 C"}')
        else:
            writer.write(b"HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Bearer\r\n"
                         b"Connection: close\r\nContent-Length: 0\r\n\r\n")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    host = "127.0.0.1:%d" % server.sockets[0].getsockname()[1]
    async with server, aiohttp.ClientSession() as session:
        info = await RTLPlaygroundApi(session, host, TOKEN).information()
        assert info["chip_temp"] == "47.3 C"
        with pytest.raises(RTLPlaygroundAuthError):
            await RTLPlaygroundApi(session, host, "1" * 32).information()



async def _switch_cmd(simulator, cmd: str) -> None:
    """A command through the management web interface of the simulator."""
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
        async with session.post(f"http://{simulator}/login", data={"pwd": "1234"},
                                allow_redirects=False) as r:
            await r.read()
        async with session.post(f"http://{simulator}/cmd", data=cmd) as r:
            assert r.status == 200
            await r.read()


async def test_port_devices_and_names(hass: HomeAssistant, simulator) -> None:
    """Every port is a device; naming it names all its entities."""
    from homeassistant.helpers import device_registry as dr

    # A name set on the switch before setup
    await _switch_cmd(simulator, "port 1 name NAS")

    entry = await _setup(hass, simulator)
    devices = dr.async_get(hass)
    switch = devices.async_get_device(identifiers={(DOMAIN, MAC)})
    port1 = devices.async_get_device(identifiers={(DOMAIN, f"{MAC}_port_1")})
    port2 = devices.async_get_device(identifiers={(DOMAIN, f"{MAC}_port_2")})
    assert port1.name == "NAS" and port2.name == "Port 2"
    assert port1.via_device_id == switch.id
    assert hass.states.get("sensor.nas_link_speed").name == "NAS Link speed"
    assert hass.states.get("binary_sensor.nas_connected").name == "NAS Connected"

    # Renamed in Home Assistant: every entity of the port follows
    devices.async_update_device(port2.id, name_by_user="Drucker")
    await hass.async_block_till_done()
    ents = er.async_entries_for_device(er.async_get(hass), port2.id)
    assert len(ents) > 3
    for e in ents:
        state = hass.states.get(e.entity_id)
        if state is not None:
            assert state.name.startswith("Drucker ")

    # Renamed on the switch: picked up at the next poll
    await _switch_cmd(simulator, "port 1 name Server")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert devices.async_get(port1.id).name == "Server"
    assert hass.states.get("sensor.nas_link_speed").name == "Server Link speed"
