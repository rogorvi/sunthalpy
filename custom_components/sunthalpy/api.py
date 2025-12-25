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
        self._data: dict | None = None
        self._prev_data: dict | None = None

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
        cnt.LOGGER.debug("Getting data from the API")
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
            .get("103", None)
        )
        humidity: float = (
            data.get("main_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("102", None)
        )

        data.setdefault("calc_data", {}).setdefault("obj", {}).setdefault(
            "lastMeasure", {}
        )["0000"] = self._get_dew_point(temp, humidity)

        data.setdefault("calc_data", {}).setdefault("obj", {}).setdefault(
            "lastMeasure", {}
        )["0001"] = self._get_aero_state(data, self._data)

        data.setdefault("calc_data", {}).setdefault("obj", {}).setdefault(
            "lastMeasure", {}
        )["0002"] = (
            0
            if data["calc_data"]["obj"]["lastMeasure"]["0001"] == cnt.AeroModes.IDLE
            else 1
        )

        self._prev_data = self._data
        self._data = data

        return data

    def get_pot_cool(self, data: dict) -> float | None:
        """Get Potencia instantánea refrigeración."""
        return (
            data.get("other_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("134", None)
        )

    def get_pot_heat(self, data: dict) -> float | None:
        """Get Potencia instantánea calefacción."""
        return (
            data.get("other_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("133", None)
        )

    def get_acs_temp(self, data: dict) -> float | None:
        """Get Temp. ACS."""
        return (
            data.get("other_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("11", None)
        )

    def get_dg1(self, data: dict) -> float | None:
        """Get Bus Demanda DG1."""
        return (
            data.get("other_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("5183", None)
        )

    def get_target_heat_temp(self, data: dict) -> float | None:
        """Get Consigna temp. calefacción."""
        return (
            data.get("other_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("170", None)
        )

    def get_return_heat_temp_int(self, data: dict) -> float | None:
        """Get Consigna temp. calefacción."""
        return (
            data.get("other_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("2", None)
        )

    def get_is_winter(self, data: dict) -> float | None:
        """Get Bus Demanda DG1."""
        return (
            data.get("other_data", {})
            .get("obj", {})
            .get("lastMeasure", {})
            .get("202", None)
        )

    def _get_aero_state(self, data: dict | None, prev_data: dict | None) -> str:
        """Find the aerothermal device sate."""
        if prev_data is None or data is None:
            return cnt.AeroModes.IDLE

        pot_cool = self.get_pot_cool(data)
        pot_heat = self.get_pot_heat(data)
        acs_now = self.get_acs_temp(data)
        is_winter = self.get_is_winter(data)
        dg1 = self.get_dg1(data)
        target_heat = self.get_target_heat_temp(data)
        temp_return = self.get_return_heat_temp_int(data)

        # If current or prev data are not available, return idle state
        if (
            pot_cool is None
            or pot_heat is None
            or acs_now is None
            or target_heat is None
            or temp_return is None
        ):
            return cnt.AeroModes.IDLE

        dg1_active: bool = str(dg1) == "1"

        # If there is no cooling nor heating energy, return idle
        if pot_cool == 0 and pot_heat == 0:
            return cnt.AeroModes.IDLE
        # If there is cooling energy return cooling
        if pot_cool > 0:
            return cnt.AeroModes.COOLING
        # If there is heating energy we need to check if it's ACS
        if pot_heat > 0:
            if temp_return > target_heat + 5:
                mode = cnt.AeroModes.ACS
                # Since ACS has priority over heating and cooling
                # we check if those are waiting
                if dg1_active:
                    waiting_mode = (
                        # is_winter defines the waiting enery mode
                        cnt.AeroModes.HEATING if is_winter else cnt.AeroModes.COOLING
                    )
                    mode += cnt.AeroModes.MODE_WAITING.format(waiting_mode)
            else:
                # If there is no ACS, then we are heating
                mode = cnt.AeroModes.HEATING
            return mode

        # Catch states not considered above
        return cnt.AeroModes.UNKNOWN

    def _get_dew_point(self, temp: float, humidity: float) -> float | None:
        """
        Calculate dew point based on temperature and humidity inputs.

        temp in Celsius. humidity in %.
        """
        if not temp or not humidity:
            return None

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
                    method=method, url=url, headers=headers, json=data, ssl=False
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
