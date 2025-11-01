"""Switch platform for integration_blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.helpers.event import async_call_later

from .entity import IntegrationBlueprintEntity
from .sunthalhome import switches

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import BlueprintDataUpdateCoordinator
    from .data import IntegrationBlueprintConfigEntry

ENTITY_DESCRIPTIONS = tuple(
    SwitchEntityDescription(
        key=f"{elem.uuid_name}--{elem.address}",
        name=elem.name,
        device_class=elem.device_class,
        entity_registry_enabled_default=elem.start_enabled,
        icon=elem.icon,
    )
    for elem in switches
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: IntegrationBlueprintConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    async_add_entities(
        IntegrationBlueprintSwitch(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationBlueprintSwitch(IntegrationBlueprintEntity, SwitchEntity):
    """integration_blueprint switch class."""

    def __init__(
        self,
        coordinator: BlueprintDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch class."""
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

    async def async_turn_on(self, **_: Any) -> None:
        """Turn on the switch."""
        uuid, address = self.entity_description.key.split("--")
        await self.coordinator.config_entry.runtime_data.client.async_switch_on(
            uuid, address
        )
        async_call_later(self.hass, 5, self._scheduled_refresh)

    async def async_turn_off(self, **_: Any) -> None:
        """Turn off the switch."""
        uuid, address = self.entity_description.key.split("--")
        await self.coordinator.config_entry.runtime_data.client.async_switch_off(
            uuid, address
        )
        async_call_later(self.hass, 5, self._scheduled_refresh)

    async def _scheduled_refresh(self, _now=None) -> None:  # noqa: ANN001
        """Handle scheduled refresh."""
        await self.coordinator.async_request_refresh()
