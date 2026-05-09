"""Sensor platform for the Sunthalpy integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.util import dt as dt_util

from .data import CALC_SENSORS, ENERGY_SENSORS, SENSORS
from .entity import SunthalpyEntity

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SunthalpyDataUpdateCoordinator
    from .data import (
        SunthalpyConfigEntry,
        SunthalpyEnergyPoint,
        SunthalpySensorPoint,
    )


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SunthalpyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register every sensor (raw, computed, and accumulated) for this entry."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = []
    entities.extend(
        SunthalpyValueSensor(coordinator, point)
        for point in (*SENSORS, *CALC_SENSORS)
    )
    entities.extend(
        SunthalpyEnergySensor(coordinator, point) for point in ENERGY_SENSORS
    )
    async_add_entities(entities)


class SunthalpyValueSensor(SunthalpyEntity, SensorEntity):
    """Sensor backed by a single (bucket, address) value in the snapshot."""

    def __init__(
        self,
        coordinator: SunthalpyDataUpdateCoordinator,
        point: SunthalpySensorPoint,
    ) -> None:
        """Initialise from a descriptor."""
        super().__init__(coordinator, point.unique_suffix)
        self._point = point
        # ``translation_key`` is what HA looks up in translations/<lang>.json
        # under ``entity.sensor.<key>.name``. We deliberately don't set
        # ``_attr_name`` because that would short-circuit the lookup.
        self._attr_translation_key = point.unique_suffix
        self._attr_native_unit_of_measurement = point.unit
        self._attr_device_class = point.device_class
        self._attr_state_class = point.state_class
        self._attr_icon = point.icon
        self._attr_entity_category = point.entity_category
        self._attr_entity_registry_enabled_default = point.enabled_by_default
        self._attr_options = list(point.options) if point.options else None
        self._attr_suggested_display_precision = point.suggested_display_precision

    @property
    def native_value(self) -> Any:
        """Return the latest value, or ``None`` if it isn't available."""
        data = self.coordinator.data or {}
        bucket = data.get("buckets", {}).get(self._point.bucket, {})
        value = bucket.get(self._point.address)
        if value is None:
            return None
        if self._point.options is not None:
            return value if value in self._point.options else None
        if isinstance(value, bool):
            return None
        return value

    @property
    def available(self) -> bool:
        """Match the parent rule, but require the value to be present."""
        if not super().available:
            return False
        data = self.coordinator.data or {}
        bucket = data.get("buckets", {}).get(self._point.bucket, {})
        return bucket.get(self._point.address) is not None


class SunthalpyEnergySensor(SunthalpyEntity, SensorEntity):
    """Sensor backed by a coordinator-side energy / runtime accumulator.

    Daily sensors expose ``last_reset`` so that Home Assistant draws their
    long-term statistics as a recurring cycle.
    """

    def __init__(
        self,
        coordinator: SunthalpyDataUpdateCoordinator,
        point: SunthalpyEnergyPoint,
    ) -> None:
        """Initialise from a descriptor."""
        super().__init__(coordinator, point.unique_suffix)
        self._point = point
        self._attr_translation_key = point.unique_suffix
        self._attr_native_unit_of_measurement = point.unit
        self._attr_device_class = point.device_class
        self._attr_icon = point.icon
        self._attr_suggested_display_precision = point.suggested_display_precision
        self._attr_entity_registry_enabled_default = point.enabled_by_default
        # Daily sensors: TOTAL with last_reset (HA renders as a cycle).
        # Lifetime sensors: TOTAL_INCREASING (Energy Dashboard friendly).
        self._attr_state_class = (
            SensorStateClass.TOTAL if point.daily else SensorStateClass.TOTAL_INCREASING
        )

    @property
    def native_value(self) -> float | None:
        """Return the current accumulator value in the right unit."""
        data = self.coordinator.data or {}
        bucket = "energy_daily" if self._point.daily else "energy_total"
        value = data.get(bucket, {}).get(self._point.category)
        if value is None:
            return None
        return round(float(value), 4)

    @property
    def last_reset(self) -> datetime | None:
        """Return midnight today for daily sensors; ``None`` otherwise."""
        if not self._point.daily:
            return None
        data = self.coordinator.data or {}
        iso_date = data.get("last_reset_daily")
        if not iso_date:
            return None
        try:
            local_midnight = dt_util.start_of_local_day(
                dt_util.parse_datetime(f"{iso_date}T00:00:00")
                or dt_util.now(),
            )
        except (TypeError, ValueError):
            return None
        return local_midnight
