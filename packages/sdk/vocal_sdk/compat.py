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

    def list_supported(self) -> dict[str, Any]:
        return self._sdk._request("GET", "/v1/models/supported")

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

    def _transcribe(self, fobj: BinaryIO, model: str, language: str | None, prompt: str | None, response_format: str, temperature: float, **kwargs: Any) -> dict[str, Any]:
        data: dict[str, Any] = {"model": model, "response_format": response_format, "temperature": temperature, **kwargs}
        if language:
            data["language"] = language
        if prompt:
            data["prompt"] = prompt
        return self._sdk._request("POST", "/v1/audio/transcriptions", files={"file": fobj}, data=data)

    def translate(self, file: str | Path | BinaryIO, model: str = "Systran/faster-whisper-tiny", **kwargs: Any) -> dict[str, Any]:
        if isinstance(file, (str, Path)):
            with open(file, "rb") as f:
                return self._sdk._request("POST", "/v1/audio/translations", files={"file": f}, data={"model": model, **kwargs})
        return self._sdk._request("POST", "/v1/audio/translations", files={"file": file}, data={"model": model, **kwargs})

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
        payload: dict[str, Any] = {"model": model, "input": text, "speed": speed, "response_format": response_format, "stream": stream}
        if voice:
            payload["voice"] = voice
        audio = self._sdk._request_raw("POST", "/v1/audio/speech", json=payload)
        if output_file:
            Path(output_file).write_bytes(audio)
        return audio

    def list_voices(self, model: str | None = None) -> dict[str, Any]:
        params = {"model": model} if model else {}
        return self._sdk._request("GET", "/v1/audio/voices", params=params)

    def clone_voice(
        self,
        text: str,
        reference_audio: str | Path | BinaryIO,
        model: str = "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
        reference_text: str | None = None,
        language: str = "en",
        response_format: str = "wav",
        output_file: str | Path | None = None,
    ) -> bytes:
        data: dict[str, Any] = {
            "text": text,
            "model": model,
            "language": language,
            "response_format": response_format,
        }
        if reference_text:
            data["reference_text"] = reference_text

        if isinstance(reference_audio, (str, Path)):
            with open(reference_audio, "rb") as f:
                audio = self._sdk._request_raw(
                    "POST",
                    "/v1/audio/clone",
                    files={"reference_audio": f},
                    data=data,
                )
        else:
            audio = self._sdk._request_raw(
                "POST",
                "/v1/audio/clone",
                files={"reference_audio": reference_audio},
                data=data,
            )

        if output_file:
            Path(output_file).write_bytes(audio)
        return audio
