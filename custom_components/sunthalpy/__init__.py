"""The Sunthalpy custom integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import SunthalpyApiClient
from .coordinator import SunthalpyDataUpdateCoordinator
from .data import SunthalpyData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import SunthalpyConfigEntry


PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunthalpyConfigEntry,
) -> bool:
    """Set up Sunthalpy from a config entry."""
    client = SunthalpyApiClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )
    coordinator = SunthalpyDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=client,
    )

    entry.runtime_data = SunthalpyData(
        client=client,
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SunthalpyConfigEntry,
) -> bool:
    """Unload a Sunthalpy config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant,
    entry: SunthalpyConfigEntry,
) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
