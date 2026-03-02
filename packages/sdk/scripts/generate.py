"""
Generate Python SDK from OpenAPI spec using openapi-python-client.

Produces a fully typed httpx async client with Pydantic models.

Usage:
    # API must be running first:  make serve
    uv run python packages/sdk/scripts/generate.py
    uv run python packages/sdk/scripts/generate.py --url http://localhost:8000/openapi.json
    uv run python packages/sdk/scripts/generate.py --path packages/sdk/openapi.json
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SDK_DIR = Path(__file__).parent.parent
VOCAL_SDK_DIR = SDK_DIR / "vocal_sdk"
CONFIG_FILE = SDK_DIR / "openapi-python-client-config.yaml"
DEFAULT_URL = "http://localhost:8000/openapi.json"

CONFIG_YAML = """\
project_name_override: vocal-sdk
package_name_override: vocal_sdk
use_path_prefixes_for_title_model_names: false
post_hooks:
  - "ruff check . --fix-only --unsafe-fixes"
  - "ruff format ."
"""

TEMPLATES_DIR = SDK_DIR / "templates"


def ensure_config() -> Path:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(CONFIG_YAML)
    return CONFIG_FILE


def run_generator(source_flag: str, source_value: str, out_dir: Path) -> None:
    # With --meta none the output-path IS the Python package directory directly.
    cmd = [
        sys.executable,
        "-m",
        "openapi_python_client",
        "generate",
        source_flag,
        source_value,
        "--output-path",
        str(out_dir),
        "--config",
        str(ensure_config()),
        "--custom-template-path",
        str(TEMPLATES_DIR),
        "--meta",
        "none",
        "--overwrite",
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print("\nGeneration failed — is the API server running? (make serve)")
        sys.exit(result.returncode)


COMPAT_PY = '''\
"""Backward-compatible VocalSDK wrapper around the generated VocalClient.

Provides the same dict-based interface as before for existing consumers.
New code should use VocalClient + the generated api.* functions directly.
"""

from pathlib import Path
from typing import Any, BinaryIO

import httpx

from .client import VocalClient


class VocalSDK:
    """Dict-based high-level client — backward-compatible wrapper over VocalClient."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 300.0) -> None:
        self._vc = VocalClient(base_url=base_url, timeout=httpx.Timeout(timeout))
        self.models = _ModelsAPI(self)
        self.audio = _AudioAPI(self)

    def _http(self) -> httpx.Client:
        return self._vc.get_httpx_client()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        r = self._http().request(method, path, **kwargs)
        r.raise_for_status()
        return r.json()

    def _request_raw(self, method: str, path: str, **kwargs: Any) -> bytes:
        r = self._http().request(method, path, **kwargs)
        r.raise_for_status()
        return r.content

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")


class _ModelsAPI:
    def __init__(self, sdk: VocalSDK) -> None:
        self._sdk = sdk

    def list(self, task: str | None = None, status: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if task:
            params["task"] = task
        if status:
            params["status"] = status
        return self._sdk._request("GET", "/v1/models", params=params)

    def get(self, model_id: str) -> dict[str, Any]:
        return self._sdk._request("GET", f"/v1/models/{model_id}")

    def download(self, model_id: str) -> dict[str, Any]:
        return self._sdk._request("POST", f"/v1/models/{model_id}/download")

    def download_status(self, model_id: str) -> dict[str, Any]:
        return self._sdk._request("GET", f"/v1/models/{model_id}/download/status")

    def delete(self, model_id: str) -> dict[str, Any]:
        return self._sdk._request("DELETE", f"/v1/models/{model_id}")


class _AudioAPI:
    def __init__(self, sdk: VocalSDK) -> None:
        self._sdk = sdk

    def transcribe(
        self,
        file: str | Path | BinaryIO,
        model: str = "Systran/faster-whisper-tiny",
        language: str | None = None,
        prompt: str | None = None,
        response_format: str = "json",
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if isinstance(file, (str, Path)):
            with open(file, "rb") as f:
                return self._transcribe(f, model, language, prompt, response_format, temperature, **kwargs)
        return self._transcribe(file, model, language, prompt, response_format, temperature, **kwargs)

    def _transcribe(self, fobj: BinaryIO, model: str, language: str | None, prompt: str | None,
                    response_format: str, temperature: float, **kwargs: Any) -> dict[str, Any]:
        data: dict[str, Any] = {"model": model, "response_format": response_format,
                                 "temperature": temperature, **kwargs}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        return self._sdk._request("POST", "/v1/audio/transcriptions", files={"file": fobj}, data=data)

    def translate(self, file: str | Path | BinaryIO, model: str = "Systran/faster-whisper-tiny",
                  **kwargs: Any) -> dict[str, Any]:
        if isinstance(file, (str, Path)):
            with open(file, "rb") as f:
                return self._sdk._request("POST", "/v1/audio/translations",
                                          files={"file": f}, data={"model": model, **kwargs})
        return self._sdk._request("POST", "/v1/audio/translations",
                                  files={"file": file}, data={"model": model, **kwargs})

    def text_to_speech(
        self,
        text: str,
        model: str = "pyttsx3",
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "mp3",
        stream: bool = False,
        output_file: str | Path | None = None,
    ) -> bytes:
        payload: dict[str, Any] = {"model": model, "input": text, "speed": speed,
                                    "response_format": response_format, "stream": stream}
        if voice:
            payload["voice"] = voice
        audio = self._sdk._request_raw("POST", "/v1/audio/speech", json=payload)
        if output_file:
            Path(output_file).write_bytes(audio)
        return audio

    def list_voices(self, model: str | None = None) -> dict[str, Any]:
        params = {"model": model} if model else {}
        return self._sdk._request("GET", "/v1/audio/voices", params=params)
'''


def sync_generated(generated_pkg: Path) -> None:
    if not generated_pkg.exists() or not any(generated_pkg.iterdir()):
        print(f"Generated package at {generated_pkg} is missing or empty.")
        sys.exit(1)

    version_line = ""
    init_file = VOCAL_SDK_DIR / "__init__.py"
    if init_file.exists():
        for line in init_file.read_text().splitlines():
            if line.startswith("__version__"):
                version_line = line
                break

    if VOCAL_SDK_DIR.exists():
        shutil.rmtree(VOCAL_SDK_DIR)

    shutil.copytree(generated_pkg, VOCAL_SDK_DIR)

    (VOCAL_SDK_DIR / "compat.py").write_text(COMPAT_PY, encoding="utf-8")

    init = VOCAL_SDK_DIR / "__init__.py"
    content = init.read_text(encoding="utf-8")
    if version_line and "__version__" not in content:
        content = f"{version_line}\n{content}"
    if "VocalSDK" not in content:
        content += '\nfrom .compat import VocalSDK\n\n__all__ = __all__ + ("VocalSDK",)\n'
    init.write_text(content, encoding="utf-8")

    subprocess.run(
        [sys.executable, "-m", "ruff", "format", str(VOCAL_SDK_DIR / "compat.py"), str(VOCAL_SDK_DIR / "__init__.py")],
        capture_output=True,
    )

    print(f"\nSDK generated at {VOCAL_SDK_DIR}")
    print("  client.py  - VocalClient / VocalAuthenticatedClient (httpx async + sync)")
    print("  compat.py  - VocalSDK (backward-compat dict-based wrapper)")
    print("  api/       - One module per endpoint tag")
    print("  models/    - Pydantic models from schema")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Vocal SDK from OpenAPI spec")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url", default=DEFAULT_URL, help="OpenAPI spec URL (default: %(default)s)")
    group.add_argument("--path", help="Path to local openapi.json file")
    args = parser.parse_args()

    if args.path:
        source_flag, source_value = "--path", str(Path(args.path).resolve())
        print(f"Generating SDK from local file: {source_value}")
    else:
        source_flag, source_value = "--url", args.url
        print(f"Generating SDK from: {source_value}")

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "vocal_sdk"
        run_generator(source_flag, source_value, out_dir)
        sync_generated(out_dir)

    print("\nNext steps:")
    print("  make lint   — verify generated code passes linting")
    print("  make test   — run full test suite")


if __name__ == "__main__":
    main()
