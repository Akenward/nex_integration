"""NEX bt device."""

import asyncio
from contextlib import AsyncExitStack
import datetime
import logging
import re

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakDBusError, BleakError

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from ..nex_exceptions import CancelledError
from .const import (
    COMMON_MSG_BASE,
    CURRENT_ELEMENT_TEMP,
    CURRENT_STATE_CODE,
    DO_NOTHING_MSG_BASE,
    ENERGY_USED,
    HELLO_MSG_BASE,
    LOWER_TEMP_LIMIT,
    MSG_ACKNOWLEDGE,
    MSG_LEN,
    MSG_NONE,
    MSG_SCHEDULE,
    MSG_STATUS,
    NOTIFY_UUID,
    TARGET_ELEMENT_TEMP,
    TURN_OFF_MSG_BASE,
    TURN_ON_MSG_BASE,
    UPPER_TEMP_LIMIT,
    WRITE_UUID,
)

_LOGGER = logging.getLogger(__name__)


class NexBTDevice:
    """NEX BT Device Class."""

    def __init__(
        self,
        hass: HomeAssistant,
        ble_device: BLEDevice,
        power: int,
        params: dict[str:int],
    ) -> None:
        """Initialise properties."""
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._client_stack = AsyncExitStack()
        self._lock = asyncio.Lock
        self._lock = asyncio.Lock()
        self.status_message = MSG_NONE
        self.status_string = [0] * 48
        self.status_size = [
            MSG_LEN.ACKNOWLEDGE - 1,
            MSG_LEN.STATUS - 1,
            MSG_LEN.SCHEDULE - 1,
            MSG_LEN.NONE - 1,
        ]
        self.message_next = 0
        self.power: int = power
        self.device_data: dict = {}
        self._address = ble_device.address
        self._hass = hass
        self._response_received = asyncio.Event()
        self._connection_established = asyncio.Event()
        self._connect_timeout: int = params.get("connect_timeout")
        self._connect_tries: int = params.get("connect_tries")
        self._notify_tries: int = params.get("notify_tries")
        self.last_data = []

    @property
    def connected(self) -> bool:
        """Check for connection."""
        return self._client is not None and self._client.is_connected

    async def _async_get_connection(self) -> bool:
        """Open connection and subscribe to notifications."""
        self._ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address.upper(), True
        )
        self._connection_established.clear()
        if not self.connected:
            for i in range(self._connect_tries):
                async with self._lock:
                    try:
                        #
                        self._client = await self._client_stack.enter_async_context(
                            BleakClient(
                                self._ble_device,
                                timeout=self._connect_timeout,
                            )
                        )

                    except TimeoutError as exc:
                        _LOGGER.debug(
                            "Timeout on connect %s, attempt %d", str(exc), i + 1
                        )
                        continue
                    except BleakError as exc:
                        _LOGGER.debug(
                            "Error on connect %s, attempt %d", str(exc), i + 1
                        )
                        continue
                    except CancelledError as exc:
                        _LOGGER.debug(
                            "Error on connect %s, attempt %d", str(exc), i + 1
                        )
                    else:
                        _LOGGER.debug("Connected after %d attempts", i + 1)
                        if self.connected:
                            self._connection_established.set()
                        break
        else:
            _LOGGER.debug("Connection reused")
            self._connection_established.set()
        if not self.connected:
            _LOGGER.debug("Abandoning connection to device")
            return False
        await self._connection_established.wait()
        for i in range(self._notify_tries):
            try:
                await self._client.start_notify(NOTIFY_UUID, self._catch_nex_response)
            except BleakDBusError as exc:
                _LOGGER.debug(
                    "Error setting up notify %s, notify attempt %d", str(exc), i
                )
                await asyncio.sleep(1)
                continue
            except BleakError as exc:
                _LOGGER.debug("Connection error %s, notify attempt %d", str(exc), i)
                await asyncio.sleep(1)
                continue
            else:
                return True
        return False

    async def async_update_status(self) -> dict:
        """Send hello message to device and wait for device status data."""
        success = await self._async_get_connection()
        if success:
            hello_message = self._hello_message()
            self._response_received.clear()
            await self._client.write_gatt_char(WRITE_UUID, hello_message, False)
            try:
                async with asyncio.timeout(2):
                    await self._response_received.wait()
            except TimeoutError:
                _LOGGER.debug("Took too long to collect element data")
        return self.device_data

    async def async_nex_turn_on(self, temp: float) -> None:
        """Turn NEX device on at given temperature."""
        await self.async_update_status()
        command_string = TURN_ON_MSG_BASE + hex(round(temp)).replace("0x", "")
        command_bytes = bytearray.fromhex(command_string)
        await self._client.write_gatt_char(WRITE_UUID, command_bytes, False)

    async def async_nex_turn_off(self) -> None:
        """Turn NEX device off."""
        await self.async_update_status()
        command_string = TURN_OFF_MSG_BASE
        command_bytes = bytearray.fromhex(command_string)
        await self._client.write_gatt_char(WRITE_UUID, command_bytes, False)

    async def async_nex_do_nothing(self) -> None:
        """Send NEX device a no action message."""
        await self._async_update_status()
        command_string = DO_NOTHING_MSG_BASE
        command_bytes = bytearray.fromhex(command_string)
        await self._client.write_gatt_char(WRITE_UUID, command_bytes, False)

    def _hello_message(self) -> bytearray:
        timeval = datetime.datetime.now()
        timestring_raw = timeval.strftime("%S:%M:%H:%d;0%w:%m:%y")
        # Correct for coding of Sunday.  ISO uses 0, NEX uses 7
        timestring_corrected = timestring_raw.replace(";00:", ":07:")
        # Remove separators from time/date string
        timestring_compressed = re.sub(":|;", "", timestring_corrected)
        hello_string = HELLO_MSG_BASE + timestring_compressed
        return bytearray.fromhex(hello_string)

    async def _catch_nex_response(
        self, sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Handle notification data received from device."""
        if data[:4] == bytes.fromhex(COMMON_MSG_BASE):
            # this is the start of a message
            match data[4]:
                # look at the 5th character for length of data
                case MSG_LEN.ACKNOWLEDGE:
                    # simple acknowledgement
                    self.status_message = MSG_ACKNOWLEDGE
                    self.message_next = len(data) - 5
                case MSG_LEN.STATUS:
                    # general status data, to be reassembled from three parts
                    self.status_message = MSG_STATUS
                    self.status_string[0 : len(data) - 5] = data[5:]
                    self.last_data = data
                    self.message_next = len(data) - 5
                case MSG_LEN.SCHEDULE:
                    # current schedule data, not needed
                    self.status_message = MSG_SCHEDULE
                    self.message_next = len(data) - 5
        elif self.status_message == MSG_STATUS:
            # this continues a general status message
            if data != self.last_data:
                self.status_string[
                    self.message_next : self.message_next + len(data)
                ] = data
                self.message_next += len(data)
                self.last_data = data
        else:
            # this continues an acknowledgement or schedule message - don't need to save this data
            self.message_next += len(data)
        if self.message_next >= self.status_size[self.status_message]:
            # status message is complete
            if self.status_message == MSG_STATUS:
                self.status_message = MSG_NONE
                if self._process_update():
                    self._response_received.set()

    def _process_update(self) -> bool:
        op_time = int.from_bytes(self.status_string[35:37], "big")
        self.device_data = {
            CURRENT_STATE_CODE: self.status_string[1],
            CURRENT_ELEMENT_TEMP: float(self.status_string[4]),
            TARGET_ELEMENT_TEMP: float(self.status_string[5]),
            LOWER_TEMP_LIMIT: float(self.status_string[6]),
            UPPER_TEMP_LIMIT: float(self.status_string[7]),
            ENERGY_USED: float(op_time) * float(self.power) / 60000,
        }
        return True
