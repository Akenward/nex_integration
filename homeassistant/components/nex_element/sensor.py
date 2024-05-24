"""Platform for sensor integration."""

from __future__ import annotations

# from .const import DOMAIN
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

# from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
#  from homeassistant.helpers.entity import async_generate_entity_id
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
    idx = "energy_used"
    name = f"Energy meter {entry.data[CONF_NAME]}"
    unique_id = entry.unique_id
    sensor_entity_id = "energy_sensor_" + str(unique_id)
    entry_id = entry.entry_id
    address = entry.data[CONF_ADDRESS]
    meters.append(
        NexConsumption(
            coordinator,
            idx,
            unique_id,
            entry_id,
            sensor_entity_id,
            address,
            name,
        )
    )
    async_add_entities(meters)
    _LOGGER.debug("add entities done")


class NexConsumption(CoordinatorEntity, SensorEntity):
    """Represent a NEX Sensor."""

    def __init__(
        self,
        coordinator: NexBTCoordinator,
        idx,
        unique_id,
        entry_id,
        sensor_entity_id,
        address,
        name,
    ) -> None:
        """Initialise NexConsumption entity."""
        super().__init__(coordinator, context=idx)
        self.idx = idx
        self.coordinator = coordinator
        self._unique_id = unique_id
        self.entry_id = entry_id
        self.sensor_entity_id = sensor_entity_id
        self.address = address
        self._name = name
        self._attr_native_value = self.coordinator.device_data.get("energy_used")
        self.native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_native_value = self.coordinator.data.get("energy_used")

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = self.coordinator.data.get("energy_used")
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (self.entry_id, self.address)
            },
            name=self.name,
            manufacturer="HeatQ",
            model="NEX",
            sw_version="1.0",
        )

    @property
    def name(self) -> str:
        """Nex sensor name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Unique identifier."""
        return self._unique_id

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Device class."""
        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> SensorStateClass | None:
        """State class."""
        return SensorStateClass.TOTAL_INCREASING
