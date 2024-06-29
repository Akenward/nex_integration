"""Config flow for nex_element integration."""

from __future__ import annotations

import logging
from typing import Any

from bluetooth_data_tools import human_readable_name
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_DOMAIN, CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_SHORT_ADDRESS,
    CONNECT_ATTEMPT_SECS,
    CONNECT_TRIES,
    DEFAULT_CONNECT_ATTEMPT_SECS,
    DEFAULT_CONNECT_TRIES,
    DEFAULT_INTERVAL_SECS,
    DEFAULT_NOTIFY_TRIES,
    DEFAULT_POWER,
    DOMAIN,
    INTERVAL_SECS,
    NOTIFY_TRIES,
    POWER,
    TITLE,
)

_LOGGER = logging.getLogger(__name__)


class NexConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for nex_element."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": human_readable_name(
                None, discovery_info.name, discovery_info.address
            )
        }
        return await self.async_step_select()

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return await self.async_step_configure()

        if discovery := self._discovery_info:
            self._discovered_devices[discovery.address] = discovery
        else:
            current_addresses = self._async_current_ids()
            for discovery in async_discovered_service_info(self.hass):
                if (
                    discovery.address in current_addresses
                    or discovery.address in self._discovered_devices
                ):
                    continue
                self._discovered_devices[discovery.address] = discovery

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        select_schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        service_info.address: (
                            f"{service_info.name} ({service_info.address})"
                        )
                        for service_info in self._discovered_devices.values()
                    }
                ),
            }
        )
        return self.async_show_form(
            step_id="select", data_schema=select_schema, errors=errors
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add additional info for selected device."""
        errors: dict[str, str] = {}

        if user_input is not None and self._discovery_info is not None:
            title = (self._discovery_info.name,)
            data = {
                CONF_ADDRESS: self._discovery_info.address,
                CONF_NAME: str(user_input[TITLE]),
                CONF_DOMAIN: DOMAIN,
                INTERVAL_SECS: int(DEFAULT_INTERVAL_SECS),
                CONNECT_TRIES: int(DEFAULT_CONNECT_TRIES),
                CONNECT_ATTEMPT_SECS: int(DEFAULT_CONNECT_ATTEMPT_SECS),
                NOTIFY_TRIES: int(DEFAULT_NOTIFY_TRIES),
                CONF_SHORT_ADDRESS: self._discovery_info.address.upper()[9:].replace(
                    ":", ""
                ),
                POWER: int(user_input[POWER]),
            }
            return self.async_create_entry(title=title, data=data)

        configure_schema = vol.Schema(
            {vol.Required(TITLE): cv.string, vol.Required(POWER): cv.positive_int}
        )

        return self.async_show_form(
            step_id="configure", data_schema=configure_schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Capture revised operational parameters."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        option_schema = vol.Schema(
            {
                vol.Optional(
                    POWER, default=self.config_entry.options.get(POWER, DEFAULT_POWER)
                ): cv.positive_int,
                vol.Optional(
                    INTERVAL_SECS,
                    default=self.config_entry.options.get(
                        INTERVAL_SECS, DEFAULT_INTERVAL_SECS
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONNECT_TRIES,
                    default=self.config_entry.options.get(
                        CONNECT_TRIES, DEFAULT_CONNECT_TRIES
                    ),
                ): cv.positive_int,
                vol.Optional(
                    CONNECT_ATTEMPT_SECS,
                    default=self.config_entry.options.get(
                        CONNECT_ATTEMPT_SECS, DEFAULT_CONNECT_ATTEMPT_SECS
                    ),
                ): cv.positive_int,
                vol.Optional(
                    NOTIFY_TRIES,
                    default=self.config_entry.options.get(
                        NOTIFY_TRIES, DEFAULT_NOTIFY_TRIES
                    ),
                ): cv.positive_int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=option_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
