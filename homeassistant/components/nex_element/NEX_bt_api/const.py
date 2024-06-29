"""UUIDs for communication with NEX device."""

import types

WRITE_UUID = "d973f2e2-b19e-11e2-9e96-0800200c9a66"
NOTIFY_UUID = "d973f2e1-b19e-11e2-9e96-0800200c9a66"

""" NEX message types """
MSG_ACKNOWLEDGE = 0
MSG_STATUS = 1
MSG_SCHEDULE = 2
MSG_NONE = 3

CONNECT_TIMEOUT = 12
MAX_CONNECT_TRIES = 8
MAX_NOTIFY_TRIES = 5
DEVICE_CONNECT_TIMEOUT = 50

TURN_ON_MSG_BASE = "aaaaaaaa05000084"
TURN_OFF_MSG_BASE = "aaaaaaaa0500008200"
DO_NOTHING_MSG_BASE = "aaaaaaaa0400000d"
HELLO_MSG_BASE = "aaaaaaaa0b000083"
COMMON_MSG_BASE = "aaaaaaaa"

CURRENT_STATE_CODE = "current_state_code"
CURRENT_ELEMENT_TEMP = "current_element_temp"
TARGET_ELEMENT_TEMP = "target_element_temp"
LOWER_TEMP_LIMIT = "lower_temp_limit"
UPPER_TEMP_LIMIT = "upper_temp_limit"
ENERGY_USED = "energy_used"

MSG_LEN = types.SimpleNamespace()
MSG_LEN.ACKNOWLEDGE = 2
MSG_LEN.STATUS = 49
MSG_LEN.SCHEDULE = 149
MSG_LEN.NONE = 1
