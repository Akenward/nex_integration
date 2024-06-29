"""Platform for sensor integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SHORT_ADDRESS, DOMAIN
from .coordinator import NexBTCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    meters = []
    coordinator: NexBTCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = f"Nex element {entry.data[CONF_SHORT_ADDRESS]}"
    entry_id = entry.entry_id
    address = entry.data[CONF_ADDRESS]
    meters.append(
        NexConsumption(
            coordinator,
            entry_id,
            address,
            name,
        )
    )
    async_add_entities(meters)
    _LOGGER.debug("add energy sensors done")


class NexConsumption(CoordinatorEntity, SensorEntity):
    """Track Nex energy consumption ."""

    def __init__(
        self,
        coordinator: NexBTCoordinator,
        entry_id,
        address,
        name,
    ) -> None:
        """Initialise NexConsumption entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry_id = entry_id
        self._attr_name = name + " energy"
        self.sensor_entity_id = (self._attr_name.lower() + "_energy_sensor").replace(
            " ", "_"
        )
        self.address = address
        self._attr_name = name + " energy"
        self.device_name = name
        if self.coordinator.data.get("energy_used") is not None:
            self._attr_native_value = str(
                round(self.coordinator.data.get("energy_used"), 2)
            )
        self.native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_unique_id = self._attr_name.lower().replace(" ", "_")

    def update(self) -> None:
        """Fetch new state data for the sensor."""

        if self.coordinator.data.get("energy_used") is not None:
            self._attr_native_value = str(
                round(self.coordinator.data.get("energy_used"), 2)
            )
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (self.entry_id, self.address)
            },
            name=self.device_name,
            manufacturer="HeatQ",
            model="NEX",
            sw_version="1.0",
        )

    @property
    def name(self) -> str:
        """Nex sensor name."""
        return self._attr_name

    @property
    def unique_id(self) -> str:
        """Unique identifier."""
        return self._attr_unique_id

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Device class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> SensorStateClass | None:
        """State class."""
        return SensorStateClass.TOTAL_INCREASING
