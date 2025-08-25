"""Config flow for ChromaFi integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bleak import BleakScanner
from bleak.backends.device import BLEDevice

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ChromaFi."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: BLEDevice | None = None
        self._discovered_devices: dict[str, BLEDevice] = {}

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        
        self._discovered_device = discovery_info.device
        
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
        
        # Scan for devices
        scanner = BleakScanner()
        devices = await scanner.discover()
        
        self._discovered_devices = {}
        for device in devices:
            if device.name and "ChromaComfort" in device.name:
                self._discovered_devices[device.address] = device
        
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