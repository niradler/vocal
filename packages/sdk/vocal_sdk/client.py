"""
Vocal SDK - Auto-generated client for Vocal API

This SDK provides a clean Python interface to the Vocal API.
Models are auto-generated from the OpenAPI spec.
"""

from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import urljoin

import requests


class VocalSDK:
    """
    Vocal SDK Client

    Example:
        >>> from vocal_sdk import VocalSDK
        >>> client = VocalSDK(base_url="http://localhost:8000")
        >>>
        >>> # List models
        >>> models = client.models.list()
        >>> print(f"Found {len(models['models'])} models")
        >>>
        >>> # Transcribe audio
        >>> result = client.audio.transcribe("recording.mp3")
        >>> print(result['text'])
        >>>
        >>> # Text to speech
        >>> audio = client.audio.text_to_speech("Hello, world!")
        >>> with open("output.wav", "wb") as f:
        >>>     f.write(audio)
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 300):
        """
        Initialize Vocal SDK

        Args:
            base_url: Base URL of Vocal API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

        # Namespaced APIs
        self.models = ModelsAPI(self)
        self.audio = AudioAPI(self)

    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request to API"""
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))

        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()

        return response.json()

    def _request_raw(self, method: str, endpoint: str, **kwargs) -> bytes:
        """Make HTTP request and return raw bytes"""
        url = urljoin(self.base_url + "/", endpoint.lstrip("/"))

        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()

        return response.content

    def health(self) -> dict[str, Any]:
        """Check API health"""
        return self._request("GET", "/health")


class ModelsAPI:
    """Models API namespace"""

    def __init__(self, client: VocalSDK):
        self.client = client

    def list(self, status: str | None = None, task: str | None = None) -> dict[str, Any]:
        """
        List all available models

        Args:
            status: Filter by status (available, downloading, not_downloaded)
            task: Filter by task (stt, tts)

        Returns:
            Dictionary with 'models' list and 'total' count
        """
        params = {}
        if status:
            params["status"] = status
        if task:
            params["task"] = task

        return self.client._request("GET", "/v1/models", params=params)

    def get(self, model_id: str) -> dict[str, Any]:
        """
        Get model information

        Args:
            model_id: Model identifier (e.g., "Systran/faster-whisper-tiny")

        Returns:
            Model information dictionary
        """
        return self.client._request("GET", f"/v1/models/{model_id}")

    def download(self, model_id: str, quantization: str | None = None) -> dict[str, Any]:
        """
        Download a model (Ollama-style pull)

        Args:
            model_id: Model identifier
            quantization: Optional quantization format

        Returns:
            Download progress information
        """
        data = {}
        if quantization:
            data["quantization"] = quantization

        return self.client._request("POST", f"/v1/models/{model_id}/download", json=data if data else None)

    def download_status(self, model_id: str) -> dict[str, Any]:
        """
        Check download status for a model

        Args:
            model_id: Model identifier

        Returns:
            Download status information
        """
        return self.client._request("GET", f"/v1/models/{model_id}/download/status")

    def delete(self, model_id: str) -> dict[str, Any]:
        """
        Delete a downloaded model

        Args:
            model_id: Model identifier

        Returns:
            Deletion confirmation
        """
        return self.client._request("DELETE", f"/v1/models/{model_id}")


class AudioAPI:
    """Audio API namespace"""

    def __init__(self, client: VocalSDK):
        self.client = client

    def transcribe(
        self,
        file: str | Path | BinaryIO,
        model: str = "Systran/faster-whisper-tiny",
        language: str | None = None,
        response_format: str = "json",
        temperature: float = 0.0,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Transcribe audio to text

        Args:
            file: Path to audio file or file-like object
            model: Model to use for transcription
            language: Language code (e.g., "en", "es") or None for auto-detect
            response_format: Output format (json, text, srt, vtt)
            temperature: Sampling temperature (0.0-1.0)
            **kwargs: Additional parameters

        Returns:
            Transcription result with text, language, duration, segments

        Example:
            >>> result = client.audio.transcribe("audio.mp3")
            >>> print(result['text'])
            >>> print(f"Language: {result['language']}")
        """
        if isinstance(file, (str, Path)):
            with open(file, "rb") as f:
                return self._transcribe_file(f, model, language, response_format, temperature, **kwargs)
        else:
            return self._transcribe_file(file, model, language, response_format, temperature, **kwargs)

    def _transcribe_file(
        self,
        file_obj: BinaryIO,
        model: str,
        language: str | None,
        response_format: str,
        temperature: float,
        **kwargs,
    ) -> dict[str, Any]:
        """Internal method to transcribe file object"""
        files = {"file": file_obj}
        data = {
            "model": model,
            "response_format": response_format,
            "temperature": temperature,
            **kwargs,
        }

        if language:
            data["language"] = language

        return self.client._request("POST", "/v1/audio/transcriptions", files=files, data=data)

    def translate(
        self,
        file: str | Path | BinaryIO,
        model: str = "Systran/faster-whisper-tiny",
        **kwargs,
    ) -> dict[str, Any]:
        """
        Translate audio to English

        Args:
            file: Path to audio file or file-like object
            model: Model to use for translation
            **kwargs: Additional parameters

        Returns:
            Translation result
        """
        if isinstance(file, (str, Path)):
            with open(file, "rb") as f:
                files = {"file": f}
                data = {"model": model, **kwargs}
                return self.client._request("POST", "/v1/audio/translations", files=files, data=data)
        else:
            files = {"file": file}
            data = {"model": model, **kwargs}
            return self.client._request("POST", "/v1/audio/translations", files=files, data=data)

    def text_to_speech(
        self,
        text: str,
        voice: str | None = None,
        speed: float = 1.0,
        response_format: str = "wav",
        output_file: str | Path | None = None,
    ) -> bytes:
        """
        Convert text to speech (TTS)

        Args:
            text: Text to convert to speech
            voice: Voice ID to use (None for default)
            speed: Speech speed multiplier (0.25 to 4.0)
            response_format: Audio format (currently only 'wav' supported)
            output_file: Optional path to save audio file

        Returns:
            Audio data as bytes

        Example:
            >>> audio = client.audio.text_to_speech("Hello, world!")
            >>> with open("output.wav", "wb") as f:
            >>>     f.write(audio)

            >>> # Or save directly
            >>> client.audio.text_to_speech("Hello!", output_file="hello.wav")
        """
        data = {
            "input": text,
            "speed": speed,
            "response_format": response_format,
        }

        if voice:
            data["voice"] = voice

        audio_data = self.client._request_raw("POST", "/v1/audio/speech", json=data)

        if output_file:
            output_path = Path(output_file)
            output_path.write_bytes(audio_data)

        return audio_data

    def list_voices(self) -> dict[str, Any]:
        """
        List available TTS voices

        Returns:
            Dictionary with 'voices' list and 'total' count

        Example:
            >>> voices = client.audio.list_voices()
            >>> for voice in voices['voices']:
            >>>     print(f"{voice['id']}: {voice['name']} ({voice['language']})")
        """
        return self.client._request("GET", "/v1/audio/voices")


__all__ = ["VocalSDK", "ModelsAPI", "AudioAPI"]
