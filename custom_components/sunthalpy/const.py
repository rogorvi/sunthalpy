"""Constants for sunthalpy."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "sunthalpy"
ATTRIBUTION = "Data provided by http://jsonplaceholder.typicode.com/"

BASE_URL: str = "https://cliente.sunthalpy.com:12345/api/client"
UUIDS: dict = {
    "user_sets": "0e115d1a-9786-403b-831d-10ec07b7d906",
    "main_data": "be539f06-ed9c-4a84-96c2-0cf2b002ac31",
    "other_data": "5f1b91c4-2311-49eb-804c-7d73e6e7fbcc",
}
HEADERS: dict = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
TIMEOUT: int = 30
