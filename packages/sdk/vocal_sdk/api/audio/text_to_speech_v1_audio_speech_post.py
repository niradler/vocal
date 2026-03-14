from http import HTTPStatus
from typing import Any, cast

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.tts_request import TTSRequest


def _get_kwargs(
    *,
    body: TTSRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/audio/speech",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | HTTPValidationError | None:
    if response.status_code == 200:
        response_200 = cast(Any, None)
        return response_200

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if response.status_code == 503:
        response_503 = cast(Any, None)
        return response_503

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Any | HTTPValidationError]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: TTSRequest,
) -> Response[Any | HTTPValidationError]:
    """Text To Speech

     Generate speech from text (OpenAI-compatible endpoint).

    - **model**: TTS model (e.g., 'hexgrad/Kokoro-82M', 'pyttsx3')
    - **input**: Text to convert to speech
    - **voice**: Optional voice ID (use /v1/audio/voices to list available voices)
    - **speed**: Speech speed multiplier (0.25 to 4.0, default: 1.0)
    - **response_format**: Audio format (mp3, opus, aac, flac, wav, pcm)
    - **stream**: Stream audio chunks as they are generated

    Args:
        body (TTSRequest): Text-to-Speech request (OpenAI-compatible)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: TTSRequest,
) -> Any | HTTPValidationError | None:
    """Text To Speech

     Generate speech from text (OpenAI-compatible endpoint).

    - **model**: TTS model (e.g., 'hexgrad/Kokoro-82M', 'pyttsx3')
    - **input**: Text to convert to speech
    - **voice**: Optional voice ID (use /v1/audio/voices to list available voices)
    - **speed**: Speech speed multiplier (0.25 to 4.0, default: 1.0)
    - **response_format**: Audio format (mp3, opus, aac, flac, wav, pcm)
    - **stream**: Stream audio chunks as they are generated

    Args:
        body (TTSRequest): Text-to-Speech request (OpenAI-compatible)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: TTSRequest,
) -> Response[Any | HTTPValidationError]:
    """Text To Speech

     Generate speech from text (OpenAI-compatible endpoint).

    - **model**: TTS model (e.g., 'hexgrad/Kokoro-82M', 'pyttsx3')
    - **input**: Text to convert to speech
    - **voice**: Optional voice ID (use /v1/audio/voices to list available voices)
    - **speed**: Speech speed multiplier (0.25 to 4.0, default: 1.0)
    - **response_format**: Audio format (mp3, opus, aac, flac, wav, pcm)
    - **stream**: Stream audio chunks as they are generated

    Args:
        body (TTSRequest): Text-to-Speech request (OpenAI-compatible)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | HTTPValidationError]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: TTSRequest,
) -> Any | HTTPValidationError | None:
    """Text To Speech

     Generate speech from text (OpenAI-compatible endpoint).

    - **model**: TTS model (e.g., 'hexgrad/Kokoro-82M', 'pyttsx3')
    - **input**: Text to convert to speech
    - **voice**: Optional voice ID (use /v1/audio/voices to list available voices)
    - **speed**: Speech speed multiplier (0.25 to 4.0, default: 1.0)
    - **response_format**: Audio format (mp3, opus, aac, flac, wav, pcm)
    - **stream**: Stream audio chunks as they are generated

    Args:
        body (TTSRequest): Text-to-Speech request (OpenAI-compatible)

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | HTTPValidationError
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
