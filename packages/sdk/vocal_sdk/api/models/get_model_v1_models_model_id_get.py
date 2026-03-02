from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.model_info import ModelInfo


def _get_kwargs(
    model_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/models/{model_id}".format(
            model_id=quote(str(model_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ModelInfo | None:
    if response.status_code == 200:
        response_200 = ModelInfo.from_dict(response.json())

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
) -> Response[HTTPValidationError | ModelInfo]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    model_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | ModelInfo]:
    """Get model info

     Get detailed information about a specific model

    Args:
        model_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ModelInfo]
    """

    kwargs = _get_kwargs(
        model_id=model_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    model_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | ModelInfo | None:
    """Get model info

     Get detailed information about a specific model

    Args:
        model_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ModelInfo
    """

    return sync_detailed(
        model_id=model_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    model_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[HTTPValidationError | ModelInfo]:
    """Get model info

     Get detailed information about a specific model

    Args:
        model_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ModelInfo]
    """

    kwargs = _get_kwargs(
        model_id=model_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    model_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> HTTPValidationError | ModelInfo | None:
    """Get model info

     Get detailed information about a specific model

    Args:
        model_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ModelInfo
    """

    return (
        await asyncio_detailed(
            model_id=model_id,
            client=client,
        )
    ).parsed
