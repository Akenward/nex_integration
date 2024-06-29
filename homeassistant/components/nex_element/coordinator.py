"""Example integration using DataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
        interval: timedelta,
        device_name: str,
    ) -> None:
        """Initialize my coordinator."""

        super().__init__(
            hass=hass,
            logger=logger,
            name=device_name,
            update_interval=interval,
            always_update=True,
        )
        self.ble_device = ble_device
        self.device = device
        self.device_name = device_name
        self._was_unavailable = True

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
            and bool(
                bluetooth.async_ble_device_from_address(
                    self.hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_update_data(self) -> dict:
        """Poll the device."""
        return await self.device.async_update_status()

    @property
    def device_data(self) -> dict:
        """Returns the status data for NEX device."""
        return self.data
