"""Constants for the Sunthalpy integration."""

from __future__ import annotations

from logging import Logger, getLogger
from typing import Any, Final


def is_truthy(value: Any) -> bool:
    """Return ``True`` if ``value`` represents a "set" boolean state.

    The Sunthalpy API uses ``0/1``, ``"0"/"1"``, ``True/False``, and
    occasionally string variants of ``on``/``off`` to encode booleans, so
    every entity that interprets a boolean address should funnel through
    this helper.
    """
    if value is None:
        return False
    return value in TRUTHY_VALUES


LOGGER: Logger = getLogger(__package__)

DOMAIN: Final = "sunthalpy"
MANUFACTURER: Final = "Sunthalpy"
MODEL: Final = "Aerothermal home"
ATTRIBUTION: Final = "Data provided by Sunthalpy"

# Network configuration
BASE_URL: Final = "https://cliente.sunthalpy.com:12345/api/client"
HEADERS: Final[dict[str, str]] = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
}
HTTP_TIMEOUT_S: Final = 10
DEFAULT_SCAN_INTERVAL_S: Final = 60

# Storage / recorder hints
STORAGE_VERSION: Final = 1
STORAGE_KEY_FMT: Final = "sunthalpy_energy_{entry_id}"

# After a switch/number write the API can take several seconds to start
# returning the new value. We keep the optimistic write live for this many
# poll cycles before giving up and trusting whatever the API reports.
PENDING_WRITE_POLLS: Final = 2

# Set of values the API uses to mean "true" for boolean addresses.
TRUTHY_VALUES: Final[frozenset[Any]] = frozenset(
    {True, 1, "1", "true", "True", "TRUE", "on", "ON", "On"},
)

# UUIDs identifying which "device" the data belongs to in the API
UUIDS: Final[dict[str, str]] = {
    "user_sets": "0e115d1a-9786-403b-831d-10ec07b7d906",
    "main_data": "be539f06-ed9c-4a84-96c2-0cf2b002ac31",
    "other_data": "5f1b91c4-2311-49eb-804c-7d73e6e7fbcc",
}

# Synthetic / computed bucket — values produced by the coordinator
CALC_BUCKET: Final = "calc_data"

# ---------------------------------------------------------------------------
# Physical safety bounds
# ---------------------------------------------------------------------------
# Aerothermal heat pumps in residential settings rarely exceed ~30 kW.
# The API has been observed to occasionally return values >100 kW, which
# are physically impossible for this kind of equipment. We clamp at 50 kW
# to leave some headroom and still discard obviously bogus spikes.
MAX_THERMAL_POWER_KW: Final = 50.0
MAX_ELECTRIC_POWER_KW: Final = 50.0

# Performance coefficients — physically capped at ~10 in extreme conditions
MAX_COP: Final = 10.0
MAX_EER: Final = 10.0

# Reasonable household pressure range
MAX_CIRCUIT_PRESSURE_BAR: Final = 5.0

# Temperature clamps
TEMP_MIN_C_INDOOR: Final = 0.0
TEMP_MAX_C_INDOOR: Final = 60.0
TEMP_MIN_C_OUTDOOR: Final = -50.0
TEMP_MAX_C_OUTDOOR: Final = 60.0
TEMP_MIN_C_CIRCUIT: Final = 0.0
TEMP_MAX_C_CIRCUIT: Final = 90.0
TEMP_MIN_C_ACS: Final = 0.0
TEMP_MAX_C_ACS: Final = 90.0

# ACS detection heuristic: when return-water temp is this many degrees
# above the heating setpoint, the unit is producing domestic hot water
# rather than space heating.
ACS_RETURN_OFFSET_C: Final = 5.0


# ---------------------------------------------------------------------------
# Aerothermal operating modes
# ---------------------------------------------------------------------------
class AeroMode:
    """Operating modes the aerothermal unit can be in."""

    IDLE: Final = "idle"
    COOLING: Final = "cooling"
    HEATING: Final = "heating"
    ACS: Final = "acs"
    ACS_HEATING_WAITING: Final = "acs_heating_waiting"
    ACS_COOLING_WAITING: Final = "acs_cooling_waiting"
    UNKNOWN: Final = "unknown"


AERO_MODES: Final[tuple[str, ...]] = (
    AeroMode.IDLE,
    AeroMode.COOLING,
    AeroMode.HEATING,
    AeroMode.ACS,
    AeroMode.ACS_HEATING_WAITING,
    AeroMode.ACS_COOLING_WAITING,
    AeroMode.UNKNOWN,
)

# Modes where the unit is actively running (used for runtime accumulation).
ACTIVE_MODES: Final[frozenset[str]] = frozenset(
    {
        AeroMode.COOLING,
        AeroMode.HEATING,
        AeroMode.ACS,
        AeroMode.ACS_HEATING_WAITING,
        AeroMode.ACS_COOLING_WAITING,
    }
)


# ---------------------------------------------------------------------------
# API addresses (as strings — that is how the upstream API keys them)
# ---------------------------------------------------------------------------
class Addr:
    """Human-readable aliases for the numeric API addresses."""

    # user_sets
    AT_HOME: Final = "0000"
    WINTER_MODE: Final = "0100"
    TEMP_MIN: Final = "1100"
    TEMP_MAX: Final = "1101"
    NGROK_ON: Final = "1800"

    # main_data
    INDOOR_HUMIDITY: Final = "102"
    INDOOR_TEMP: Final = "103"

    # other_data
    SUPPLY_TEMP_INDOOR: Final = "1"
    RETURN_TEMP_INDOOR: Final = "2"
    SUPPLY_TEMP_OUTDOOR: Final = "4"
    RETURN_TEMP_OUTDOOR: Final = "5"
    CIRCUIT_PRESSURE: Final = "6"
    ACS_TEMP: Final = "11"
    OUTDOOR_TEMP: Final = "20"
    ALARM: Final = "32"
    POWER_HEAT: Final = "133"
    POWER_COOL: Final = "134"
    POWER_ELEC: Final = "135"
    COP: Final = "136"
    EER: Final = "137"
    SETPOINT_ACS: Final = "168"
    SETPOINT_HEAT: Final = "170"
    SETPOINT_COOL: Final = "175"
    SUMMER_MODE_ONLINE: Final = "201"
    WINTER_MODE_ONLINE: Final = "202"
    COMPRESSOR_RPM: Final = "5002"
    BUS_DEMAND_ACS: Final = "5181"
    BUS_DEMAND_DG1: Final = "5183"
    BUS_PROGRAM: Final = "5188"
    BUS_PUMP_ON: Final = "5257"

    # calc_data (synthetic)
    DEW_POINT: Final = "0000"
    AERO_STATE: Final = "0001"
    IS_ON: Final = "0002"


# ---------------------------------------------------------------------------
# Energy categories — every category produces a daily and a cumulative sensor
# ---------------------------------------------------------------------------
class EnergyCat:
    """Stable identifiers for accumulated energy buckets."""

    THERMAL_HEAT_TOTAL: Final = "thermal_heat_total"
    THERMAL_COOL_TOTAL: Final = "thermal_cool_total"
    THERMAL_HEAT_HEATING: Final = "thermal_heat_heating"
    THERMAL_HEAT_ACS: Final = "thermal_heat_acs"
    THERMAL_COOL_COOLING: Final = "thermal_cool_cooling"
    ELECTRIC_TOTAL: Final = "electric_total"
    ELECTRIC_HEATING: Final = "electric_heating"
    ELECTRIC_COOLING: Final = "electric_cooling"
    ELECTRIC_ACS: Final = "electric_acs"
    RUNTIME_HOURS: Final = "runtime_hours"
