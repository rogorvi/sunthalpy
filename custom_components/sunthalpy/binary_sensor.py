"""Binary sensor platform for the Sunthalpy integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import is_truthy
from .data import BINARY_SENSORS
from .entity import SunthalpyEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SunthalpyDataUpdateCoordinator
    from .data import SunthalpyBinaryPoint, SunthalpyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SunthalpyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register every binary sensor for this entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        SunthalpyBinarySensor(coordinator, point) for point in BINARY_SENSORS
    )


class SunthalpyBinarySensor(SunthalpyEntity, BinarySensorEntity):
    """Binary sensor backed by a single (bucket, address) value."""

    def __init__(
        self,
        coordinator: SunthalpyDataUpdateCoordinator,
        point: SunthalpyBinaryPoint,
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
        """Return ``True`` if the address resolves to a truthy value."""
        data = self.coordinator.data or {}
        bucket = data.get("buckets", {}).get(self._point.bucket, {})
        value = bucket.get(self._point.address)
        if value is None:
            return None
        return is_truthy(value)

    @property
    def available(self) -> bool:
        """Mirror the coordinator's availability state."""
        if not super().available:
            return False
        data = self.coordinator.data or {}
        bucket = data.get("buckets", {}).get(self._point.bucket, {})
        return bucket.get(self._point.address) is not None
