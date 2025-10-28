"""Sensor platform for sunthalpy."""

from __future__ import annotations

from datetime import timedelta
from math import floor
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import LOGGER
from .entity import IntegrationBlueprintEntity
from .sunthalhome import hist_sensors, sensors

if TYPE_CHECKING:
    from datetime import datetime

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
        icon=elem.icon,
    )
    for elem in sensors
)


async def async_setup_entry(
    hass: HomeAssistant,
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
    """Set up the history sensor platform."""
    async_add_entities(
        DailyIntegralSensor(
            hass,
            coordinator=entry.runtime_data.coordinator,
            name=elem.name,
            key=elem.name.replace(" ", "_").lower(),
            source_entity_id=elem.source_entity_id,
        )
        for elem in hist_sensors
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
        uuid_name, address = self.entity_description.key.split("--")
        data = self.coordinator.data.get(uuid_name, {})

        return (
            data.get("obj", {})
            .get("lastMeasure", {})
            .get(
                address,
                None,
            )
        )


class DailyIntegralSensor(IntegrationBlueprintEntity, RestoreEntity, SensorEntity):
    """Sensor that calculates daily integral of another sensor (like utility meter)."""

    def __init__(
        self,
        hass: HomeAssistant,
        source_entity_id: str,
        name: str,
        key: str,
        coordinator: BlueprintDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, key)
        self._hass = hass
        self._source_entity_id = source_entity_id
        self._attr_name = name
        self._attr_unique_id = f"{source_entity_id}_daily_integral"

        # State tracking
        self._state = 0
        self._last_value = None
        self._last_update = None

        # Set appropriate attributes
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_device_class = SensorDeviceClass.ENERGY  # Adjust based on your needs
        self._attr_native_unit_of_measurement = (
            UnitOfEnergy.KILO_WATT_HOUR
        )  # Adjust based on source sensor
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        return {
            "last_state": self._state,
            "last_value": self._last_value,
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

    def on_start_func_register(self) -> None:
        """Register callbacks."""
        # Track state changes of the source sensor
        self.async_on_remove(
            async_track_state_change_event(
                self._hass,
                [self._source_entity_id],
                self._async_sensor_changed,
            )
        )

        # Reset daily at midnight
        self.async_on_remove(
            async_track_time_change(
                self._hass,
                self._async_reset_daily,
                hour=0,
                minute=0,
                second=0,
            )
        )

        # Update as often as the rest of the sensors
        if self.coordinator.update_interval is None:
            interval_mins: int = 5
        else:
            interval_mins: int = floor(self.coordinator.update_interval.seconds / 60)

        self.async_on_remove(
            async_track_time_interval(
                self._hass,
                self._async_periodic_update,
                timedelta(minutes=interval_mins),
            )
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks  and restore state when entity is added."""
        await super().async_added_to_hass()

        self.on_start_func_register()

        # Restore previous state
        last_state = await self.async_get_last_state()

        if last_state is not None:
            try:
                # Restore additional attributes
                if last_state.attributes:
                    if (
                        "last_state" in last_state.attributes
                        and last_state.attributes["last_state"] is not None
                    ):
                        self._state = float(last_state.attributes["last_state"])

                    if (
                        "last_value" in last_state.attributes
                        and last_state.attributes["last_value"] is not None
                    ):
                        self._last_value = float(last_state.attributes["last_value"])

                    if (
                        "last_update" in last_state.attributes
                        and last_state.attributes["last_update"] is not None
                    ):
                        self._last_update = dt_util.parse_datetime(
                            last_state.attributes["last_update"]
                        )

                LOGGER.debug(
                    f"Restored {self.name}: state={self._state}, "
                    f"last_value={self._last_value}, last_update={self._last_update}"
                )

                # Check if we should reset (new day)
                if self._last_update is not None:
                    now = dt_util.now()
                    last_date = dt_util.as_local(self._last_update).date()
                    current_date = now.date()

                    if current_date > last_date:
                        LOGGER.debug(f"New day detected, resetting {self.name}")
                        self._state = 0
                        self._last_value = None
                        self._last_update = None

            except (ValueError, TypeError) as ex:
                LOGGER.warning(f"Could not restore state: {ex}")

        # Initialize with current state if not restored
        if self._last_value is None:
            source_state = self._hass.states.get(self._source_entity_id)
            if source_state and source_state.state not in ("unknown", "unavailable"):
                try:
                    self._last_value = float(source_state.state)
                    self._last_update = dt_util.utcnow()
                except ValueError:
                    LOGGER.warning("Could not convert %s to float", source_state.state)

    @callback
    def _async_sensor_changed(self, event) -> None:  # noqa: ANN001
        """Handle sensor state changes."""
        new_state = event.data.get("new_state")

        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            current_value = float(new_state.state)
            current_time = dt_util.utcnow()

            # Calculate integral (trapezoidal rule)
            if self._last_value is not None and self._last_update is not None:
                time_diff = (
                    current_time - self._last_update
                ).total_seconds() / 3600  # hours
                average_value = (self._last_value + current_value) / 2
                increment = average_value * time_diff

                self._state += increment

            self._last_value = current_value
            self._last_update = current_time

            self.async_write_ha_state()

        except ValueError:
            LOGGER.warning("Could not convert %s to float", new_state.state)

    @callback
    def _async_reset_daily(self, now: datetime) -> None:  # noqa: ARG002
        """Reset the sensor at midnight."""
        LOGGER.debug("Resetting daily integral sensor: %s", self.name)
        self._state = 0
        self._last_value = None
        self._last_update = None

        # Get current value to start fresh
        source_state = self._hass.states.get(self._source_entity_id)
        if source_state and source_state.state not in ("unknown", "unavailable"):
            try:
                self._last_value = float(source_state.state)
                self._last_update = dt_util.utcnow()
            except ValueError:
                pass

        self.async_write_ha_state()

    @callback
    def _async_periodic_update(self, now: datetime) -> None:  # noqa: ARG002
        """Periodic update every 5 minutes."""
        # Force an update with the current source sensor value
        source_state = self._hass.states.get(self._source_entity_id)

        if source_state is None or source_state.state in ("unknown", "unavailable"):
            return

        try:
            current_value = float(source_state.state)
            current_time = dt_util.utcnow()

            # Calculate integral (trapezoidal rule)
            if self._last_value is not None and self._last_update is not None:
                time_diff = (
                    current_time - self._last_update
                ).total_seconds() / 3600  # hours
                average_value = (self._last_value + current_value) / 2
                increment = average_value * time_diff

                self._state += increment

            self._last_value = current_value
            self._last_update = current_time

            self.async_write_ha_state()

        except ValueError:
            LOGGER.warning("Could not convert %s to float", source_state.state)
