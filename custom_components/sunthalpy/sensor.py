"""Sensor platform for sunthalpy."""

from __future__ import annotations

from datetime import timedelta
from math import floor
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import DEFAULT_UPDATE_MIN, LOGGER
from .entity import IntegrationBlueprintEntity
from .sunthalhome import (
    BinarySunthalDataPoint,
    HistSensorSunthalDataPoint,
    NumberSunthalDataPoint,
    SensorSunthalDataPoint,
    SunthalDataPoint,
    SwitchSunthalDataPoint,
    calc_sensors,
    hist_sensors,
    sensors,
)

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Any

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import BlueprintDataUpdateCoordinator
    from .data import IntegrationBlueprintConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationBlueprintConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all sensors."""
    # Set up the sensor platform."""
    async_add_entities(
        IntegrationBlueprintSensor(
            coordinator=entry.runtime_data.coordinator,
            sensor_data=elem,
        )
        for elem in sensors + calc_sensors
    )
    # Set up the history sensor platform.
    async_add_entities(
        IntegralSensor(
            hass,
            coordinator=entry.runtime_data.coordinator,
            sensor_data=elem,
        )
        for elem in hist_sensors
        if not elem.reset_daily
    )
    # Set up the history sensor platform.
    async_add_entities(
        DailyIntegralSensor(
            hass,
            coordinator=entry.runtime_data.coordinator,
            sensor_data=elem,
        )
        for elem in hist_sensors
        if elem.reset_daily
    )


class IntegrationBlueprintSensor(IntegrationBlueprintEntity, SensorEntity):
    """sunthalpy Sensor class."""

    def __init__(
        self,
        coordinator: BlueprintDataUpdateCoordinator,
        sensor_data: SunthalDataPoint
        | BinarySunthalDataPoint
        | NumberSunthalDataPoint
        | SwitchSunthalDataPoint
        | SensorSunthalDataPoint,
    ) -> None:
        """Initialize the sensor class."""
        name = sensor_data.name if type(sensor_data.name) is str else ""
        target_entity_id = (
            f"{self.platform}.{slugify(coordinator.config_entry.title)}_{slugify(name)}"
        )
        self.entity_id = target_entity_id
        self.name = name
        super().__init__(coordinator, name)
        self.sensor_data = sensor_data

        # Set appropriate attributes
        if type(sensor_data) is SensorSunthalDataPoint:
            self._attr_state_class = sensor_data.state_class
            self._attr_device_class = sensor_data.device_class
        self._attr_native_unit_of_measurement = sensor_data.unit
        self._attr_suggested_display_precision = 1
        self.entity_registry_enabled_default = sensor_data.start_enabled

    def _get_sensor_data(self) -> Any:
        """Get the sensor data from coordinator."""
        if self.coordinator.data is None:
            return None

        data = self.coordinator.data.get(self.sensor_data.uuid_name, {})

        return (
            data.get("obj", {})
            .get("lastMeasure", {})
            .get(self.sensor_data.address, None)
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        return self._get_sensor_data() is not None

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        value = self._get_sensor_data()

        # Apply clamping if configured
        if value is not None:
            clamp_min = self.sensor_data.clamp_min
            clamp_max = self.sensor_data.clamp_max

            if clamp_min is not None and value < clamp_min:
                LOGGER.info(
                    f"Clamped value of {self.name}. "
                    f"Original value {value}, "
                    f"converted to {clamp_min}."
                )
                return clamp_min
            if clamp_max is not None and value > clamp_max:
                LOGGER.info(
                    f"Clamped value of {self.name}. "
                    f"Original value {value}, "
                    f"converted to {clamp_max}."
                )
                return clamp_max

        return value


class IntegralSensor(IntegrationBlueprintEntity, RestoreEntity, SensorEntity):
    """Sensor that calculates the integral of another sensor (like utility meter)."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: BlueprintDataUpdateCoordinator,
        sensor_data: HistSensorSunthalDataPoint,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, sensor_data.name)
        self._hass = hass
        self._source_entity_id = (
            f"{sensor_data.source_entity_id.split('.')[0]}."
            f"{slugify(coordinator.config_entry.title)}_"
            f"{sensor_data.source_entity_id.split('.')[1]}"
        )

        self._attr_name = sensor_data.name

        # State tracking
        self._state = 0
        self._last_value = None
        self._last_update = None

        # Race condition protection
        self._is_updating = False

        # Set appropriate attributes
        self._attr_state_class = sensor_data.state_class
        self._attr_device_class = sensor_data.device_class
        self._attr_native_unit_of_measurement = sensor_data.unit
        self._attr_suggested_display_precision = 1
        self.entity_registry_enabled_default = sensor_data.start_enabled

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

    def _update_integral(self, current_value: float, current_time: datetime) -> None:
        """
        Update integral calculation.

        Note: This method must be called while holding self._update_lock
        to prevent race conditions.
        """
        if self._last_value is not None and self._last_update is not None:
            time_diff = (current_time - self._last_update).total_seconds() / 3600
            increment = ((self._last_value + current_value) / 2) * time_diff
            self._state += increment

        self._last_value = current_value
        self._last_update = current_time

    def _on_start_func_register(self) -> None:
        """Register callbacks."""
        # Track state changes of the source sensor
        self.async_on_remove(
            async_track_state_change_event(
                self._hass,
                [self._source_entity_id],
                self._async_sensor_changed,
            )
        )

        # Update as often as the rest of the sensors
        if self.coordinator.update_interval is None:
            interval_mins: int = DEFAULT_UPDATE_MIN
        else:
            interval_mins: int = max(
                floor(self.coordinator.update_interval.seconds / 60), 1
            )

        self.async_on_remove(
            async_track_time_interval(
                self._hass,
                self._async_periodic_update,
                timedelta(minutes=interval_mins),
            )
        )

    def _post_process_restore(self) -> None:
        """Post process after restoring state. Can be overridden by subclasses."""

    async def async_added_to_hass(self) -> None:
        """Register callbacks and restore state when entity is added."""
        await super().async_added_to_hass()

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

                self._post_process_restore()

                LOGGER.debug(
                    f"Restored {self.name}: state={self._state}, "
                    f"last_value={self._last_value}, last_update={self._last_update}"
                )

            except (ValueError, TypeError) as ex:
                LOGGER.warning(f"Could not restore state: {ex}")

        # Initialize with current state if not restored
        # but don't fail if entity doesn't exist yet
        if self._last_value is None:
            source_state = self._hass.states.get(self._source_entity_id)
            if source_state and source_state.state not in ("unknown", "unavailable"):
                try:
                    self._last_value = float(source_state.state)
                    self._last_update = dt_util.utcnow()
                except ValueError:
                    LOGGER.debug(
                        f"Could not convert {source_state.state}"
                        f" to float for {self._source_entity_id}"
                    )

        # Register the listeners
        self._on_start_func_register()

    @callback
    def _async_sensor_changed(self, event) -> None:  # noqa: ANN001
        """Handle sensor state changes."""
        new_state = event.data.get("new_state")

        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            current_value = float(new_state.state)
        except ValueError:
            LOGGER.warning(
                "Could not convert %s to float for %s",
                new_state.state,
                self.name,
            )
            return

        # Schedule the actual update in a coroutine to use async lock
        self._hass.async_create_task(
            self._async_update_with_lock(current_value, dt_util.utcnow())
        )

    async def _async_update_with_lock(
        self, current_value: float, current_time: datetime
    ) -> None:
        """Update integral with lock protection."""
        if self._is_updating:
            LOGGER.debug("Update already in progress for %s, skipping", self.name)
            return

        self._is_updating = True
        try:
            self._update_integral(current_value, current_time)
            self.async_write_ha_state()
        finally:
            self._is_updating = False

    @callback
    def _async_periodic_update(self, now: datetime) -> None:  # noqa: ARG002
        """Periodic update every N minutes with race condition protection."""
        # Force an update with the current source sensor value
        source_state = self._hass.states.get(self._source_entity_id)

        if source_state is None or source_state.state in ("unknown", "unavailable"):
            return

        try:
            current_value = float(source_state.state)
        except ValueError:
            LOGGER.warning(
                "Could not convert %s to float for %s",
                source_state.state,
                self.name,
            )
            return

        # Schedule the actual update in a coroutine to use async lock
        self._hass.async_create_task(
            self._async_update_with_lock(current_value, dt_util.utcnow())
        )


class DailyIntegralSensor(IntegralSensor):
    """IntegralSensor that resets daily."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: BlueprintDataUpdateCoordinator,
        sensor_data: HistSensorSunthalDataPoint,
        # source_entity_id: str,
        # name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            hass,
            coordinator=coordinator,
            sensor_data=sensor_data,
        )

    def _on_start_func_register(self) -> None:
        """Register callbacks."""
        super()._on_start_func_register()

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

    @callback
    def _async_reset_daily(self, now: datetime) -> None:  # noqa: ARG002
        """Reset the sensor at midnight with race protection."""
        # Schedule async reset to use lock
        self._hass.async_create_task(self._async_reset_with_lock())

    async def _async_reset_with_lock(self) -> None:
        """Perform the actual reset with lock protection."""
        if self._is_updating:
            LOGGER.debug("Update already in progress for %s, skipping", self.name)
            return

        self._is_updating = True
        try:
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
        finally:
            self._is_updating = False

    def _post_process_restore(self) -> None:
        """Reset to 0 if it's a new day."""
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
