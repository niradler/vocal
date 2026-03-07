"""Shared fixtures for contract tests.

Contract tests start a real API server but do NOT download heavyweight models.
All tests use pyttsx3 (built-in, no download) for TTS and only exercise the
model-management endpoints for listing/info (no actual model loading).
"""
import subprocess
import sys
import time

import httpx
import pytest
import requests

from vocal_sdk import VocalClient

_BASE_URL = "http://localhost:8000"


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
    """Start API server once for the whole contract test session, or reuse if already running."""
    try:
        r = requests.get(f"{_BASE_URL}/health", timeout=2)
        if r.status_code == 200:
            yield _BASE_URL
            return
    except Exception:
        pass

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "vocal_api.main:app", "--port", "8000", "--log-level", "error"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if not _server_ready(_BASE_URL):
        proc.kill()
        pytest.fail("Contract test API server failed to start")

    yield _BASE_URL

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
