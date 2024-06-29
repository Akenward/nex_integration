"""Support for NEX thermostatic heating elements."""

import logging
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_OPERATION_MODE, CONF_SHORT_ADDRESS, DOMAIN
from .coordinator import NexBTCoordinator
from .NEX_bt_api.const import (
    CURRENT_ELEMENT_TEMP,
    LOWER_TEMP_LIMIT,
    TARGET_ELEMENT_TEMP,
    UPPER_TEMP_LIMIT,
)

NEX_TARGET_TEMPERATURE = WaterHeaterEntityFeature.TARGET_TEMPERATURE
NEX_OPERATION_MODE = WaterHeaterEntityFeature.OPERATION_MODE

SUPPORT_FLAGS_HEATER = NEX_OPERATION_MODE | NEX_TARGET_TEMPERATURE


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the heated rail."""
    coordinator: NexBTCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = f"Nex element {entry.data[CONF_SHORT_ADDRESS]}"
    entry_id = entry.entry_id
    address = entry.data[CONF_ADDRESS]
    unit = hass.config.units.temperature_unit

    component = NexHeatedRail(
        coordinator,
        name,
        entry_id,
        address,
        unit,
    )

    async_add_entities([component])

    water_heater_services = hass.services.async_services_for_domain("water_heater")
    if "set_away_mode" in water_heater_services.values():
        hass.services.async_remove("water_heater", "set_away_mode")
    _LOGGER.debug("water heater entity added")


class NexHeatedRail(CoordinatorEntity, WaterHeaterEntity, RestoreEntity):
    """Representation of a NEX heated rail."""

    def __init__(
        self,
        coordinator: NexBTCoordinator,
        name,
        entry_id,
        address,
        unit,
    ) -> None:
        """Set up water heater object."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_name = name + " heater"
        self.device_name = name
        self.unique_id = (self._attr_name.lower()).replace(" ", "_")
        self.entry_id = entry_id
        self.heater_entity_id = (self._attr_name.lower() + "_element").replace(" ", "_")
        self.sensor_entity_id = (self._attr_name.lower() + "_temperature").replace(
            " ", "_"
        )
        self.address = address
        self._attr_temperature_unit = unit
        self._operation_list = [
            STATE_ON,
            STATE_OFF,
        ]
        self._attr_min_temp: float | None = coordinator.device_data.get(
            LOWER_TEMP_LIMIT
        )
        self._attr_max_temp: float | None = coordinator.device_data.get(
            UPPER_TEMP_LIMIT
        )
        self._attr_current_temperature: float | None = coordinator.device_data.get(
            CURRENT_ELEMENT_TEMP
        )
        self._attr_target_temperature: float | None = coordinator.device_data.get(
            TARGET_ELEMENT_TEMP
        )
        _current_state_code = coordinator.device_data.get("current_state_code")
        self._attr_current_operation = (
            STATE_OFF if int(_current_state_code) == 0 else STATE_ON
        )
        self._attr_supported_features = SUPPORT_FLAGS_HEATER
        self._attr_available = True

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

    @callback
    async def _async_on_change(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"].state
        if new_state in [STATE_ON, STATE_OFF]:
            await self.async_set_operation_mode(new_state)

    def _update_heater_status(self) -> None:
        if self.coordinator.device_data.get(LOWER_TEMP_LIMIT) is not None:
            self._attr_min_temp = float(
                self.coordinator.device_data.get(LOWER_TEMP_LIMIT)
            )
        if self.coordinator.device_data.get(UPPER_TEMP_LIMIT) is not None:
            self._attr_max_temp = float(
                self.coordinator.device_data.get(UPPER_TEMP_LIMIT)
            )
        if self.coordinator.device_data.get(CURRENT_ELEMENT_TEMP) is not None:
            self._attr_current_temperature = float(
                self.coordinator.device_data.get(CURRENT_ELEMENT_TEMP)
            )
        if self.coordinator.device_data.get(TARGET_ELEMENT_TEMP) is not None:
            self._attr_target_temperature = float(
                self.coordinator.device_data.get(TARGET_ELEMENT_TEMP)
            )
        if self.coordinator.device_data.get("current_state_code") is not None:
            _current_state_code = self.coordinator.device_data.get("current_state_code")
            self._attr_current_operation = (
                STATE_OFF if int(_current_state_code) == 0 else STATE_ON
            )
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Fetch new state data for the heater."""
        self._update_heater_status()

    @callback
    async def _async_on_change(self, event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"].state
        if new_state in [STATE_ON, STATE_OFF]:
            await self.async_set_operation_mode(new_state)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set on/off state for heating element."""
        if operation_mode == STATE_OFF:
            self._attr_current_operation = STATE_OFF
            await self.coordinator.device.async_nex_turn_off()
        elif operation_mode == STATE_ON:
            self._attr_current_operation = STATE_ON
            await self.coordinator.device.async_nex_turn_on(
                self._attr_target_temperature
            )
        else:
            self._attr_current_operation = STATE_UNKNOWN
        self.async_write_ha_state()

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        return self._attr_supported_features

    @property
    def operation_list(self) -> list[str] | None:
        """Return the list of available operation modes."""
        return self._operation_list

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature for element."""
        _LOGGER.debug("Parameter keys: %s", kwargs.keys())
        if kwargs.get(ATTR_OPERATION_MODE) is not None:
            await self.async_set_operation_mode(kwargs.get(ATTR_OPERATION_MODE))
        self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if self._attr_target_temperature < self._attr_min_temp:
            self._attr_target_temperature = self._attr_min_temp
        if self._attr_target_temperature > self._attr_max_temp:
            self._attr_target_temperature = self._attr_max_temp

        if self._attr_current_operation == STATE_ON:
            await self.coordinator.device.async_nex_turn_on(
                self._attr_target_temperature
            )
        self.async_write_ha_state()

    def turn_on(self):
        """Turn heater entity on."""
        unsub = async_track_state_change_event(
            self.hass, "water_heater." + self.unique_id, self._async_on_change
        )
        heater_state = self.hass.states.get("water_heater." + self.unique_id).state
        if heater_state == STATE_OFF:
            self.hass.states.set("water_heater." + self.unique_id, STATE_ON)
        unsub()

    def turn_off(self):
        "Turn heater entity off."
        unsub = async_track_state_change_event(
            self.hass, "water_heater." + self.unique_id, self._async_on_change
        )
        heater_state = self.hass.states.get("water_heater." + self.unique_id).state
        if heater_state == STATE_ON:
            self.hass.states.set("water_heater." + self.unique_id, STATE_OFF)
        unsub()
