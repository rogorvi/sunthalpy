"""Data update coordinator for the Sunthalpy integration."""

from __future__ import annotations

from datetime import timedelta
from math import log
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import (
    SunthalpyApiAuthenticationError,
    SunthalpyApiClient,
    SunthalpyApiError,
)
from .const import (
    ACS_RETURN_OFFSET_C,
    ACTIVE_MODES,
    CALC_BUCKET,
    DEFAULT_SCAN_INTERVAL_S,
    DOMAIN,
    LOGGER,
    MAX_ELECTRIC_POWER_KW,
    MAX_THERMAL_POWER_KW,
    PENDING_WRITE_POLLS,
    STORAGE_KEY_FMT,
    STORAGE_VERSION,
    Addr,
    AeroMode,
    EnergyCat,
    is_truthy,
)
from .data import (
    BINARY_SENSORS,
    NUMBERS,
    SENSORS,
    default_energy_state,
)

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

    from .data import SunthalpyConfigEntry


class SunthalpyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    Fetch, sanitise, and integrate Sunthalpy data.

    The coordinator is responsible for the integration's whole "data
    pipeline":

    * call the cloud API,
    * clamp implausible readings to ``None`` (so HA shows them as
      unavailable rather than as a poisoned graph spike),
    * compute synthetic values (dew point, aero state, on/off),
    * accumulate energy and runtime via trapezoidal integration,
    * persist the accumulators in HA's :class:`Store` so they survive
      restarts.

    Returned ``data`` shape::

        {
            "buckets": { <bucket>: { <address>: <clamped value> } },
            "energy_total": { <category>: <kWh or hours> },
            "energy_daily": { <category>: <kWh or hours> },
            "last_reset_daily": <isoformat date>,
        }
    """

    config_entry: SunthalpyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SunthalpyConfigEntry,
        client: SunthalpyApiClient,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_S),
        )
        self._client = client
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY_FMT.format(entry_id=entry.entry_id),
        )
        # Previous-poll snapshot used by trapezoidal integration.
        self._prev_powers: dict[str, float] | None = None
        self._prev_mode: str | None = None
        self._prev_timestamp: datetime | None = None
        # Accumulators (initialised lazily from the store on first refresh).
        self._energy_total: dict[str, float] = default_energy_state()
        self._energy_daily: dict[str, float] = default_energy_state()
        self._last_reset_daily: str | None = None
        self._loaded = False
        # Optimistic writes: maps (bucket, address) -> (value, expires_at).
        # The pending value is preferred over the next poll's value until
        # either the API confirms it (i.e. starts returning the same
        # value) or the TTL expires, whichever comes first.
        self._pending_writes: dict[
            tuple[str, str],
            tuple[Any, datetime],
        ] = {}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    async def _async_load_state(self) -> None:
        """Restore accumulators from disk on the first refresh."""
        if self._loaded:
            return
        stored = await self._store.async_load()
        if isinstance(stored, dict):
            self._energy_total.update(
                {k: float(v) for k, v in stored.get("total", {}).items()},
            )
            self._energy_daily.update(
                {k: float(v) for k, v in stored.get("daily", {}).items()},
            )
            self._last_reset_daily = stored.get("last_reset_daily")
        self._loaded = True

    async def _async_save_state(self) -> None:
        """Write accumulators to disk."""
        await self._store.async_save(
            {
                "total": self._energy_total,
                "daily": self._energy_daily,
                "last_reset_daily": self._last_reset_daily,
            },
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh data, integrate, and return the new snapshot."""
        await self._async_load_state()
        try:
            raw = await self._client.async_get_data()
        except SunthalpyApiAuthenticationError as exc:
            raise ConfigEntryAuthFailed(exc) from exc
        except SunthalpyApiError as exc:
            raise UpdateFailed(exc) from exc

        buckets = self._sanitise(raw)
        buckets = self._apply_pending_writes(buckets)

        # Compute synthetic values from the (already clamped) raw values.
        calc = buckets.setdefault(CALC_BUCKET, {})
        calc[Addr.DEW_POINT] = self._dew_point(
            buckets.get("main_data", {}).get(Addr.INDOOR_TEMP),
            buckets.get("main_data", {}).get(Addr.INDOOR_HUMIDITY),
        )
        mode = self._aero_mode(buckets)
        calc[Addr.AERO_STATE] = mode
        calc[Addr.IS_ON] = mode in ACTIVE_MODES

        # Accumulate energy and runtime.
        self._integrate(buckets, mode)

        # Persist (best effort — failures are logged but not surfaced).
        try:
            await self._async_save_state()
        except Exception:  # noqa: BLE001 - storage errors should not crash polling
            LOGGER.exception("Failed to persist Sunthalpy accumulators")

        return {
            "buckets": buckets,
            "energy_total": dict(self._energy_total),
            "energy_daily": dict(self._energy_daily),
            "last_reset_daily": self._last_reset_daily,
        }

    # ------------------------------------------------------------------
    # Helpers exposed to the entity layer
    # ------------------------------------------------------------------
    def get_value(self, bucket: str, address: str) -> Any:
        """Return the current value for ``(bucket, address)`` from the snapshot."""
        if self.data is None:
            return None
        return self.data.get("buckets", {}).get(bucket, {}).get(address)

    async def async_set_switch(
        self,
        bucket: str,
        address: str,
        *,
        value: bool,
    ) -> None:
        """
        Push a switch change to the API and reflect it in the UI immediately.

        We do not call :meth:`async_request_refresh` here on purpose. The
        API takes a few seconds to start returning the new value, so an
        immediate refetch would rewrite the UI back to the old state.
        Instead we record the desired value as a "pending write" that
        overrides the next few polls until the API agrees.
        """
        await self._client.async_set_switch(bucket, address, value=value)
        self._record_optimistic(bucket, address, value)

    async def async_set_number(
        self,
        bucket: str,
        address: str,
        value: float,
    ) -> None:
        """Push a number change to the API and reflect it in the UI immediately."""
        rounded = round(float(value), 1)
        await self._client.async_set_number(bucket, address, rounded)
        self._record_optimistic(bucket, address, rounded)

    def _record_optimistic(
        self,
        bucket: str,
        address: str,
        value: Any,
    ) -> None:
        """Register a pending write and notify listeners with the new value."""
        ttl = timedelta(seconds=DEFAULT_SCAN_INTERVAL_S * PENDING_WRITE_POLLS)
        self._pending_writes[(bucket, address)] = (
            value,
            dt_util.utcnow() + ttl,
        )
        if self.data is None:
            return
        # Build a shallow copy of the snapshot with the new value patched
        # in. ``async_set_updated_data`` requires a new top-level dict
        # for change detection to fire.
        new_buckets = {
            name: dict(payload) for name, payload in self.data["buckets"].items()
        }
        new_buckets.setdefault(bucket, {})[address] = value
        self.async_set_updated_data({**self.data, "buckets": new_buckets})

    def _apply_pending_writes(
        self,
        buckets: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """
        Override polled values with still-pending optimistic writes.

        Pending writes that the API has caught up with (or that have
        outlived their TTL) are dropped. The rest are written into the
        bucket dict so every downstream consumer (entities, energy
        integration, aero-state computation) sees a consistent value.
        """
        if not self._pending_writes:
            return buckets
        now = dt_util.utcnow()
        out = {name: dict(payload) for name, payload in buckets.items()}
        for key, (value, expires_at) in list(self._pending_writes.items()):
            bucket, address = key
            if now > expires_at:
                LOGGER.debug(
                    "Pending write %s/%s expired without confirmation; "
                    "trusting API value %r",
                    bucket,
                    address,
                    out.get(bucket, {}).get(address),
                )
                del self._pending_writes[key]
                continue
            api_value = out.get(bucket, {}).get(address)
            if self._values_equivalent(api_value, value):
                LOGGER.debug(
                    "Pending write %s/%s confirmed by API",
                    bucket,
                    address,
                )
                del self._pending_writes[key]
            else:
                out.setdefault(bucket, {})[address] = value
        return out

    @staticmethod
    def _values_equivalent(api_value: Any, pending_value: Any) -> bool:
        """Return ``True`` if ``api_value`` represents the same state as pending."""
        if api_value is None:
            return False
        if isinstance(pending_value, bool):
            return is_truthy(api_value) == pending_value
        try:
            return abs(float(api_value) - float(pending_value)) < 0.05  # noqa: PLR2004
        except TypeError, ValueError:
            return str(api_value) == str(pending_value)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        """Best-effort cast to ``float``; return ``None`` on failure."""
        if value is None or isinstance(value, bool):
            # ``bool`` inherits ``int`` — keep it as bool by returning None.
            return None
        try:
            return float(value)
        except TypeError, ValueError:
            return None

    def _sanitise(
        self,
        raw: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """
        Apply per-address clamps to discard implausible readings.

        Anything outside the configured physical range (set in
        :mod:`.data`) is replaced with ``None`` so HA reports the entity
        as ``unavailable`` rather than rendering a spike that poisons
        long-term statistics.
        """
        # Build a per-(bucket, address) clamp table once.
        clamps: dict[tuple[str, str], tuple[float | None, float | None]] = {}
        for desc in (*SENSORS, *BINARY_SENSORS, *NUMBERS):
            if desc.clamp_min is None and desc.clamp_max is None:
                continue
            clamps[(desc.bucket, desc.address)] = (
                desc.clamp_min,
                desc.clamp_max,
            )

        out: dict[str, dict[str, Any]] = {}
        for bucket, payload in raw.items():
            cleaned: dict[str, Any] = {}
            for address, value in payload.items():
                bounds = clamps.get((bucket, address))
                if bounds is None:
                    cleaned[address] = value
                    continue
                low, high = bounds
                num = self._coerce_float(value)
                if num is None:
                    cleaned[address] = value
                    continue
                if low is not None and num < low:
                    LOGGER.debug(
                        "Discarding %s/%s: %s < %s",
                        bucket,
                        address,
                        num,
                        low,
                    )
                    cleaned[address] = None
                elif high is not None and num > high:
                    LOGGER.debug(
                        "Discarding %s/%s: %s > %s",
                        bucket,
                        address,
                        num,
                        high,
                    )
                    cleaned[address] = None
                else:
                    cleaned[address] = num
            out[bucket] = cleaned
        return out

    @staticmethod
    def _dew_point(temp: Any, humidity: Any) -> float | None:
        """
        Return dew point (°C) using the Magnus-Tetens approximation.

        ``temp`` is in °C and ``humidity`` is in %. ``None`` is returned
        for missing or implausible inputs.
        """
        if not isinstance(temp, (int, float)) or not isinstance(
            humidity,
            (int, float),
        ):
            return None
        if humidity <= 0 or humidity > 100:  # noqa: PLR2004
            return None
        b = 17.625
        c = 243.04
        gamma = log(humidity / 100) + (b * temp) / (c + temp)
        return round(c * gamma / (b - gamma), 2)

    @staticmethod
    def _aero_mode(buckets: dict[str, dict[str, Any]]) -> str:
        """Decide which mode the unit is in from the latest readings."""
        other = buckets.get("other_data", {})
        pot_heat = other.get(Addr.POWER_HEAT)
        pot_cool = other.get(Addr.POWER_COOL)
        return_temp = other.get(Addr.RETURN_TEMP_INDOOR)
        target_heat = other.get(Addr.SETPOINT_HEAT)
        is_winter_raw = other.get(Addr.WINTER_MODE_ONLINE)
        dg1_raw = other.get(Addr.BUS_DEMAND_DG1)
        aero_mode = AeroMode.UNKNOWN

        if pot_heat is None or pot_cool is None:
            aero_mode = AeroMode.UNKNOWN
        elif pot_heat == 0 and pot_cool == 0:
            aero_mode = AeroMode.IDLE
        elif pot_cool > 0:
            aero_mode = AeroMode.COOLING
        elif pot_heat > 0:
            if (
                return_temp is None
                or target_heat is None
                or return_temp <= target_heat + ACS_RETURN_OFFSET_C
            ):
                return AeroMode.HEATING
            # Producing DHW. Detect whether the unit is also waiting on
            # space conditioning (high DG1 demand bus).
            dg1_active = str(dg1_raw) == "1"
            if dg1_active:
                is_winter = str(is_winter_raw) == "1"
                return (
                    AeroMode.ACS_HEATING_WAITING
                    if is_winter
                    else AeroMode.ACS_COOLING_WAITING
                )
            return AeroMode.ACS
        return aero_mode

    # ------------------------------------------------------------------
    # Energy integration
    # ------------------------------------------------------------------
    def _maybe_reset_daily(self, now_local: datetime) -> None:
        """Reset the daily counters at the local-midnight rollover."""
        today = now_local.date().isoformat()
        if self._last_reset_daily != today:
            LOGGER.debug(
                "Daily energy reset: %s -> %s",
                self._last_reset_daily,
                today,
            )
            self._energy_daily = default_energy_state()
            self._last_reset_daily = today

    def _bump(self, category: str, increment: float) -> None:
        """Add ``increment`` (≥ 0) to both the total and daily accumulator."""
        if increment <= 0:
            return
        self._energy_total[category] = self._energy_total.get(category, 0.0) + increment
        self._energy_daily[category] = self._energy_daily.get(category, 0.0) + increment

    def _integrate(
        self,
        buckets: dict[str, dict[str, Any]],
        mode: str,
    ) -> None:
        """
        Run one trapezoidal-integration step over the new sample.

        Powers are read from the (already clamped) buckets. Any sample
        that is missing or wildly out of range is treated as zero — that
        is conservative and keeps a single bad poll from skewing the
        cumulative numbers.
        """
        now = dt_util.utcnow()
        now_local = dt_util.as_local(now)
        self._maybe_reset_daily(now_local)

        other = buckets.get("other_data", {})
        powers = {
            "heat": self._safe_power(
                other.get(Addr.POWER_HEAT),
                MAX_THERMAL_POWER_KW,
            ),
            "cool": self._safe_power(
                other.get(Addr.POWER_COOL),
                MAX_THERMAL_POWER_KW,
            ),
            "elec": self._safe_power(
                other.get(Addr.POWER_ELEC),
                MAX_ELECTRIC_POWER_KW,
            ),
        }

        if (
            self._prev_powers is None
            or self._prev_timestamp is None
            or self._prev_mode is None
        ):
            # First sample after start: nothing to integrate against yet.
            self._prev_powers = powers
            self._prev_timestamp = now
            self._prev_mode = mode
            return

        delta_s = (now - self._prev_timestamp).total_seconds()
        # If something nasty happens (clock change, paused integration),
        # cap the step at twice the configured interval to avoid huge
        # spurious increments.
        max_step_s = DEFAULT_SCAN_INTERVAL_S * 2
        if delta_s <= 0 or delta_s > max_step_s:
            self._prev_powers = powers
            self._prev_timestamp = now
            self._prev_mode = mode
            return
        delta_h = delta_s / 3600.0

        # Trapezoidal averages between the two samples.
        avg_heat = 0.5 * (self._prev_powers["heat"] + powers["heat"])
        avg_cool = 0.5 * (self._prev_powers["cool"] + powers["cool"])
        avg_elec = 0.5 * (self._prev_powers["elec"] + powers["elec"])

        # Total thermal / electric energy, regardless of mode.
        self._bump(EnergyCat.THERMAL_HEAT_TOTAL, avg_heat * delta_h)
        self._bump(EnergyCat.THERMAL_COOL_TOTAL, avg_cool * delta_h)
        self._bump(EnergyCat.ELECTRIC_TOTAL, avg_elec * delta_h)

        # Mode-attributed buckets — the prev/curr modes can disagree
        # (the unit transitioned during the interval); we attribute the
        # whole step to whichever mode is "active" right now, which is a
        # reasonable approximation given a 60-second poll.
        if mode == AeroMode.HEATING:
            self._bump(EnergyCat.THERMAL_HEAT_HEATING, avg_heat * delta_h)
            self._bump(EnergyCat.ELECTRIC_HEATING, avg_elec * delta_h)
        elif mode == AeroMode.COOLING:
            self._bump(EnergyCat.THERMAL_COOL_COOLING, avg_cool * delta_h)
            self._bump(EnergyCat.ELECTRIC_COOLING, avg_elec * delta_h)
        elif mode in {
            AeroMode.ACS,
            AeroMode.ACS_HEATING_WAITING,
            AeroMode.ACS_COOLING_WAITING,
        }:
            self._bump(EnergyCat.THERMAL_HEAT_ACS, avg_heat * delta_h)
            self._bump(EnergyCat.ELECTRIC_ACS, avg_elec * delta_h)

        # Runtime: count the interval if the unit was active at *both*
        # endpoints — that avoids double-counting brief transient spikes.
        if mode in ACTIVE_MODES and self._prev_mode in ACTIVE_MODES:
            self._bump(EnergyCat.RUNTIME_HOURS, delta_h)

        self._prev_powers = powers
        self._prev_timestamp = now
        self._prev_mode = mode

    @staticmethod
    def _safe_power(value: Any, ceiling: float) -> float:
        """Coerce ``value`` to a non-negative power below ``ceiling``."""
        if value is None or isinstance(value, bool):
            return 0.0
        try:
            num = float(value)
        except TypeError, ValueError:
            return 0.0
        if num < 0 or num > ceiling:
            return 0.0
        return num
