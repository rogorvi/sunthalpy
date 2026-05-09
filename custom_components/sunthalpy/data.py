"""Type definitions and entity descriptors for the Sunthalpy integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)

from .const import (
    AERO_MODES,
    MAX_CIRCUIT_PRESSURE_BAR,
    MAX_COP,
    MAX_EER,
    MAX_ELECTRIC_POWER_KW,
    MAX_THERMAL_POWER_KW,
    TEMP_MAX_C_ACS,
    TEMP_MAX_C_CIRCUIT,
    TEMP_MAX_C_INDOOR,
    TEMP_MAX_C_OUTDOOR,
    TEMP_MIN_C_ACS,
    TEMP_MIN_C_CIRCUIT,
    TEMP_MIN_C_INDOOR,
    TEMP_MIN_C_OUTDOOR,
    Addr,
    EnergyCat,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import SunthalpyApiClient
    from .coordinator import SunthalpyDataUpdateCoordinator


type SunthalpyConfigEntry = ConfigEntry[SunthalpyData]


@dataclass
class SunthalpyData:
    """Runtime data attached to a Sunthalpy config entry."""

    client: SunthalpyApiClient
    coordinator: SunthalpyDataUpdateCoordinator
    integration: Integration


# ---------------------------------------------------------------------------
# Common descriptor base — every entity type extends this with platform-
# specific fields. Using a dataclass keeps the table-driven descriptions
# below readable and lets us share the clamp / icon / availability fields.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class SunthalpyPoint:
    """Generic descriptor for a Sunthalpy data point."""

    bucket: str
    address: str
    name: str
    unique_suffix: str
    unit: str | None = None
    icon: str | None = None
    enabled_by_default: bool = True
    entity_category: EntityCategory | None = None
    clamp_min: float | None = None
    clamp_max: float | None = None


@dataclass(frozen=True, kw_only=True)
class SunthalpySensorPoint(SunthalpyPoint):
    """Descriptor for a regular sensor entity."""

    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    options: tuple[str, ...] | None = None
    suggested_display_precision: int | None = None


@dataclass(frozen=True, kw_only=True)
class SunthalpyBinaryPoint(SunthalpyPoint):
    """Descriptor for a binary sensor entity."""

    device_class: BinarySensorDeviceClass | None = None


@dataclass(frozen=True, kw_only=True)
class SunthalpySwitchPoint(SunthalpyPoint):
    """Descriptor for a switch entity."""

    device_class: SwitchDeviceClass | None = None


@dataclass(frozen=True, kw_only=True)
class SunthalpyNumberPoint(SunthalpyPoint):
    """Descriptor for a number entity."""

    device_class: NumberDeviceClass | None = None
    min_value: float = 0.0
    max_value: float = 100.0
    step: float = 1.0
    mode: NumberMode = NumberMode.AUTO


@dataclass(frozen=True, kw_only=True)
class SunthalpyEnergyPoint:
    """
    Descriptor for an accumulated energy / runtime sensor.

    Energy points come in pairs (daily and total). The ``daily`` flag
    selects which of the two coordinator-side accumulators to read.
    """

    category: str
    name: str
    unique_suffix: str
    unit: str
    device_class: SensorDeviceClass
    daily: bool
    icon: str | None = None
    suggested_display_precision: int | None = 2
    enabled_by_default: bool = True


# ---------------------------------------------------------------------------
# Sensors — direct measurements from the API
# ---------------------------------------------------------------------------
SENSORS: tuple[SunthalpySensorPoint, ...] = (
    SunthalpySensorPoint(
        bucket="main_data",
        address=Addr.INDOOR_TEMP,
        name="Indoor temperature",
        unique_suffix="indoor_temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_INDOOR,
        clamp_max=TEMP_MAX_C_INDOOR,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="main_data",
        address=Addr.INDOOR_HUMIDITY,
        name="Indoor humidity",
        unique_suffix="indoor_humidity",
        unit=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=0,
        clamp_max=100,
        suggested_display_precision=0,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.OUTDOOR_TEMP,
        name="Outdoor temperature",
        unique_suffix="outdoor_temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_OUTDOOR,
        clamp_max=TEMP_MAX_C_OUTDOOR,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.SUPPLY_TEMP_INDOOR,
        name="Indoor supply temperature",
        unique_suffix="indoor_supply_temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_CIRCUIT,
        clamp_max=TEMP_MAX_C_CIRCUIT,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.RETURN_TEMP_INDOOR,
        name="Indoor return temperature",
        unique_suffix="indoor_return_temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_CIRCUIT,
        clamp_max=TEMP_MAX_C_CIRCUIT,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.SUPPLY_TEMP_OUTDOOR,
        name="Outdoor supply temperature",
        unique_suffix="outdoor_supply_temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_CIRCUIT,
        clamp_max=TEMP_MAX_C_CIRCUIT,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.RETURN_TEMP_OUTDOOR,
        name="Outdoor return temperature",
        unique_suffix="outdoor_return_temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_CIRCUIT,
        clamp_max=TEMP_MAX_C_CIRCUIT,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.ACS_TEMP,
        name="DHW temperature",
        unique_suffix="dhw_temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_ACS,
        clamp_max=TEMP_MAX_C_ACS,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.CIRCUIT_PRESSURE,
        name="Circuit pressure",
        unique_suffix="circuit_pressure",
        unit=UnitOfPressure.BAR,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=0,
        clamp_max=MAX_CIRCUIT_PRESSURE_BAR,
        suggested_display_precision=2,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.POWER_HEAT,
        name="Heating power",
        unique_suffix="power_heating",
        unit=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=0,
        clamp_max=MAX_THERMAL_POWER_KW,
        suggested_display_precision=2,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.POWER_COOL,
        name="Cooling power",
        unique_suffix="power_cooling",
        unit=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=0,
        clamp_max=MAX_THERMAL_POWER_KW,
        suggested_display_precision=2,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.POWER_ELEC,
        name="Electric power",
        unique_suffix="power_electric",
        unit=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=0,
        clamp_max=MAX_ELECTRIC_POWER_KW,
        suggested_display_precision=2,
    ),
    SunthalpySensorPoint(
        # COP / EER are dimensionless efficiency ratios that routinely
        # exceed 1.0, so the POWER_FACTOR device class would reject them.
        # We expose them as plain measurements with a custom icon.
        bucket="other_data",
        address=Addr.COP,
        name="COP",
        unique_suffix="cop",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        clamp_min=0,
        clamp_max=MAX_COP,
        suggested_display_precision=2,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.EER,
        name="EER",
        unique_suffix="eer",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:gauge",
        clamp_min=0,
        clamp_max=MAX_EER,
        suggested_display_precision=2,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.SETPOINT_ACS,
        name="DHW setpoint",
        unique_suffix="setpoint_dhw",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_ACS,
        clamp_max=TEMP_MAX_C_ACS,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.SETPOINT_HEAT,
        name="Heating setpoint",
        unique_suffix="setpoint_heating",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_CIRCUIT,
        clamp_max=TEMP_MAX_C_CIRCUIT,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.SETPOINT_COOL,
        name="Cooling setpoint",
        unique_suffix="setpoint_cooling",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        clamp_min=TEMP_MIN_C_CIRCUIT,
        clamp_max=TEMP_MAX_C_CIRCUIT,
        suggested_display_precision=1,
    ),
    # ----- Diagnostic-tier raw readouts ----------------------------------
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.COMPRESSOR_RPM,
        name="Compressor RPM",
        unique_suffix="compressor_rpm",
        unit=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        clamp_min=0,
        suggested_display_precision=0,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.BUS_DEMAND_ACS,
        name="Bus demand DHW",
        unique_suffix="bus_demand_dhw",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.BUS_DEMAND_DG1,
        name="Bus demand DG1",
        unique_suffix="bus_demand_dg1",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.BUS_PROGRAM,
        name="Bus program",
        unique_suffix="bus_program",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    SunthalpySensorPoint(
        bucket="other_data",
        address=Addr.BUS_PUMP_ON,
        name="Bus heat-pump enable",
        unique_suffix="bus_pump_on",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
)


# ---------------------------------------------------------------------------
# Computed sensors — values produced by the coordinator from raw measurements
# ---------------------------------------------------------------------------
CALC_SENSORS: tuple[SunthalpySensorPoint, ...] = (
    SunthalpySensorPoint(
        bucket="calc_data",
        address=Addr.DEW_POINT,
        name="Indoor dew point",
        unique_suffix="indoor_dew_point",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    SunthalpySensorPoint(
        bucket="calc_data",
        address=Addr.AERO_STATE,
        name="Aerothermal state",
        unique_suffix="aerothermal_state",
        device_class=SensorDeviceClass.ENUM,
        options=AERO_MODES,
        icon="mdi:heat-pump",
    ),
)


# ---------------------------------------------------------------------------
# Binary sensors
# ---------------------------------------------------------------------------
BINARY_SENSORS: tuple[SunthalpyBinaryPoint, ...] = (
    SunthalpyBinaryPoint(
        bucket="other_data",
        address=Addr.ALARM,
        name="Alarm",
        unique_suffix="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    SunthalpyBinaryPoint(
        bucket="calc_data",
        address=Addr.IS_ON,
        name="Running",
        unique_suffix="running",
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:heat-pump",
    ),
    SunthalpyBinaryPoint(
        bucket="user_sets",
        address=Addr.NGROK_ON,
        name="Ngrok online",
        unique_suffix="ngrok_online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    SunthalpyBinaryPoint(
        bucket="other_data",
        address=Addr.SUMMER_MODE_ONLINE,
        name="Summer mode online",
        unique_suffix="summer_mode_online",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
    SunthalpyBinaryPoint(
        bucket="other_data",
        address=Addr.WINTER_MODE_ONLINE,
        name="Winter mode online",
        unique_suffix="winter_mode_online",
        entity_category=EntityCategory.DIAGNOSTIC,
        enabled_by_default=False,
    ),
)


# ---------------------------------------------------------------------------
# Switches
# ---------------------------------------------------------------------------
SWITCHES: tuple[SunthalpySwitchPoint, ...] = (
    SunthalpySwitchPoint(
        bucket="user_sets",
        address=Addr.WINTER_MODE,
        name="Winter mode",
        unique_suffix="winter_mode",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:snowflake",
    ),
    SunthalpySwitchPoint(
        bucket="user_sets",
        address=Addr.AT_HOME,
        name="At home",
        unique_suffix="at_home",
        device_class=SwitchDeviceClass.SWITCH,
        icon="mdi:home-account",
    ),
)


# ---------------------------------------------------------------------------
# Numbers
# ---------------------------------------------------------------------------
NUMBERS: tuple[SunthalpyNumberPoint, ...] = (
    SunthalpyNumberPoint(
        bucket="user_sets",
        address=Addr.TEMP_MIN,
        name="Minimum temperature",
        unique_suffix="temperature_min",
        unit=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        min_value=17.9,
        max_value=27.9,
        step=0.1,
        mode=NumberMode.BOX,
        clamp_min=17.9,
        clamp_max=27.9,
    ),
    SunthalpyNumberPoint(
        bucket="user_sets",
        address=Addr.TEMP_MAX,
        name="Maximum temperature",
        unique_suffix="temperature_max",
        unit=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        min_value=18.0,
        max_value=28.0,
        step=0.1,
        mode=NumberMode.BOX,
        clamp_min=18.0,
        clamp_max=28.0,
    ),
)


# ---------------------------------------------------------------------------
# Energy / runtime sensors — every category produces a daily and a total.
# ---------------------------------------------------------------------------
def _energy_pair(
    category: str,
    name: str,
    suffix: str,
    *,
    is_runtime: bool = False,
    icon: str | None = None,
) -> tuple[SunthalpyEnergyPoint, SunthalpyEnergyPoint]:
    """Return a ``(daily, total)`` pair of descriptors for a category."""
    if is_runtime:
        unit = UnitOfTime.HOURS
        device_class = SensorDeviceClass.DURATION
    else:
        unit = UnitOfEnergy.KILO_WATT_HOUR
        device_class = SensorDeviceClass.ENERGY
    return (
        SunthalpyEnergyPoint(
            category=category,
            name=f"{name} (today)",
            unique_suffix=f"{suffix}_daily",
            unit=unit,
            device_class=device_class,
            daily=True,
            icon=icon,
        ),
        SunthalpyEnergyPoint(
            category=category,
            name=name,
            unique_suffix=f"{suffix}_total",
            unit=unit,
            device_class=device_class,
            daily=False,
            icon=icon,
        ),
    )


ENERGY_SENSORS: tuple[SunthalpyEnergyPoint, ...] = (
    *_energy_pair(
        EnergyCat.THERMAL_HEAT_TOTAL,
        "Heating thermal energy",
        "thermal_heat_total",
        icon="mdi:radiator",
    ),
    *_energy_pair(
        EnergyCat.THERMAL_COOL_TOTAL,
        "Cooling thermal energy",
        "thermal_cool_total",
        icon="mdi:snowflake-thermometer",
    ),
    *_energy_pair(
        EnergyCat.THERMAL_HEAT_HEATING,
        "Thermal energy used for heating",
        "thermal_heat_heating_mode",
        icon="mdi:radiator",
    ),
    *_energy_pair(
        EnergyCat.THERMAL_HEAT_ACS,
        "Thermal energy used for DHW",
        "thermal_heat_acs",
        icon="mdi:water-boiler",
    ),
    *_energy_pair(
        EnergyCat.THERMAL_COOL_COOLING,
        "Thermal energy used for cooling",
        "thermal_cool_cooling_mode",
        icon="mdi:snowflake-thermometer",
    ),
    *_energy_pair(
        EnergyCat.ELECTRIC_TOTAL,
        "Electric energy",
        "electric_total",
        icon="mdi:lightning-bolt",
    ),
    *_energy_pair(
        EnergyCat.ELECTRIC_HEATING,
        "Electric energy used for heating",
        "electric_heating",
        icon="mdi:lightning-bolt",
    ),
    *_energy_pair(
        EnergyCat.ELECTRIC_COOLING,
        "Electric energy used for cooling",
        "electric_cooling",
        icon="mdi:lightning-bolt",
    ),
    *_energy_pair(
        EnergyCat.ELECTRIC_ACS,
        "Electric energy used for DHW",
        "electric_acs",
        icon="mdi:lightning-bolt",
    ),
    *_energy_pair(
        EnergyCat.RUNTIME_HOURS,
        "Runtime",
        "runtime",
        is_runtime=True,
        icon="mdi:timer-play",
    ),
)


# All distinct energy categories — used by the coordinator to size the
# accumulator dictionaries.
ENERGY_CATEGORIES: tuple[str, ...] = tuple(
    sorted({p.category for p in ENERGY_SENSORS}),
)


def default_energy_state() -> dict[str, float]:
    """Return a fresh dict of zero accumulators, one per category."""
    return dict.fromkeys(ENERGY_CATEGORIES, 0.0)
