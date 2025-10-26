"""Class containing Sunthalpy data structures and methods."""

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import UnitOfPower, UnitOfPressure, UnitOfTemperature

BASE_URL: str = "https://cliente.sunthalpy.com:12345/api/client"
UUIDS: dict = {
    "user_sets": "0e115d1a-9786-403b-831d-10ec07b7d906",
    "main_data": "be539f06-ed9c-4a84-96c2-0cf2b002ac31",
    "other_data": "5f1b91c4-2311-49eb-804c-7d73e6e7fbcc",
}
HEADERS: dict = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
TIMEOUT: int = 30


@dataclass
class SunthalDataPoint:
    """
    Represents a data point for the Sunthalpy home automation system.

    A data point holds information about a specific sensor or control value,
    including its identifier, name, address, unit of measurement, and values.

    Type Parameters:
        T: The type of the value, restricted to float, bool, int, or str

    Attributes:
        uuid_name (str): The UUID category name this data point belongs to
        name (str): Human-readable name of the data point
        address (str): Address identifier in the Sunthal system
        unit (str, optional): Unit of measurement. Defaults to empty string
        default_value (T, optional): Default value for this data point. Defaults to None
        current_value (T, optional): Current value of this data point. Defaults to None

    """

    uuid_name: str
    name: str
    address: str
    unit: str | None = None
    default_value = None
    current_value = None
    start_enabled: bool = True


@dataclass
class BinarySunthalDataPoint(SunthalDataPoint):
    """Represents a binary input data point for the Sunthalpy home automation system."""

    device_class: BinarySensorDeviceClass | None = None


@dataclass
class NumberSunthalDataPoint(SunthalDataPoint):
    """Represents a number input point for the Sunthalpy home automation system."""

    device_class: NumberDeviceClass | None = None
    min_value: float = 0.0
    max_value: float = 100.0
    step: float = 1.0
    mode: NumberMode = NumberMode.AUTO


@dataclass
class SwitchSunthalDataPoint(SunthalDataPoint):
    """Represents a binary data point for the Sunthalpy home automation system."""

    device_class: SwitchDeviceClass | None = None


@dataclass
class SensorSunthalDataPoint(SunthalDataPoint):
    """Represents a binary data point for the Sunthalpy home automation system."""

    device_class: SensorDeviceClass | None = None


switches = (
    SwitchSunthalDataPoint(
        device_class=SwitchDeviceClass.SWITCH,
        uuid_name="user_sets",
        name="Modo Invierno",
        address="0100",
    ),
    SwitchSunthalDataPoint(
        device_class=SwitchDeviceClass.SWITCH,
        uuid_name="user_sets",
        name="En casa",
        address="0000",
    ),
)

numbers = (
    NumberSunthalDataPoint(
        device_class=NumberDeviceClass.TEMPERATURE,
        uuid_name="user_sets",
        name="Temp. min",
        address="1100",
        unit=UnitOfTemperature.CELSIUS,
        min_value=17.9,
        max_value=27.9,
        step=0.1,
        mode=NumberMode.BOX,
    ),
    NumberSunthalDataPoint(
        device_class=NumberDeviceClass.TEMPERATURE,
        uuid_name="user_sets",
        name="Temp. max",
        address="1101",
        unit=UnitOfTemperature.CELSIUS,
        min_value=18.0,
        max_value=28.0,
        step=0.1,
        mode=NumberMode.BOX,
    ),
)

binary_sensors = (
    BinarySunthalDataPoint(
        uuid_name="user_sets",
        name="ngrok on",
        address="1800",
        start_enabled=False,
    ),
    BinarySunthalDataPoint(
        uuid_name="other_data",
        name="Modo Verano online",
        address="201",
        start_enabled=False,
    ),
    BinarySunthalDataPoint(
        uuid_name="other_data",
        name="Modo Invierno online",
        address="202",
        start_enabled=False,
    ),
    BinarySunthalDataPoint(
        device_class=BinarySensorDeviceClass.PROBLEM,
        uuid_name="other_data",
        name="Alarma",
        address="32",
        start_enabled=False,
    ),
)

sensors = (
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="user_sets",
        name="Temp. min online",
        address="1100",
        unit=UnitOfTemperature.CELSIUS,
        start_enabled=False,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="user_sets",
        name="Temp. max online",
        address="1101",
        unit=UnitOfTemperature.CELSIUS,
        start_enabled=False,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="main_data",
        name="Temp. interior",
        address="103",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.HUMIDITY,
        uuid_name="main_data",
        name="Humedad Interior",
        address="102",
        unit="%",
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="other_data",
        name="Temp. impulsion interior",
        address="1",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="other_data",
        name="Temp. retorno interior",
        address="2",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="other_data",
        name="Temp. impulsion exterior",
        address="4",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="other_data",
        name="Temp. retorno exterior",
        address="5",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.PRESSURE,
        uuid_name="other_data",
        name="Presión circuito",
        address="6",
        unit=UnitOfPressure.BAR,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="other_data",
        name="Temp. ACS",
        address="11",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="other_data",
        name="Temp. Exterior",
        address="20",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.POWER,
        uuid_name="other_data",
        name="Potencia instantánea calefacción",
        address="133",
        unit=UnitOfPower.KILO_WATT,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.POWER,
        uuid_name="other_data",
        name="Potencia instantánea refrigeración",
        address="134",
        unit=UnitOfPower.KILO_WATT,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.POWER,
        uuid_name="other_data",
        name="Consumo eléctrico",
        address="135",
        unit=UnitOfPower.KILO_WATT,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.POWER_FACTOR,
        uuid_name="other_data",
        name="COP",
        address="136",
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.POWER_FACTOR,
        uuid_name="other_data",
        name="EER",
        address="137",
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="other_data",
        name="Consigna temp. ACS",
        address="168",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="other_data",
        name="Consigna temp. calefacción",
        address="170",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        device_class=SensorDeviceClass.TEMPERATURE,
        uuid_name="other_data",
        name="Consigna temp. refrigeración",
        address="175",
        unit=UnitOfTemperature.CELSIUS,
    ),
    SensorSunthalDataPoint(
        uuid_name="other_data",
        name="RPM Compresor",
        address="5002",
        unit="RPM",
        start_enabled=False,
    ),
    SensorSunthalDataPoint(
        uuid_name="other_data",
        name="Bus Demanda ACS",
        address="5181",
        start_enabled=False,
    ),
    SensorSunthalDataPoint(
        uuid_name="other_data",
        name="Bus Demanda DG1",
        address="5183",
        start_enabled=False,
    ),
    SensorSunthalDataPoint(
        uuid_name="other_data",
        name="Bus Programa",
        address="5188",
        start_enabled=False,
    ),
    SensorSunthalDataPoint(
        uuid_name="other_data",
        name="Bus Enciende Bomba Calor",
        address="5257",
        start_enabled=False,
    ),
)
