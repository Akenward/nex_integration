"""Constants for the nex_element integration."""

from datetime import timedelta

DOMAIN = "nex_element"

INT_UPDATE_INTERVAL = 50


DEVICE_STARTUP_TIMEOUT_SECONDS = 25
DEVICE_UPDATE_TIMEOUT = 90
CONF_SHORT_ADDRESS = "short_address"
CONF_DEFAULT_TEMPERATURE = 60

ATTR_OPERATION_MODE = "operation_mode"
UNIT_COST = "unit_cost"

POWER = "power"
INTERVAL_SECS = "interval_secs"
CONNECT_TRIES = "connect_tries"
CONNECT_ATTEMPT_SECS = "connect_attempt_secs"
NOTIFY_TRIES = "notify_tries"
TITLE = "title"

DEFAULT_POWER = 400
DEFAULT_INTERVAL_SECS = 50
DEFAULT_INTERVAL = timedelta(seconds=DEFAULT_INTERVAL_SECS)
DEFAULT_CONNECT_TRIES = 8
DEFAULT_CONNECT_ATTEMPT_SECS = 12
DEFAULT_NOTIFY_TRIES = 4
