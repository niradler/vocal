from http import HTTPStatus
from typing import Any

import httpx

from ...client import AuthenticatedClient, Client
from ...types import Response, UNSET
from ... import errors

from ...models.http_validation_error import HTTPValidationError
from ...models.model_list_response import ModelListResponse
from ...types import Unset


def _get_kwargs(
    *,
    task: None | str | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_task: None | str | Unset
    if isinstance(task, Unset):
        json_task = UNSET
    else:
        json_task = task
    params["task"] = json_task

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/v1/models",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ModelListResponse | None:
    if response.status_code == 200:
        response_200 = ModelListResponse.from_dict(response.json())

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
) -> Response[HTTPValidationError | ModelListResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    task: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | ModelListResponse]:
    """List models

     List downloaded models (Ollama-style)

    Args:
        task (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ModelListResponse]
    """

    kwargs = _get_kwargs(
        task=task,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    task: None | str | Unset = UNSET,
) -> HTTPValidationError | ModelListResponse | None:
    """List models

     List downloaded models (Ollama-style)

    Args:
        task (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ModelListResponse
    """

    return sync_detailed(
        client=client,
        task=task,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    task: None | str | Unset = UNSET,
) -> Response[HTTPValidationError | ModelListResponse]:
    """List models

     List downloaded models (Ollama-style)

    Args:
        task (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ModelListResponse]
    """

    kwargs = _get_kwargs(
        task=task,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    task: None | str | Unset = UNSET,
) -> HTTPValidationError | ModelListResponse | None:
    """List models

     List downloaded models (Ollama-style)

    Args:
        task (None | str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ModelListResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            task=task,
        )
    ).parsed
