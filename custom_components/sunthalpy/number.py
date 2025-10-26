"""Numer platform for sunthalpy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.helpers.event import async_call_later

from .entity import IntegrationBlueprintEntity
from .sunthalhome import numbers

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import BlueprintDataUpdateCoordinator
    from .data import IntegrationBlueprintConfigEntry
ENTITY_DESCRIPTIONS = (
    NumberEntityDescription(
        key=f"{elem.uuid_name}--{elem.address}",
        name=elem.name,
        device_class=elem.device_class,
        native_min_value=elem.min_value,
        native_max_value=elem.max_value,
        native_step=elem.step,
        native_unit_of_measurement=elem.unit,
        mode=elem.mode,
        entity_registry_enabled_default=elem.start_enabled,
        icon=elem.icon,
    )
    for elem in numbers
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationBlueprintConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    async_add_entities(
        SunthalpyNumber(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class SunthalpyNumber(IntegrationBlueprintEntity, NumberEntity):
    """Sunthalpy number class."""

    def __init__(
        self,
        coordinator: BlueprintDataUpdateCoordinator,
        entity_description: NumberEntityDescription,
    ) -> None:
        """Initialize the number class."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def native_value(self) -> float | None:
        """Return the native value of the sensor."""
        uuid, address = self.entity_description.key.split("--")
        data = self.coordinator.data.get(uuid, {})
        return (
            data.get("obj", {})
            .get("lastMeasure", {})
            .get(
                address,
                None,
            )
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        uuid, address = self.entity_description.key.split("--")
        await self.coordinator.config_entry.runtime_data.client.async_update_number(
            uuid, address, value
        )
        async_call_later(self.hass, 5, self._scheduled_refresh)

    async def _scheduled_refresh(self, _now=None) -> None:  # noqa: ANN001
        """Handle scheduled refresh."""
        await self.coordinator.async_request_refresh()
