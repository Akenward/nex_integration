"""NEX bt device."""

import asyncio
from contextlib import AsyncExitStack
import datetime
import logging
import re
from uuid import UUID

from bleak import BleakClient

# from bleak.backends.device import BLEDevice
# from bleak.backends.scanner import AdvertisementData
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import (
    CONF_TIMEOUT,
    MSG_ACKNOWLEDGE,
    MSG_NONE,
    MSG_SCHEDULE,
    MSG_STATUS,
    NOTIFY_UUID,
    WRITE_UUID,
    MAX_CONNECTION_RETRIES,
)
from .exceptions import BleakConnectionFailure, BleakTimeout

_LOGGER = logging.getLogger(__name__)


class NexBTDevice:
    """NEX BT Device Class."""

    def __init__(
        self, hass: HomeAssistant, ble_device: BLEDevice, power, unit_cost
    ) -> None:
        """Initialise properties."""
        self._ble_device = ble_device
        self._client: BleakClient | None = None
        self._client_stack = AsyncExitStack()
        self._lock = asyncio.Lock()
        # self._client_stack = AsyncExitStack()
        self._lock = asyncio.Lock()
        self.status_message = MSG_NONE
        self.status_string = [0] * 48
        self.status_size = [1, 48, 144]
        self.message_next = 0
        self.power = power
        self.unit_cost = unit_cost
        self.device_data: dict = {}
        self._address = ble_device.address
        self._hass = hass
        self._response_received = asyncio.Event()
        self._connection_established = asyncio.Event()

    @property
    def connected(self) -> bool:
        """Check for connection."""
        return self._client is not None and self._client.is_connected

    async def _async_get_connection(self) -> bool:
        """Open connection and subscribe to notifications."""
        self._connection_established.clear()
        self._ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address.upper(), True
        )
        async with self._lock:
            if not self.connected:
                attempts = 0
                while not self.connected and attempts < MAX_CONNECTION_RETRIES:
                    try:
                        self._client = await self._client_stack.enter_async_context(
                            BleakClient(
                                self._ble_device,
                                timeout=20,
                            )
                        )
                    except TimeoutError as exc:
                        _LOGGER.debug("Timeout on connect", exc_info=True)
                        raise BleakTimeout("Timeout on connect") from exc
                    except BleakError as exc:
                        _LOGGER.debug("Error on connect", exc_info=True)
                        raise BleakConnectionFailure("Error on connect") from exc
                    finally:
                        attempts += 1
            else:
                _LOGGER.debug("Reusing connection")
        if self.connected:
            self._connection_established.set()
        else:
            _LOGGER.debug("Abandoning connection to device")
        await self._connection_established.wait()
        if self.connected:
            await self._client.start_notify(NOTIFY_UUID, self._catch_nex_response)
            return True
        else:
            return False

    async def async_nex_turn_on(self, temp: float) -> None:
        """Turn NEX device on at given temperature."""
        await self._async_get_connection()
        if self._client is not None:
            await self._async_update_status()
            self._response_received.clear()
            uuid_str = "{" + WRITE_UUID + "}"
            uuid = UUID(uuid_str)
            command_string = "aaaaaaaa05000084" + hex(round(temp)).replace("0x", "")
            command_bytes = bytearray.fromhex(command_string)
            await self._client.write_gatt_char(WRITE_UUID, command_bytes, False)
            try:
                async with asyncio.timeout(20):
                    await self._response_received.wait()
            except TimeoutError:
                _LOGGER.debug("Took too long to collect element data")
        return self.device_data

    async def async_nex_turn_off(self) -> None:
        """Turn NEX device off."""
        await self._async_get_connection()
        if self._client is not None:
            await self._async_update_status()
            self._response_received.clear()
            uuid_str = "{" + WRITE_UUID + "}"
            uuid = UUID(uuid_str)
            command_string = "aaaaaaaa0500008200"
            command_bytes = bytearray.fromhex(command_string)
            await self._client.write_gatt_char(WRITE_UUID, command_bytes, False)
            try:
                async with asyncio.timeout(20):
                    await self._response_received.wait()
            except TimeoutError:
                _LOGGER.debug("Took too long to collect element data")
        return self.device_data

    def _hello_message(self) -> bytearray:
        timeval = datetime.datetime.now()
        timestring_raw = timeval.strftime("%S:%M:%H:%d;0%w:%m:%y")
        timestring_corrected = timestring_raw.replace(";00:", ":07:")
        timestring_compressed = re.sub(":|;", "", timestring_corrected)
        hello_string = "aaaaaaaa0b000083" + timestring_compressed
        return bytearray.fromhex(hello_string)

    async def _async_update_status(self) -> dict:
        """Send hello message to device and return device status data."""
        await self._async_get_connection()
        if self._client is not None:
            hello_message = self._hello_message()
            self._response_received.clear()
            await self._client.write_gatt_char(WRITE_UUID, hello_message, False)
            try:
                async with asyncio.timeout(20):
                    await self._response_received.wait()
            except TimeoutError:
                _LOGGER.debug("Took too long to collect element data")
        return self.device_data

    async def _catch_nex_response(
        self, sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Process notification data received from device."""
        if data[:4] == bytes.fromhex("aaaaaaaa"):
            # this is the start of a message
            match data[4]:
                # look at the 5th character for length of data
                case 2:
                    # simple acknowledgement
                    self.status_message = MSG_ACKNOWLEDGE
                    self.message_next = len(data) - 5
                case 49:
                    # general status data
                    self.status_message = MSG_STATUS
                    self.status_string[0 : len(data) - 5] = data[5:]
                    self.message_next = len(data) - 5
                case 153:
                    # current schedule data
                    self.status_message = MSG_SCHEDULE
                    self.message_next = len(data) - 5
        elif self.status_message == MSG_STATUS:
            # this continues a general status message
            self.status_string[self.message_next : self.message_next + len(data)] = data
            self.message_next += len(data)
        else:
            # this continues an ack or schedule message - don't need to save this data
            self.message_next += len(data)

        if self.message_next >= self.status_size[self.status_message]:
            # message data is complete
            if self.status_message == MSG_STATUS:
                self.status_message = MSG_NONE
                if self._process_update():
                    self._response_received.set()

    def _process_update(self) -> bool:
        op_time = int.from_bytes(self.status_string[35:37], "big")
        self.device_data = {
            "current_state_code": self.status_string[1],
            "current_element_temp": float(self.status_string[4]),
            "target_element_temp": float(self.status_string[5]),
            "lower_temp_limit": float(self.status_string[6]),
            "upper_temp_limit": float(self.status_string[7]),
            "energy_used": float(op_time * int(self.power) / 60000),
        }
        return True

    async def async_update_status(self):
        "Call method to update entity status."
        return await self._async_update_status()

    def poll_needed(self, seconds: int | None = None) -> bool:
        "Determine whether a poll is needed."
        if seconds is None:
            return False
        return seconds >= CONF_TIMEOUT
