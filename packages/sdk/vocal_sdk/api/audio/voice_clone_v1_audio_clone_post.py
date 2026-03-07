from http import HTTPStatus
from typing import Any, cast

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response
from ... import errors

from ...models.body_voice_clone_v1_audio_clone_post import (
    BodyVoiceCloneV1AudioClonePost,
)
from ...models.http_validation_error import HTTPValidationError


def _get_kwargs(
    *,
    body: BodyVoiceCloneV1AudioClonePost,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/audio/clone",
    }

    _kwargs["files"] = body.to_multipart()

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
    body: BodyVoiceCloneV1AudioClonePost,
) -> Response[Any | HTTPValidationError]:
    """Voice cloning synthesis

     Clone a voice from a reference recording and synthesize text with it.

    Upload a short audio recording of the speaker (3–30 seconds) and the text you want
    synthesized. The model generates speech that matches the voice characteristics of the
    provided reference.

    **Supported models:** Qwen3-TTS base variants (require CUDA). Use `/v1/models` to see
    available cloning-capable models.

    **Reference audio:** wav, mp3, m4a recommended. 3–30 seconds of clean speech.

    **Note:** Voice cloning is hardware-intensive. Ensure the model is downloaded first
    via `POST /v1/models/{model_id}/download`.

    Args:
        body (BodyVoiceCloneV1AudioClonePost):

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
    body: BodyVoiceCloneV1AudioClonePost,
) -> Any | HTTPValidationError | None:
    """Voice cloning synthesis

     Clone a voice from a reference recording and synthesize text with it.

    Upload a short audio recording of the speaker (3–30 seconds) and the text you want
    synthesized. The model generates speech that matches the voice characteristics of the
    provided reference.

    **Supported models:** Qwen3-TTS base variants (require CUDA). Use `/v1/models` to see
    available cloning-capable models.

    **Reference audio:** wav, mp3, m4a recommended. 3–30 seconds of clean speech.

    **Note:** Voice cloning is hardware-intensive. Ensure the model is downloaded first
    via `POST /v1/models/{model_id}/download`.

    Args:
        body (BodyVoiceCloneV1AudioClonePost):

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
    body: BodyVoiceCloneV1AudioClonePost,
) -> Response[Any | HTTPValidationError]:
    """Voice cloning synthesis

     Clone a voice from a reference recording and synthesize text with it.

    Upload a short audio recording of the speaker (3–30 seconds) and the text you want
    synthesized. The model generates speech that matches the voice characteristics of the
    provided reference.

    **Supported models:** Qwen3-TTS base variants (require CUDA). Use `/v1/models` to see
    available cloning-capable models.

    **Reference audio:** wav, mp3, m4a recommended. 3–30 seconds of clean speech.

    **Note:** Voice cloning is hardware-intensive. Ensure the model is downloaded first
    via `POST /v1/models/{model_id}/download`.

    Args:
        body (BodyVoiceCloneV1AudioClonePost):

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
    body: BodyVoiceCloneV1AudioClonePost,
) -> Any | HTTPValidationError | None:
    """Voice cloning synthesis

     Clone a voice from a reference recording and synthesize text with it.

    Upload a short audio recording of the speaker (3–30 seconds) and the text you want
    synthesized. The model generates speech that matches the voice characteristics of the
    provided reference.

    **Supported models:** Qwen3-TTS base variants (require CUDA). Use `/v1/models` to see
    available cloning-capable models.

    **Reference audio:** wav, mp3, m4a recommended. 3–30 seconds of clean speech.

    **Note:** Voice cloning is hardware-intensive. Ensure the model is downloaded first
    via `POST /v1/models/{model_id}/download`.

    Args:
        body (BodyVoiceCloneV1AudioClonePost):

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
