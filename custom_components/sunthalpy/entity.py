"""BlueprintEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BlueprintDataUpdateCoordinator


class IntegrationBlueprintEntity(CoordinatorEntity[BlueprintDataUpdateCoordinator]):
    """BlueprintEntity class."""

    def __init__(
        self,
        coordinator: BlueprintDataUpdateCoordinator,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    coordinator.config_entry.domain,
                    coordinator.config_entry.entry_id,
                ),
            },
        )
