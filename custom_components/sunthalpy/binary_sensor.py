"""Binary sensor platform for integration_blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import IntegrationBlueprintEntity
from .sunthalhome import binary_sensors

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import BlueprintDataUpdateCoordinator
    from .data import IntegrationBlueprintConfigEntry

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key=f"{elem.uuid_name}--{elem.address}",
        name=elem.name,
        device_class=elem.device_class,
        entity_registry_enabled_default=elem.start_enabled,
        icon=elem.icon,
    )
    for elem in binary_sensors
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationBlueprintConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        IntegrationBlueprintBinarySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationBlueprintBinarySensor(IntegrationBlueprintEntity, BinarySensorEntity):
    """integration_blueprint binary_sensor class."""

    def __init__(
        self,
        coordinator: BlueprintDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary_sensor class."""
        name = entity_description.name if type(entity_description.name) is str else ""
        super().__init__(coordinator, name)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
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
