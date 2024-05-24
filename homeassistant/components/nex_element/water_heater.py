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
    # CONF_DOMAIN,
    CONF_ADDRESS,
    CONF_NAME,
    #    CONF_DEVICE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

# from .const import DOMAIN
#  UnitOfTemperature,
#    CONF_TEMPERATURE_UNIT
# from . import (
#    CONF_HEATER,
#    CONF_SENSOR,
#    CONF_TARGET_TEMP,
#    CONF_CURRENT_TEMP,
#    CONF_TEMP_MIN,
#    CONF_TEMP_MAX,
# )
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo

# from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

# from .NEX_bt_api.nexbt import NexBTDevice
from .coordinator import NexBTCoordinator

NEX_TARGET_TEMPERATURE = WaterHeaterEntityFeature.TARGET_TEMPERATURE
NEX_OPERATION_MODE = WaterHeaterEntityFeature.OPERATION_MODE
NEX_AWAY_MODE = WaterHeaterEntityFeature.AWAY_MODE

# try:
# from homeassistant.util.unit_conversion import TemperatureConverter as convert
# except ImportError or ModuleNotFoundError:
#    from homeassistant.util.temperature import convert as convert

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS_HEATER = NEX_TARGET_TEMPERATURE | NEX_OPERATION_MODE | NEX_AWAY_MODE

DEFAULT_NAME = "NEX Heated Rail"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the heated rail."""
    rails = []
    unique_id = entry.unique_id
    coordinator: NexBTCoordinator = hass.data[DOMAIN][entry.entry_id]
    # nex_device = hass.data.setdefault(DOMAIN, {})[entry.entry_id]
    name = f"Water heater {entry.data[CONF_NAME]}"
    sensor_entity_id = "energy_sensor_" + str(unique_id)
    heater_entity_id = "heater_" + str(unique_id)
    entry_id = entry.entry_id
    address = entry.data[CONF_ADDRESS]
    unique_id = async_generate_entity_id("nex_rail.{}", entry.entry_id, None, hass)
    unit = hass.config.units.temperature_unit

    rails.append(
        NexHeatedRail(
            coordinator,
            unique_id,
            entry_id,
            sensor_entity_id,
            heater_entity_id,
            address,
            unit,
            name,
        )
    )

    async_add_entities(rails)


class NexHeatedRail(WaterHeaterEntity, RestoreEntity):
    """Representation of a NEX heated rail."""

    def __init__(
        self,
        coordinator: NexBTCoordinator,
        unique_id,
        entry_id,
        sensor_entity_id,
        heater_entity_id,
        address,
        unit,
        name: str,
    ) -> None:
        """Set up attributes for NexHeatedRail."""
        self.coordinator = coordinator
        self.unique_id = unique_id
        self.entry_id = entry_id
        _LOGGER.debug("Adding entry_id: %s ", self.entry_id)
        self.heater_entity_id = heater_entity_id
        self.sensor_entity_id = sensor_entity_id
        self.address = address
        self._attr_temperature_unit = unit
        self._name = name
        self._min_temperature: float | None = self.coordinator.device_data.get(
            "lower_temp_limit"
        )
        self._max_temperature: float | None = self.coordinator.device_data.get(
            "upper_temp_limit"
        )
        self._current_temperature = self.coordinator.device_data.get(
            "current_element_temp"
        )
        self._target_temperature = self.coordinator.device_data.get(
            "target_element_temp"
        )
        self._current_operating_mode = self.coordinator.device_data.get("current_mode")
        self._current_operating_mode = self.coordinator.device_data.get("current_mode")
        self._current_operation = (
            STATE_OFF if self._current_operating_mode == 0 else STATE_ON
        )
        self._operation_list = [
            STATE_ON,
            STATE_OFF,
        ]
        self._support_flags = SUPPORT_FLAGS_HEATER
        self._attr_available = True
        self._attr_should_poll = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (self.entry_id, self.address)
            },
            name=self._name,
            manufacturer="HeatQ",
            model="NEX",
            sw_version="1.0",
        )

    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        return self._support_flags

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self._current_temperature

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._attr_temperature_unit

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_operation(self) -> str | None:
        """Return current operation ie. on, off."""
        return self._current_operation

    @property
    def operation_list(self) -> list[str] | None:
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return (
            self._min_temperature if isinstance(self._min_temperature, float) else 0.0
        )

    @property
    def max_temp(self) -> float:
        """Return the maximum targetable temperature."""
        return (
            self._max_temperature if isinstance(self._max_temperature, float) else 0.0
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperatures."""
        self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        await self._async_control_heating()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode."""
        self._current_operation = operation_mode
        await self._async_control_heating()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self.sensor_entity_id], self._async_sensor_changed
            )
        )

        old_state = await self.async_get_last_state()
        if old_state is not None:
            if isinstance((old_state.attributes.get(ATTR_TEMPERATURE)), float):
                self._target_temperature = old_state.attributes.get(ATTR_TEMPERATURE)
            self._current_operation = old_state.state

        temp_sensor = self.hass.states.get(self.sensor_entity_id)
        if temp_sensor and temp_sensor.state not in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            self._current_temperature = float(temp_sensor.state)

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
            # Failsafe
            _LOGGER.warning(
                "No Temperature information, entering Failsafe, turning off heater %s",
                self.heater_entity_id,
            )
            await self._async_heater_turn_off()
            self._current_temperature = None
        else:
            self._current_temperature = float(new_state.state)

        await self._async_control_heating()

    @callback
    def _async_switch_changed(self, event):
        """Handle heater switch state changes."""
        new_state = event.data.get("new_state")
        _LOGGER.debug(format(new_state, "New switch state = {%}"))
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._attr_available = False
        else:
            self._attr_available = True
            _LOGGER.debug("%s became Available", self.name)
            if new_state.state == STATE_ON and self._current_operation == STATE_OFF:
                self._current_operation = STATE_ON
                _LOGGER.debug("STATE_ON")
            elif new_state.state == STATE_OFF and self._current_operation == STATE_ON:
                self._current_operation = STATE_OFF
                _LOGGER.debug("STATE_OFF")

        self.async_write_ha_state()

    async def _async_control_heating(self):
        """Check if we need to turn heating on or off."""
        if self._current_operation == STATE_OFF or self._current_temperature is None:
            pass
        elif (
            abs(self._current_temperature - self._target_temperature)
            > self._temperature_delta
        ):
            if self._current_temperature < self._target_temperature:
                await self._async_heater_turn_on()
            else:
                await self._async_heater_turn_off()
        self.async_write_ha_state()

    async def _async_heater_turn_on(self):
        """Turn heater toggleable device on."""
        heater = self.hass.states.get(self.heater_entity_id)
        if heater is None or heater.state == STATE_ON:
            return

        _LOGGER.debug("Turning on heater %s", self.heater_entity_id)
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_ON, data, context=self._context
        )

    async def _async_heater_turn_off(self):
        """Turn heater toggleable device off."""
        heater = self.hass.states.get(self.heater_entity_id)
        if heater is None or heater.state == STATE_OFF:
            return

        _LOGGER.debug("Turning off heater %s", self.heater_entity_id)
        data = {ATTR_ENTITY_ID: self.heater_entity_id}
        await self.hass.services.async_call(
            HA_DOMAIN, SERVICE_TURN_OFF, data, context=self._context
        )
