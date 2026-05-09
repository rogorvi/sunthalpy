"""Base entity for the Sunthalpy integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, MODEL

if TYPE_CHECKING:
    from .coordinator import SunthalpyDataUpdateCoordinator


class SunthalpyEntity(CoordinatorEntity["SunthalpyDataUpdateCoordinator"]):
    """Base entity that wires every Sunthalpy entity to the same device."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SunthalpyDataUpdateCoordinator,
        unique_suffix: str,
    ) -> None:
        """Initialise common attributes."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Sunthalpy",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
