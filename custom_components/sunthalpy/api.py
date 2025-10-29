"""Sample API Client."""

from __future__ import annotations

import socket
from math import log
from typing import Any

import aiohttp
import async_timeout

from . import const as cnt


class IntegrationBlueprintApiClientError(Exception):
    """Exception to indicate a general API error."""


class IntegrationBlueprintApiClientCommunicationError(
    IntegrationBlueprintApiClientError,
):
    """Exception to indicate a communication error."""


class IntegrationBlueprintApiClientAuthenticationError(
    IntegrationBlueprintApiClientError,
):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise IntegrationBlueprintApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


class IntegrationBlueprintApiClient:
    """Sample API Client."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Sample API Client."""
        self._username = username
        self._password = password
        self._session = session
        self._session.connector._ssl = False  # type: ignore # Disable SSL verification  # noqa: PGH003, SLF001

    async def _get_token(self) -> str:
        """Get token from the API."""
        token_data = await self._api_wrapper(
            method="post",
            url=f"{cnt.BASE_URL}/login",
            data={"email": self._username, "pass": self._password},
            headers=cnt.HEADERS,
        )
        return token_data["obj"]["token"]

    async def async_get_data(self) -> Any:
        """Get data from the API."""
        # Get data
        data_headers = cnt.HEADERS.copy()
        data_headers["auth"] = await self._get_token()
        data = {
            uuid_name: await self._api_wrapper(
                method="post",
                url=f"{cnt.BASE_URL}/get/device-data/last",
                data={"uuid": uuid},
                headers=data_headers,
            )
            for uuid_name, uuid in cnt.UUIDS.items()
        }

        temp: float = (
            data.get("main_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("103", 1.0)
        )
        humidity: float = (
            data.get("main_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("102", 1.0)
        )

        data.setdefault("calc_data", {}).setdefault("obj", {}).setdefault(
            "lastMeasure", {}
        )["0000"] = self.get_dew_point(temp, humidity)

        return data

    def get_dew_point(self, temp: float, humidity: float) -> float:
        """
        Calculate dew point based on temperature and humidity inputs.

        temp in Celsius. humidity in %.
        """
        b = 17.625
        c = 243.04
        gamma = log(humidity / 100) + (b * temp) / (c + temp)
        return round(c * gamma / (b - gamma), 1)

    async def _switch(self, uuid: str, address: str, *, set_to: bool) -> Any:
        """Set switch status."""
        data_headers = cnt.HEADERS.copy()
        data_headers["auth"] = await self._get_token()
        return await self._api_wrapper(
            method="post",
            url=f"{cnt.BASE_URL}/send/device/command",
            data={
                "uuid": cnt.UUIDS[uuid],
                "value": set_to,
                "deviceInternalAddress": address,
            },
            headers=data_headers,
        )

    async def async_switch_on(self, uuid: str, address: str) -> Any:
        """Turn on the switch."""
        return await self._switch(uuid, address, set_to=True)

    async def async_switch_off(self, uuid: str, address: str) -> Any:
        """Turn off the switch."""
        return await self._switch(uuid, address, set_to=False)

    async def async_update_number(self, uuid: str, address: str, value: float) -> Any:
        """Turn off the switch."""
        # Set switch status
        data_headers = cnt.HEADERS.copy()
        data_headers["auth"] = await self._get_token()
        data = {
            "uuid": cnt.UUIDS[uuid],
            "value": round(value, 1),
            "deviceInternalAddress": address,
        }
        return await self._api_wrapper(
            method="post",
            url=f"{cnt.BASE_URL}/send/device/command",
            data=data,
            headers=data_headers,
        )

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                _verify_response_or_raise(response)
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise IntegrationBlueprintApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise IntegrationBlueprintApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise IntegrationBlueprintApiClientError(
                msg,
            ) from exception
