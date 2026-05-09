"""HTTP client for the Sunthalpy cloud API."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Any

import aiohttp
import async_timeout

from .const import BASE_URL, HEADERS, HTTP_TIMEOUT_S, LOGGER, UUIDS

if TYPE_CHECKING:
    from collections.abc import Mapping


class SunthalpyApiError(Exception):
    """Base class for Sunthalpy API errors."""


class SunthalpyApiCommunicationError(SunthalpyApiError):
    """Raised on network / transport-level failures."""


class SunthalpyApiAuthenticationError(SunthalpyApiError):
    """Raised when credentials are rejected by the API."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Map HTTP status codes to typed exceptions."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise SunthalpyApiAuthenticationError(msg)
    response.raise_for_status()


class SunthalpyApiClient:
    """Async client for the Sunthalpy cloud API.

    The API is a JSON-over-HTTPS service that requires a per-call bearer
    token obtained from a login endpoint. This client caches no state and
    fetches a fresh token for every batch of calls; that keeps it robust
    against silent token expiry at the cost of one extra request per poll.
    """

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialise the client with credentials and an aiohttp session."""
        self._username = username
        self._password = password
        self._session = session

    async def async_validate_credentials(self) -> None:
        """Attempt a login round-trip; used by the config flow."""
        await self._get_token()

    async def async_get_data(self) -> dict[str, dict[str, Any]]:
        """Fetch the latest measurements for every UUID bucket.

        Returns
        -------
        dict
            Mapping ``{<bucket name>: {<address>: <value>}}`` for every
            bucket configured in ``UUIDS``. Raises on transport / auth
            errors so the caller (the coordinator) can surface them.

        """
        LOGGER.debug("Fetching Sunthalpy data")
        token = await self._get_token()
        out: dict[str, dict[str, Any]] = {}
        for bucket_name, uuid in UUIDS.items():
            payload = await self._post(
                "/get/device-data/last",
                token,
                {"uuid": uuid},
            )
            last_measure = (
                payload.get("obj", {}).get("lastMeasure", {})
                if isinstance(payload, dict)
                else {}
            )
            out[bucket_name] = dict(last_measure)
        return out

    async def async_set_switch(
        self,
        bucket_name: str,
        address: str,
        *,
        value: bool,
    ) -> Any:
        """Set a boolean device address on the given bucket."""
        return await self._send_command(bucket_name, address, value)

    async def async_set_number(
        self,
        bucket_name: str,
        address: str,
        value: float,
    ) -> Any:
        """Set a numeric device address (rounded to 1 decimal)."""
        return await self._send_command(bucket_name, address, round(value, 1))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    async def _get_token(self) -> str:
        """Authenticate and return a fresh bearer token."""
        body = await self._raw_request(
            "post",
            f"{BASE_URL}/login",
            data={"email": self._username, "pass": self._password},
            headers=HEADERS,
        )
        token = (body or {}).get("obj", {}).get("token")
        if not isinstance(token, str) or not token:
            msg = "Login response did not contain a token"
            raise SunthalpyApiAuthenticationError(msg)
        return token

    async def _post(
        self,
        path: str,
        token: str,
        data: Mapping[str, Any],
    ) -> Any:
        """POST ``data`` to ``path`` using ``token`` as auth header."""
        headers = {**HEADERS, "auth": token}
        return await self._raw_request(
            "post",
            f"{BASE_URL}{path}",
            data=dict(data),
            headers=headers,
        )

    async def _send_command(
        self,
        bucket_name: str,
        address: str,
        value: Any,
    ) -> Any:
        """Send a write command to a device address."""
        if bucket_name not in UUIDS:
            msg = f"Unknown bucket name: {bucket_name}"
            raise SunthalpyApiError(msg)
        token = await self._get_token()
        payload = {
            "uuid": UUIDS[bucket_name],
            "value": value,
            "deviceInternalAddress": address,
        }
        return await self._post("/send/device/command", token, payload)

    async def _raw_request(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Execute an HTTP request and translate failures to typed errors."""
        try:
            async with async_timeout.timeout(HTTP_TIMEOUT_S):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    ssl=False,
                )
                _verify_response_or_raise(response)
                return await response.json()
        except TimeoutError as exc:
            msg = f"Timeout contacting Sunthalpy API: {exc}"
            raise SunthalpyApiCommunicationError(msg) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            msg = f"Network error contacting Sunthalpy API: {exc}"
            raise SunthalpyApiCommunicationError(msg) from exc
