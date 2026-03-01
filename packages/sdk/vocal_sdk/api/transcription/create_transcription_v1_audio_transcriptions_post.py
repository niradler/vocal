from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response
from ... import errors

from ...models.body_create_transcription_v1_audio_transcriptions_post import (
    BodyCreateTranscriptionV1AudioTranscriptionsPost,
)
from ...models.http_validation_error import HTTPValidationError
from ...models.transcription_response import TranscriptionResponse


def _get_kwargs(
    *,
    body: BodyCreateTranscriptionV1AudioTranscriptionsPost,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/v1/audio/transcriptions",
    }

    _kwargs["files"] = body.to_multipart()

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | TranscriptionResponse | None:
    if response.status_code == 200:
        response_200 = TranscriptionResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | TranscriptionResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BodyCreateTranscriptionV1AudioTranscriptionsPost,
) -> Response[HTTPValidationError | TranscriptionResponse]:
    """Transcribe audio

     Transcribe audio file to text using specified model

    Args:
        body (BodyCreateTranscriptionV1AudioTranscriptionsPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TranscriptionResponse]
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
    body: BodyCreateTranscriptionV1AudioTranscriptionsPost,
) -> HTTPValidationError | TranscriptionResponse | None:
    """Transcribe audio

     Transcribe audio file to text using specified model

    Args:
        body (BodyCreateTranscriptionV1AudioTranscriptionsPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TranscriptionResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BodyCreateTranscriptionV1AudioTranscriptionsPost,
) -> Response[HTTPValidationError | TranscriptionResponse]:
    """Transcribe audio

     Transcribe audio file to text using specified model

    Args:
        body (BodyCreateTranscriptionV1AudioTranscriptionsPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | TranscriptionResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: BodyCreateTranscriptionV1AudioTranscriptionsPost,
) -> HTTPValidationError | TranscriptionResponse | None:
    """Transcribe audio

     Transcribe audio file to text using specified model

    Args:
        body (BodyCreateTranscriptionV1AudioTranscriptionsPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | TranscriptionResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
