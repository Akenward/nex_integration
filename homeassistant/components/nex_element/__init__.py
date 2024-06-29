"""The nex_element integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONNECT_ATTEMPT_SECS,
    CONNECT_TRIES,
    DOMAIN,
    INTERVAL_SECS,
    NOTIFY_TRIES,
    POWER,
)
from .coordinator import NexBTCoordinator
from .NEX_bt_api.nexbt import NexBTDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WATER_HEATER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up nex_element from a config entry."""

    assert entry.unique_id is not None
    hass.data.setdefault(DOMAIN, {})
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Generic BT Device with address {address}"
        )
    new_data: dict[str:Any] = {**entry.data, **entry.options}
    power = new_data.get(POWER)
    params = {
        "connect_tries": new_data.get(CONNECT_TRIES),
        "connect_timeout": new_data.get(CONNECT_ATTEMPT_SECS),
        "notify_tries": new_data.get(NOTIFY_TRIES),
    }
    interval = timedelta(seconds=new_data.get(INTERVAL_SECS))

    if entry.entry_id in hass.data[DOMAIN]:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        coordinator.interval = interval
        if hasattr(coordinator, "device"):
            coordinator.device.power = power
            coordinator.params = params
    else:
        nex_device = NexBTDevice(hass, ble_device, power, params)
        title = entry.data[CONF_NAME]
        coordinator = NexBTCoordinator(
            hass,
            _LOGGER,
            ble_device,
            nex_device,
            interval,
            title,  # local name e.g. Bathroom Towel Heater
        )
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator
        entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a listener for entry changes."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
