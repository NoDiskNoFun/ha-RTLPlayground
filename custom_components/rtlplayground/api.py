"""Client for the read-only monitoring API of the RTLPlayground firmware.

The switch answers in its API VLAN with plain HTTP/1.1, closes the connection
after every response and handles one TCP connection at a time, so requests
are sent one after the other with "Connection: close".
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=10)


class RTLPlaygroundError(Exception):
    """The switch could not be reached or answered something unusable."""


class RTLPlaygroundAuthError(RTLPlaygroundError):
    """The token was refused."""


class RTLPlaygroundApi:
    """Reads the JSON status pages of one switch."""

    def __init__(self, session: aiohttp.ClientSession, host: str, token: str) -> None:
        self._session = session
        self._host = host.strip().rstrip("/")
        if "://" not in self._host:
            self._host = f"http://{self._host}"
        self._token = token.strip()
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    async def _get(self, path: str) -> Any:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Connection": "close",
            "Accept": "application/json",
        }
        async with self._lock:
            try:
                async with self._session.get(
                    f"{self._host}{path}", headers=headers, timeout=TIMEOUT
                ) as resp:
                    if resp.status == 401:
                        raise RTLPlaygroundAuthError("token refused")
                    if resp.status != 200:
                        raise RTLPlaygroundError(f"{path}: HTTP {resp.status}")
                    raw = await resp.read()
            except RTLPlaygroundError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise RTLPlaygroundError(f"{path}: {err}") from err
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except ValueError as err:
            raise RTLPlaygroundError(f"{path}: invalid JSON") from err

    async def information(self) -> dict[str, Any]:
        data = await self._get("/information.json")
        if not isinstance(data, dict):
            raise RTLPlaygroundError("information.json: not an object")
        return data

    async def ports(self) -> list[dict[str, Any]]:
        return _as_list(await self._get("/ports.json"), "ports.json")

    async def traffic(self) -> list[dict[str, Any]]:
        return _as_list(await self._get("/traffic.json"), "traffic.json")

    async def counters(self, port: int) -> list[int]:
        """The MIB counters of one port, see doc/api.md (counters)."""
        data = _as_list(await self._get(f"/counters.json?port={port}"), "counters.json")
        return [hex_int(v) for v in data]


def _as_list(data: Any, name: str) -> list:
    if not isinstance(data, list):
        raise RTLPlaygroundError(f"{name}: not a list")
    return data


def hex_int(value: Any) -> int | None:
    """Numbers come as "0x..." strings."""
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    try:
        return int(value, 16) if value.lower().startswith("0x") else int(value)
    except ValueError:
        return None
