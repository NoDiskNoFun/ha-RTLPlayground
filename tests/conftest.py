"""Fixtures: the firmware's web UI simulator (tools/httpd_sim.py) in API mode."""

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOKEN = "0123456789abcdef0123456789abcdef"
SIM = Path(__file__).parent / "httpd_sim.py"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def simulator(tmp_path, socket_enabled):
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(SIM), "--port", str(port), "--api-token", TOKEN],
        cwd=tmp_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield f"127.0.0.1:{port}"
    proc.terminate()
    proc.wait(5)
