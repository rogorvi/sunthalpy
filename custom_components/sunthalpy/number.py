"""Number platform for the Sunthalpy integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity

from .const import Addr
from .data import NUMBERS
from .entity import SunthalpyEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SunthalpyDataUpdateCoordinator
    from .data import SunthalpyConfigEntry, SunthalpyNumberPoint


# Minimum spread enforced between the heating min and max setpoints.
# The thermostat would refuse to operate if min >= max, so when a write
# would violate the invariant we silently bump the partner first.
MIN_MAX_SPREAD_C = 0.1


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SunthalpyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register every number entity for this entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        SunthalpyNumber(coordinator, point) for point in NUMBERS
    )


class SunthalpyNumber(SunthalpyEntity, NumberEntity):
    """Number entity that writes a float to a Sunthalpy device address."""

    def __init__(
        self,
        coordinator: SunthalpyDataUpdateCoordinator,
        point: SunthalpyNumberPoint,
    ) -> None:
        """Initialise from a descriptor."""
        super().__init__(coordinator, point.unique_suffix)
        self._point = point
        self._attr_translation_key = point.unique_suffix
        self._attr_native_unit_of_measurement = point.unit
        self._attr_device_class = point.device_class
        self._attr_icon = point.icon
        self._attr_entity_category = point.entity_category
        self._attr_entity_registry_enabled_default = point.enabled_by_default
        self._attr_native_min_value = point.min_value
        self._attr_native_max_value = point.max_value
        self._attr_native_step = point.step
        self._attr_mode = point.mode

    @property
    def native_value(self) -> float | None:
        """Return the current numeric value, or ``None``."""
        data = self.coordinator.data or {}
        bucket = data.get("buckets", {}).get(self._point.bucket, {})
        value = bucket.get(self._point.address)
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """
        Push a new value to the device.

        The heating min/max setpoints share an invariant: ``min < max``.
        If the requested change would violate it, we adjust the partner
        first (so the device never sees an inverted pair) and then write
        the requested value.
        """
        bucket = self._point.bucket
        address = self._point.address
        rounded = round(float(value), 1)

        if address == Addr.TEMP_MIN:
            partner = self._read_partner(bucket, Addr.TEMP_MAX)
            if partner is not None and rounded >= partner:
                await self.coordinator.async_set_number(
                    bucket,
                    Addr.TEMP_MAX,
                    round(rounded + MIN_MAX_SPREAD_C, 1),
                )
        elif address == Addr.TEMP_MAX:
            partner = self._read_partner(bucket, Addr.TEMP_MIN)
            if partner is not None and rounded <= partner:
                await self.coordinator.async_set_number(
                    bucket,
                    Addr.TEMP_MIN,
                    round(rounded - MIN_MAX_SPREAD_C, 1),
                )

        await self.coordinator.async_set_number(bucket, address, rounded)

    def _read_partner(self, bucket: str, address: str) -> float | None:
        """Return the current numeric value of the partner address, or ``None``."""
        value = self.coordinator.get_value(bucket, address)
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
