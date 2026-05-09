"""Switch platform for the Sunthalpy integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity

from .const import is_truthy
from .data import SWITCHES
from .entity import SunthalpyEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SunthalpyDataUpdateCoordinator
    from .data import SunthalpyConfigEntry, SunthalpySwitchPoint


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SunthalpyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register every switch for this entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        SunthalpySwitch(coordinator, point) for point in SWITCHES
    )


class SunthalpySwitch(SunthalpyEntity, SwitchEntity):
    """Switch that writes a boolean to a Sunthalpy device address."""

    def __init__(
        self,
        coordinator: SunthalpyDataUpdateCoordinator,
        point: SunthalpySwitchPoint,
    ) -> None:
        """Initialise from a descriptor."""
        super().__init__(coordinator, point.unique_suffix)
        self._point = point
        self._attr_translation_key = point.unique_suffix
        self._attr_device_class = point.device_class
        self._attr_icon = point.icon
        self._attr_entity_category = point.entity_category
        self._attr_entity_registry_enabled_default = point.enabled_by_default

    @property
    def is_on(self) -> bool | None:
        """Return whether the switch is currently on."""
        data = self.coordinator.data or {}
        bucket = data.get("buckets", {}).get(self._point.bucket, {})
        value = bucket.get(self._point.address)
        if value is None:
            return None
        return is_truthy(value)

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Turn the switch on via the API."""
        await self.coordinator.async_set_switch(
            self._point.bucket,
            self._point.address,
            value=True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002
        """Turn the switch off via the API."""
        await self.coordinator.async_set_switch(
            self._point.bucket,
            self._point.address,
            value=False,
        )
