"""Config flow for ChromaFi integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bleak.backends.device import BLEDevice

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ChromaFi."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        
        self._discovered_device = discovery_info
        
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_device.name or "ChromaComfort Fan",
                data={
                    CONF_ADDRESS: self._discovered_device.address,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovered_device.name or "ChromaComfort Fan"
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            if CONF_ADDRESS in user_input:
                await self.async_set_unique_id(user_input[CONF_ADDRESS])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=self._discovered_devices[user_input[CONF_ADDRESS]].name or "ChromaComfort Fan",
                    data=user_input,
                )
        
        # Get devices discovered by Home Assistant's Bluetooth integration
        current_addresses = self._async_current_ids()
        
        self._discovered_devices = {}
        for discovery_info in async_discovered_service_info(self.hass, False):
            if discovery_info.address in current_addresses:
                continue
            if discovery_info.name and ("ChromaComfort" in discovery_info.name or "Chroma-Comfort" in discovery_info.name):
                self._discovered_devices[discovery_info.address] = discovery_info
        
        if not self._discovered_devices:
            return self.async_show_form(
                step_id="user",
                errors={"base": "no_devices_found"},
            )
        
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): vol.In(
                    {
                        addr: f"{device.name} ({addr})"
                        for addr, device in self._discovered_devices.items()
                    }
                ),
            }),
            errors=errors,
        )