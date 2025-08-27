"""Config flow for ChromaComfort integration."""
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
    """Handle a config flow for ChromaComfort."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.info("ChromaComfort Config Flow: Bluetooth discovery triggered for device '%s' (%s)", 
                    discovery_info.name, discovery_info.address)
        
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
        _LOGGER.info("ChromaComfort Config Flow: Current configured addresses: %s", current_addresses)
        
        # Get all discovered devices for debugging
        all_discovered = list(async_discovered_service_info(self.hass, False))
        _LOGGER.info("ChromaComfort Config Flow: Total discovered Bluetooth devices: %d", len(all_discovered))
        
        # Log all device names for debugging
        for i, discovery_info in enumerate(all_discovered):
            _LOGGER.info("ChromaComfort Config Flow: Device %d: Name='%s', Address='%s', RSSI=%s", 
                        i + 1, discovery_info.name, discovery_info.address, 
                        getattr(discovery_info, 'rssi', 'N/A'))
        
        self._discovered_devices = {}
        matching_count = 0
        
        for discovery_info in all_discovered:
            # Skip already configured devices
            if discovery_info.address in current_addresses:
                _LOGGER.debug("ChromaComfort Config Flow: Skipping already configured device %s", discovery_info.address)
                continue
            
            # Check device name matching with more variations
            device_name = discovery_info.name or ""
            device_name_lower = device_name.lower()
            
            # Check various name patterns (case insensitive)
            chroma_comfort_match = "chromacomfort" in device_name_lower
            chroma_comfort_hyphen_match = "chroma-comfort" in device_name_lower  
            chroma_match = "chroma" in device_name_lower and "comfort" in device_name_lower
            
            _LOGGER.info("ChromaComfort Config Flow: Checking device '%s' (%s):", device_name, discovery_info.address)
            _LOGGER.info("  - ChromaComfort match: %s", chroma_comfort_match)
            _LOGGER.info("  - Chroma-Comfort match: %s", chroma_comfort_hyphen_match) 
            _LOGGER.info("  - Contains Chroma+Comfort: %s", chroma_match)
            
            if device_name and (chroma_comfort_match or chroma_comfort_hyphen_match or chroma_match):
                self._discovered_devices[discovery_info.address] = discovery_info
                matching_count += 1
                _LOGGER.info("ChromaComfort Config Flow: Found matching ChromaComfort device: '%s' (%s)", 
                           device_name, discovery_info.address)
        
        _LOGGER.info("ChromaComfort Config Flow: Found %d matching ChromaComfort devices out of %d total", 
                    matching_count, len(all_discovered))
        
        if not self._discovered_devices:
            _LOGGER.warning("ChromaComfort Config Flow: No ChromaComfort fans found. Total devices scanned: %d", 
                          len(all_discovered))
            return self.async_show_form(
                step_id="user",
                errors={"base": "no_devices_found"},
            )
        
        _LOGGER.info("ChromaComfort Config Flow: Presenting %d devices for selection", len(self._discovered_devices))
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