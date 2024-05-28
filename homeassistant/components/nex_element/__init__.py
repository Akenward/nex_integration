"""The nex_element integration."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, Event
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import (
    async_track_state_change_event,
)

from .const import DOMAIN
from .coordinator import NexBTCoordinator
from .NEX_bt_api.nexbt import NexBTDevice

CONF_HEATER = "heater_switch"
CONF_SENSOR = "temperature_sensor"
CONF_TARGET_TEMP = "target_temperature"
CONF_TEMP_CURRENT = "current_temperature"
CONF_TEMP_MIN = "min_temp"
CONF_TEMP_MAX = "max_temp"

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
    power = entry.data["power"]
    unit_cost = entry.data["unit_cost"]
    nex_device = NexBTDevice(hass, ble_device, power, unit_cost)

    coordinator = NexBTCoordinator(
        hass,
        _LOGGER,
        ble_device,
        nex_device,
        entry.title,  # , entry.unique_id
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    # heater_entity_id = "water_heater_" + str(entry.unique_id)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
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
