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

# from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
# """Validate the user input allows us to connect.
# Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
# """
# TO**DO validate the data can be used to set up a connection.

# If your PyPI package is not built with async, pass your methods
# to the executor:
# await hass.async_add_executor_job(
#     your_validate_func, data[CONF_USERNAME], data[CONF_PASSWORD]
# )

# hub = PlaceholderHub(data[CONF_HOST])


# If you cannot connect:
# throw CannotConnect
# If the authentication is wrong:
# InvalidAuth

# Return info that you want to store in the config entry.
# return {"title": "Name of the device"}


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
            # await self.async_set_unique_id(
            #    self._discovery_info.address, raise_on_progress=False
            # )
            # self._abort_if_unique_id_configured()
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

        data_schema = vol.Schema(
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
            step_id="select", data_schema=data_schema, errors=errors
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add additional info for selected device."""
        errors: dict[str, str] = {}

        if user_input is not None and self._discovery_info is not None:
            local_name = self._discovery_info.name
            title = user_input["title"]
            power = user_input["power"]
            unit_cost = user_input["unit_cost"]
            return self.async_create_entry(
                title=local_name,
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_NAME: title,
                    CONF_DOMAIN: DOMAIN,
                    "power": power,
                    "unit_cost": unit_cost,
                },
            )

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

        data_schema = vol.Schema(
            {
                vol.Required("title"): str,
                vol.Required("power"): str,
                vol.Required("unit_cost"): str,
            }
        )
        return self.async_show_form(
            step_id="configure", data_schema=data_schema, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
