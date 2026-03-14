"""Shared fixtures for contract tests.

Contract tests start a real API server but do NOT download heavyweight models.
All tests use pyttsx3 (built-in, no download) for TTS and only exercise the
model-management endpoints for listing/info (no actual model loading).
"""

import os
import socket
import subprocess
import sys
import tempfile
import time

import httpx
import pytest
import requests

from vocal_sdk import VocalClient


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _server_ready(url: str, retries: int = 60, delay: float = 0.5) -> bool:
    for _ in range(retries):
        try:
            r = requests.get(f"{url}/health", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False


@pytest.fixture(scope="session")
def api_server():
    """Start an isolated API server for the whole contract test session."""
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory() as tmpdir:
        env = os.environ.copy()
        env["VOCAL_MODEL_STORAGE_PATH"] = os.path.join(tmpdir, "models")

        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "vocal_api.main:app", "--port", str(port), "--log-level", "error"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        if not _server_ready(base_url):
            proc.kill()
            pytest.fail("Contract test API server failed to start")

        yield base_url

        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture(scope="session")
def client(api_server) -> VocalClient:
    return VocalClient(
        base_url=api_server,
        timeout=httpx.Timeout(30.0),
        raise_on_unexpected_status=True,
    )
