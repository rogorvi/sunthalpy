"""Config flow for the Sunthalpy integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from slugify import slugify

from .api import (
    SunthalpyApiAuthenticationError,
    SunthalpyApiClient,
    SunthalpyApiCommunicationError,
    SunthalpyApiError,
)
from .const import DOMAIN, LOGGER


class SunthalpyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a UI-driven config flow for Sunthalpy."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except SunthalpyApiAuthenticationError as exc:
                LOGGER.warning("Sunthalpy auth error: %s", exc)
                errors["base"] = "auth"
            except SunthalpyApiCommunicationError as exc:
                LOGGER.error("Sunthalpy connection error: %s", exc)
                errors["base"] = "connection"
            except SunthalpyApiError:
                LOGGER.exception("Unknown Sunthalpy error during config flow")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(slugify(user_input[CONF_USERNAME]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.EMAIL,
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def _test_credentials(self, username: str, password: str) -> None:
        """Try logging in to validate the credentials."""
        client = SunthalpyApiClient(
            username=username,
            password=password,
            session=async_create_clientsession(self.hass),
        )
        await client.async_validate_credentials()
