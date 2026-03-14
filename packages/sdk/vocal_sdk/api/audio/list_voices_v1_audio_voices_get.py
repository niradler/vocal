from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.voices_response import VoicesResponse
from ...types import Unset


def _get_kwargs(
    *,
    model: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_model: None | str | Unset
    if isinstance(model, Unset):
        json_model = UNSET
    else:
        json_model = model
    params["model"] = json_model

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/audio/voices",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | VoicesResponse | None:
    if response.status_code == 200:
        response_200 = VoicesResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | VoicesResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    model: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | VoicesResponse]:
    """List Voices

     List available TTS voices.

    - **model**: Optional model ID to list voices for a specific model

    Args:
        model (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | VoicesResponse]
    """

    kwargs = _get_kwargs(
        model=model,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    model: None | str | Unset = UNSET,
) -> HTTPValidationError | VoicesResponse | None:
    """List Voices

     List available TTS voices.

    - **model**: Optional model ID to list voices for a specific model

    Args:
        model (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | VoicesResponse
    """

    return sync_detailed(
        client=client,
        model=model,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    model: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | VoicesResponse]:
    """List Voices

     List available TTS voices.

    - **model**: Optional model ID to list voices for a specific model

    Args:
        model (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | VoicesResponse]
    """

    kwargs = _get_kwargs(
        model=model,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    model: None | str | Unset = UNSET,
) -> HTTPValidationError | VoicesResponse | None:
    """List Voices

     List available TTS voices.

    - **model**: Optional model ID to list voices for a specific model

    Args:
        model (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | VoicesResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            model=model,
        )
    ).parsed
