from typing import Final

DOMAIN: Final = "sensorlinx"
SCAN_INTERVAL: Final = 60  # seconds, default polling interval
MANUFACTURER: Final = "HBX Controls"

CONF_SCAN_INTERVAL: Final = "scan_interval"
MIN_SCAN_INTERVAL: Final = 30  # seconds
MAX_SCAN_INTERVAL: Final = 3600  # seconds

CONF_TIMEOUT: Final = "timeout"
DEFAULT_TIMEOUT: Final = 30  # seconds
MIN_TIMEOUT: Final = 10  # seconds
MAX_TIMEOUT: Final = 120  # seconds
