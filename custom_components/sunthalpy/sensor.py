"""Sensor platform for sunthalpy."""  # noqa: EXE002

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)

from .entity import IntegrationBlueprintEntity
from .sunthalhome import sensors

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from uv import Any

    from .coordinator import BlueprintDataUpdateCoordinator
    from .data import IntegrationBlueprintConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key=f"{elem.uuid_name}--{elem.address}",
        name=elem.name,
        device_class=elem.device_class,
        native_unit_of_measurement=elem.unit,
        entity_registry_enabled_default=elem.start_enabled,
    )
    for elem in sensors
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationBlueprintConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        IntegrationBlueprintSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationBlueprintSensor(IntegrationBlueprintEntity, SensorEntity):
    """sunthalpy Sensor class."""

    def __init__(
        self,
        coordinator: BlueprintDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def native_value(self) -> Any:
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
