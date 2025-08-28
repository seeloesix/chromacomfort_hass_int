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
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import area_registry as ar

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
        
        # Go to confirmation step to let user configure the device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the discovered device."""
        errors = {}
        
        if user_input is not None:
            # Get the device address
            address = self._discovered_device.address
            device_name = user_input.get(CONF_NAME) or (self._discovered_device.name or "ChromaComfort Fan")
            room = user_input.get("room")
            
            # Set unique ID to prevent duplicates
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            
            # Create the config entry with device area if specified
            entry_data = {
                CONF_ADDRESS: address,
                CONF_NAME: device_name,
            }
            
            # Add room if specified and not "none"
            if room and room != "none":
                entry_data["room"] = room
            
            # Create config entry
            return self.async_create_entry(
                title=device_name,
                data=entry_data,
            )
        
        # Get room list from Home Assistant areas
        areas = {}
        try:
            area_registry = ar.async_get(self.hass)
            areas = {area.id: area.name for area in area_registry.areas.values()}
        except Exception:
            _LOGGER.debug("Could not get area registry")
        
        # Add common room names if area registry is empty
        if not areas:
            areas = {
                "living_room": "Living Room",
                "bedroom": "Bedroom",
                "bathroom": "Bathroom",
                "kitchen": "Kitchen",
                "office": "Office",
            }
        
        # Always add "No Room" as default
        areas["none"] = "No Room"
        
        # Get device information for display
        default_name = self._discovered_device.name or "ChromaComfort Fan"
        device_address = self._discovered_device.address
        
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema({
                vol.Optional(CONF_NAME, default=default_name): str,
                vol.Optional("room", default="none"): vol.In(areas),
            }),
            errors=errors,
            description_placeholders={
                "name": default_name,
                "address": device_address,
                "manufacturer": "GooWi Technology",
                "model": "Multi-Color LED Ventilation Fan",
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
                
                # Store selected device and go to configuration step
                selected_device = self._discovered_devices[user_input[CONF_ADDRESS]]
                self._discovered_device = selected_device
                
                return await self.async_step_bluetooth_confirm()
        
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
            
            device_name = discovery_info.name or "Unknown"
            
            # PRIMARY DETECTION: Check manufacturer data (most reliable)
            is_chromacomfort = False
            has_service_uuid = False
            
            # Check for manufacturer ID 10 (0x0A) - GooWi Technology
            if hasattr(discovery_info, 'manufacturer_data') and discovery_info.manufacturer_data:
                for manufacturer_id, data in discovery_info.manufacturer_data.items():
                    if manufacturer_id == 10:  # GooWi Technology manufacturer ID
                        is_chromacomfort = True
                        _LOGGER.info("ChromaComfort Config Flow: Found GooWi device by manufacturer ID 10: '%s' (%s)", 
                                   device_name, discovery_info.address)
                        _LOGGER.debug("  Manufacturer data: %s", data.hex() if data else "None")
                        break
            
            # SECONDARY: Check for the specific service UUID
            if not is_chromacomfort and hasattr(discovery_info, 'service_uuids') and discovery_info.service_uuids:
                for uuid in discovery_info.service_uuids:
                    if "a08f7710-c37c-11e3-99cc-0228ac012a70" in uuid.lower():  # ChromaComfort service UUID
                        is_chromacomfort = True
                        has_service_uuid = True
                        _LOGGER.info("ChromaComfort Config Flow: Found device by service UUID: '%s' (%s)", 
                                   device_name, discovery_info.address)
                        break
            
            # Log device check for debugging
            if is_chromacomfort:
                _LOGGER.info("ChromaComfort Config Flow: ✓ Detected ChromaComfort fan: '%s' (%s)", 
                           device_name, discovery_info.address)
            else:
                _LOGGER.debug("ChromaComfort Config Flow: Skipping non-ChromaComfort device: '%s' (%s)", 
                            device_name, discovery_info.address)
            
            # Accept device if it has the right manufacturer data or service UUID
            if is_chromacomfort:
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