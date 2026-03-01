import ssl
from typing import Any

from attrs import define, field, evolve
import httpx


@define
class VocalClient:
    """Vocal Speech AI Platform — HTTP client

    Provides both a synchronous httpx.Client and an asynchronous httpx.AsyncClient
    for calling the Vocal API endpoints generated in the ``api`` module.

    Keyword arguments (passed through to httpx):

    ``base_url``: The base URL for the Vocal API (e.g. ``http://localhost:8000``)

    ``cookies``: A dictionary of cookies to be sent with every request

    ``headers``: A dictionary of headers to be sent with every request

    ``timeout``: The maximum time a request can take. API functions raise
    httpx.TimeoutException if this is exceeded.

    ``verify_ssl``: Whether to verify the server SSL certificate. Set to False for local dev.

    ``follow_redirects``: Whether to follow redirects. Default is False.

    ``httpx_args``: Additional arguments forwarded to the httpx.Client / httpx.AsyncClient constructor.


    Attributes:
    raise_on_unexpected_status: Whether or not to raise an errors.UnexpectedStatus if the API returns a
            status code that was not documented in the source OpenAPI document. Can also be provided as a keyword
            argument to the constructor.
    """

    raise_on_unexpected_status: bool = field(default=False, kw_only=True)
    _base_url: str = field(alias="base_url")
    _cookies: dict[str, str] = field(factory=dict, kw_only=True, alias="cookies")
    _headers: dict[str, str] = field(factory=dict, kw_only=True, alias="headers")
    _timeout: httpx.Timeout | None = field(default=None, kw_only=True, alias="timeout")
    _verify_ssl: str | bool | ssl.SSLContext = field(
        default=True, kw_only=True, alias="verify_ssl"
    )
    _follow_redirects: bool = field(
        default=False, kw_only=True, alias="follow_redirects"
    )
    _httpx_args: dict[str, Any] = field(factory=dict, kw_only=True, alias="httpx_args")
    _client: httpx.Client | None = field(default=None, init=False)
    _async_client: httpx.AsyncClient | None = field(default=None, init=False)

    def with_headers(self, headers: dict[str, str]) -> "VocalClient":
        """Return a new client with additional headers"""
        if self._client is not None:
            self._client.headers.update(headers)
        if self._async_client is not None:
            self._async_client.headers.update(headers)
        return evolve(self, headers={**self._headers, **headers})

    def with_cookies(self, cookies: dict[str, str]) -> "VocalClient":
        """Return a new client with additional cookies"""
        if self._client is not None:
            self._client.cookies.update(cookies)
        if self._async_client is not None:
            self._async_client.cookies.update(cookies)
        return evolve(self, cookies={**self._cookies, **cookies})

    def with_timeout(self, timeout: httpx.Timeout) -> "VocalClient":
        """Return a new client with a new timeout"""
        if self._client is not None:
            self._client.timeout = timeout
        if self._async_client is not None:
            self._async_client.timeout = timeout
        return evolve(self, timeout=timeout)

    def set_httpx_client(self, client: httpx.Client) -> "VocalClient":
        """Manually set the underlying httpx.Client

        **NOTE**: This overrides all other settings (cookies, headers, timeout).
        """
        self._client = client
        return self

    def get_httpx_client(self) -> httpx.Client:
        """Get the underlying httpx.Client, constructing one if not yet set"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._client

    def __enter__(self) -> "VocalClient":
        """Enter a context manager for self.client"""
        self.get_httpx_client().__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit the context manager for internal httpx.Client"""
        self.get_httpx_client().__exit__(*args, **kwargs)

    def set_async_httpx_client(self, async_client: httpx.AsyncClient) -> "VocalClient":
        """Manually set the underlying httpx.AsyncClient

        **NOTE**: This overrides all other settings (cookies, headers, timeout).
        """
        self._async_client = async_client
        return self

    def get_async_httpx_client(self) -> httpx.AsyncClient:
        """Get the underlying httpx.AsyncClient, constructing one if not yet set"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._async_client

    async def __aenter__(self) -> "VocalClient":
        """Enter a context manager for underlying httpx.AsyncClient"""
        await self.get_async_httpx_client().__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit the context manager for underlying httpx.AsyncClient"""
        await self.get_async_httpx_client().__aexit__(*args, **kwargs)


@define
class VocalAuthenticatedClient:
    """Vocal Speech AI Platform — authenticated HTTP client

    Extends VocalClient with an Authorization header for secured endpoints.

    Keyword arguments (passed through to httpx):

    ``base_url``: The base URL for the Vocal API (e.g. ``http://localhost:8000``)

    ``cookies``: A dictionary of cookies to be sent with every request

    ``headers``: A dictionary of headers to be sent with every request

    ``timeout``: The maximum time a request can take. API functions raise
    httpx.TimeoutException if this is exceeded.

    ``verify_ssl``: Whether to verify the server SSL certificate. Set to False for local dev.

    ``follow_redirects``: Whether to follow redirects. Default is False.

    ``httpx_args``: Additional arguments forwarded to the httpx.Client / httpx.AsyncClient constructor.


    Attributes:
    raise_on_unexpected_status: Whether or not to raise an errors.UnexpectedStatus if the API returns a
            status code that was not documented in the source OpenAPI document. Can also be provided as a keyword
            argument to the constructor.
    token: The token to use for authentication
    prefix: The prefix to use for the Authorization header
    auth_header_name: The name of the Authorization header
    """

    raise_on_unexpected_status: bool = field(default=False, kw_only=True)
    _base_url: str = field(alias="base_url")
    _cookies: dict[str, str] = field(factory=dict, kw_only=True, alias="cookies")
    _headers: dict[str, str] = field(factory=dict, kw_only=True, alias="headers")
    _timeout: httpx.Timeout | None = field(default=None, kw_only=True, alias="timeout")
    _verify_ssl: str | bool | ssl.SSLContext = field(
        default=True, kw_only=True, alias="verify_ssl"
    )
    _follow_redirects: bool = field(
        default=False, kw_only=True, alias="follow_redirects"
    )
    _httpx_args: dict[str, Any] = field(factory=dict, kw_only=True, alias="httpx_args")
    _client: httpx.Client | None = field(default=None, init=False)
    _async_client: httpx.AsyncClient | None = field(default=None, init=False)

    token: str
    prefix: str = "Bearer"
    auth_header_name: str = "Authorization"

    def with_headers(self, headers: dict[str, str]) -> "VocalAuthenticatedClient":
        """Return a new client with additional headers"""
        if self._client is not None:
            self._client.headers.update(headers)
        if self._async_client is not None:
            self._async_client.headers.update(headers)
        return evolve(self, headers={**self._headers, **headers})

    def with_cookies(self, cookies: dict[str, str]) -> "VocalAuthenticatedClient":
        """Return a new client with additional cookies"""
        if self._client is not None:
            self._client.cookies.update(cookies)
        if self._async_client is not None:
            self._async_client.cookies.update(cookies)
        return evolve(self, cookies={**self._cookies, **cookies})

    def with_timeout(self, timeout: httpx.Timeout) -> "VocalAuthenticatedClient":
        """Return a new client with a new timeout"""
        if self._client is not None:
            self._client.timeout = timeout
        if self._async_client is not None:
            self._async_client.timeout = timeout
        return evolve(self, timeout=timeout)

    def set_httpx_client(self, client: httpx.Client) -> "VocalAuthenticatedClient":
        """Manually set the underlying httpx.Client

        **NOTE**: This overrides all other settings (cookies, headers, timeout).
        """
        self._client = client
        return self

    def get_httpx_client(self) -> httpx.Client:
        """Get the underlying httpx.Client, constructing one if not yet set"""
        if self._client is None:
            self._headers[self.auth_header_name] = (
                f"{self.prefix} {self.token}" if self.prefix else self.token
            )
            self._client = httpx.Client(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._client

    def __enter__(self) -> "VocalAuthenticatedClient":
        """Enter a context manager for self.client"""
        self.get_httpx_client().__enter__()
        return self

    def __exit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit the context manager for internal httpx.Client"""
        self.get_httpx_client().__exit__(*args, **kwargs)

    def set_async_httpx_client(
        self, async_client: httpx.AsyncClient
    ) -> "VocalAuthenticatedClient":
        """Manually set the underlying httpx.AsyncClient

        **NOTE**: This overrides all other settings (cookies, headers, timeout).
        """
        self._async_client = async_client
        return self

    def get_async_httpx_client(self) -> httpx.AsyncClient:
        """Get the underlying httpx.AsyncClient, constructing one if not yet set"""
        if self._async_client is None:
            self._headers[self.auth_header_name] = (
                f"{self.prefix} {self.token}" if self.prefix else self.token
            )
            self._async_client = httpx.AsyncClient(
                base_url=self._base_url,
                cookies=self._cookies,
                headers=self._headers,
                timeout=self._timeout,
                verify=self._verify_ssl,
                follow_redirects=self._follow_redirects,
                **self._httpx_args,
            )
        return self._async_client

    async def __aenter__(self) -> "VocalAuthenticatedClient":
        """Enter a context manager for underlying httpx.AsyncClient"""
        await self.get_async_httpx_client().__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """Exit the context manager for underlying httpx.AsyncClient"""
        await self.get_async_httpx_client().__aexit__(*args, **kwargs)


Client = VocalClient
AuthenticatedClient = VocalAuthenticatedClient
