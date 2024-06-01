"""Support for generic water heater units."""

import logging
from typing import Any

# from homeassistant.const import CONF_ADDRESS
from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

CONF_SHORT_ADDRESS = "short_address"

from homeassistant.components.water_heater.const import (
    STATE_ECO,
)

from homeassistant.core import (
    HomeAssistant,
    DOMAIN as HA_DOMAIN,
    callback,
    Event,
    EventStateChangedData,
)

from homeassistant.helpers.device_registry import DeviceInfo

from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

from .coordinator import NexBTCoordinator

NEX_TARGET_TEMPERATURE = WaterHeaterEntityFeature.TARGET_TEMPERATURE
NEX_OPERATION_MODE = WaterHeaterEntityFeature.OPERATION_MODE
NEX_AWAY_MODE = WaterHeaterEntityFeature.AWAY_MODE
NEX_ON_OFF = WaterHeaterEntityFeature.ON_OFF

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS_HEATER = NEX_OPERATION_MODE | NEX_TARGET_TEMPERATURE | NEX_AWAY_MODE


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the heated rail."""
    rails = []
    coordinator: NexBTCoordinator = hass.data[DOMAIN][entry.entry_id]
    name = f"Nex element {entry.data[CONF_SHORT_ADDRESS]}"
    entry_id = entry.entry_id
    address = entry.data[CONF_ADDRESS]
    unit = hass.config.units.temperature_unit

    rails.append(
        NexHeatedRail(
            coordinator,
            name,
            entry_id,
            address,
            unit,
        )
    )

    async_add_entities(rails)
    _LOGGER.debug("add water heater entities done")


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
        self.unique_id = (self._attr_name.lower() + "_heater").replace(" ", "_")
        self.entry_id = entry_id
        self.heater_entity_id = (self._attr_name.lower() + "_heater_element").replace(
            " ", "_"
        )
        self.sensor_entity_id = (
            self._attr_name.lower() + "_heater_temperature"
        ).replace(" ", "_")
        self.address = address
        self._attr_temperature_unit = unit
        self._operation_list = [
            STATE_ON,
            STATE_OFF,
        ]
        self._attr_min_temp: float | None = coordinator.device_data.get(
            "lower_temp_limit"
        )
        self._attr_max_temp: float | None = coordinator.device_data.get(
            "upper_temp_limit"
        )
        self._attr_current_temperature = coordinator.device_data.get(
            "current_element_temp"
        )
        self._attr_target_temperature = coordinator.device_data.get(
            "target_element_temp"
        )
        _current_state_code = coordinator.device_data.get("current_state_code")
        self._attr_current_operation = (
            STATE_OFF if int(_current_state_code) == 0 else STATE_ON
        )
        self._attr_supported_features = SUPPORT_FLAGS_HEATER
        self._attr_available = True
        self._attr_is_away_mode_on = False
        self._attr_operation_mode = STATE_ECO

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

    def _update_heater_status(self) -> None:
        self._attr_min_temp: float | None = self.coordinator.device_data.get(
            "lower_temp_limit"
        )
        self._attr_max_temp: float | None = self.coordinator.device_data.get(
            "upper_temp_limit"
        )
        self._attr_current_temperature = self.coordinator.device_data.get(
            "current_element_temp"
        )
        self._attr_target_temperature = self.coordinator.device_data.get(
            "target_element_temp"
        )
        _current_state_code = self.coordinator.device_data.get("current_state_code")
        self._attr_current_operation = (
            STATE_OFF if int(_current_state_code) == 0 else STATE_ON
        )

    def _handle_coordinator_update(self) -> None:
        """Fetch new state data for the heater."""
        self._update_heater_status()
        self.async_write_ha_state()

    async def async_set_operation_mode(self, operation_mode: str):
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

    async def async_turn_away_mode_on(self) -> None:
        """Turn away mode on."""
        self._attr_is_away_mode_on = True
        self._attr_current_operation = STATE_ON
        self._attr_target_temperature = self._attr_min_temp
        await self.coordinator.device.async_nex_turn_on(self._attr_min_temp)
        self.async_write_ha_state()

    async def async_turn_away_mode_off(self) -> None:
        """Turn away mode off."""
        self._attr_is_away_mode_off = False
        self._attr_current_operation = STATE_OFF
        self._attr_target_temperature = (self._attr_min_temp + self._attr_max_temp) / 2
        await self.coordinator.device.async_nex_turn_off()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if self._attr_current_operation == STATE_ON:
            await self.coordinator.device.async_nex_turn_on(
                self._attr_target_temperature
            )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        temp_sensor = self.hass.states.get(self.sensor_entity_id)
        if temp_sensor and temp_sensor.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            self._attr_current_temperature = float(temp_sensor.state)

        heater_switch = self.hass.states.get(self.heater_entity_id)
        if heater_switch and heater_switch.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            self._attr_available = True
        self.async_write_ha_state()

    async def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # await self._async_heater_turn_off()
            self._attr_current_temperature = None
        else:
            self._attr_current_temperature = float(new_state.state)
        self.async_write_ha_state()

    @callback
    def _async_switch_changed(self, event: Event):
        """Handle heater switch state changes."""
        new_state = event.data.get("new_state")
        _LOGGER.debug("***** New switch state: %s", new_state)
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._attr_available = False
        else:
            self._attr_available = True
            _LOGGER.debug("%s became Available", self._attr_name)
            if new_state.state == STATE_ON and self._current_operation == STATE_OFF:
                self._attr_current_operation = STATE_ON
                _LOGGER.debug("STATE_ON")
            elif new_state.state == STATE_OFF and self._current_operation == STATE_ON:
                self._attr_current_operation = STATE_OFF
                _LOGGER.debug("STATE_OFF")

        self.async_write_ha_state()

    async def _async_heater_turn_on(self):
        _LOGGER.debug("****** Turning on heater %s", self.heater_entity_id)
        """Turn heater toggleable device on."""
        heater = self.hass.states.get(self.heater_entity_id)
        if heater is None or heater.state == STATE_ON:
            return
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_ON, data, context=self._context
        )

    async def _async_heater_turn_off(self):
        _LOGGER.debug("****** Turning off heater %s", self.heater_entity_id)
        """Turn heater toggleable device off."""
        heater = self.hass.states.get(self.heater_entity_id)
        if heater is None or heater.state == STATE_OFF:
            return

        _LOGGER.debug("Turning off heater %s", self.heater_entity_id)
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_OFF, data, context=self._context
        )
