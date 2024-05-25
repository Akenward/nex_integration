"""Example integration using DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
import logging

from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEVICE_STARTUP_TIMEOUT_SECONDS
from .NEX_bt_api.nexbt import NexBTDevice

_LOGGER = logging.getLogger(__name__)


class NexBTCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
        device: NexBTDevice,
        device_name: str,
        # connectable: bool,
    ) -> None:
        """Initialize my coordinator."""

        super().__init__(
            hass=hass,
            logger=logger,
            name=device_name,
            # address=ble_device.address,
            # needs_poll_method=self._needs_poll,
            # update_method=self._async_nex_update_data,
            # mode = bluetooth.BluetoothScanningMode.ACTIVE,
            # connectable=connectable,
            update_interval=timedelta(seconds=60),
            always_update=True,
        )
        self.ble_device = ble_device
        self.device = device
        # self.device_name = device_name
        self._ready_event = asyncio.Event()
        self._was_unavailable = True  #
        # self.data = {}

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        # Only poll if hass is running, we need to poll,
        # and we actually have a way to connect to the device
        # return False
        return (
            self.hass.state == CoreState.running
            and self.device.poll_needed(seconds_since_last_poll)
            # and bool(
            #    bluetooth.async_ble_device_from_address(
            #        self.hass, service_info.device.address, connectable=True
            #    )
            # )
        )

    async def _async_update_data(self) -> dict:
        """Poll the device."""
        async with asyncio.timeout(25):
            return await self.device.async_update_status()

    async def async_wait_ready(self) -> bool:
        """Wait for the device to be ready."""
        with contextlib.suppress(asyncio.TimeoutError):
            async with asyncio.timeout(DEVICE_STARTUP_TIMEOUT_SECONDS):
                await self._ready_event.wait()
                return True
        return False

    @property
    def device_data(self) -> dict:
        """Returns the status data for NEX device."""
        return self.data
