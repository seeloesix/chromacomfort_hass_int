"""Data coordinator for ChromaComfort integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, 
    MANUFACTURER, 
    MODEL, 
    UPDATE_INTERVAL,
    CHAR_FAN_CONTROL,
    CHAR_LIGHT_CONTROL,
    CHAR_COLOR_CONTROL,
    CHAR_DEVICE_STATUS,
    FAN_CMD_OFF,
    FAN_CMD_ON,
    LIGHT_CMD_OFF,
    LIGHT_CMD_ON,
    COLOR_CMD_OFF,
)

_LOGGER = logging.getLogger(__name__)


class ChromaComfortCoordinator(DataUpdateCoordinator):
    """Data coordinator for ChromaComfort device."""

    def __init__(self, hass: HomeAssistant, address: str, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{address}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.address = address
        self.entry = entry
        self.device: BLEDevice | None = None
        self.client: BleakClient | None = None
        self._lock = asyncio.Lock()
        
        # Get custom name and room from config entry
        self.custom_name = entry.data.get(CONF_NAME, "ChromaComfort Fan")
        self.room = entry.data.get("room")
        
        # Device state (will be populated during reverse engineering)
        self.data = {
            "fan_speed": 0,
            "light_on": False,
            "brightness": 255,
            "rgb_color": (255, 255, 255),
        }
        
        # Build device info with custom name and area
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=self.custom_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
        
        # Add suggested area if room is specified
        if self.room and self.room != "none":
            self.device_info["suggested_area"] = self.room

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        try:
            async with self._lock:
                if not self.client or not self.client.is_connected:
                    _LOGGER.debug("Attempting to connect to device %s", self.address)
                    await self._connect()
                
                # TODO: Read actual device state via Bluetooth
                # For now, return current state
                _LOGGER.debug("Returning current state for device %s: %s", self.address, self.data)
                return self.data
                
        except Exception as err:
            _LOGGER.error("Error communicating with device %s: %s", self.address, err)
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    async def _connect(self) -> None:
        """Connect to the device."""
        if self.client:
            await self.disconnect()
        
        # Get device from Home Assistant's Bluetooth integration
        # Note: async_ble_device_from_address is NOT async, despite the name
        self.device = async_ble_device_from_address(self.hass, self.address, connectable=True)
        if not self.device:
            _LOGGER.error("Could not find BLE device with address %s", self.address)
            raise UpdateFailed(f"Could not find device {self.address}")
        
        _LOGGER.info("Found BLE device: %s at %s", self.device.name, self.address)
        
        try:
            # Use retry connector for reliable connection
            _LOGGER.debug("Establishing BLE connection to %s", self.address)
            self.client = await establish_connection(
                BleakClient,
                self.device,
                name=self.address,
                timeout=30.0,
            )
            _LOGGER.info("Successfully connected to %s", self.address)
        except Exception as err:
            _LOGGER.error("Failed to establish BLE connection to %s: %s", self.address, err)
            raise UpdateFailed(f"Could not connect to device: {err}") from err
        
        # Discover services and characteristics
        try:
            services = self.client.services
            _LOGGER.debug("Discovered services: %s", services)
            
            # Log all characteristics for debugging
            for service in services:
                _LOGGER.debug("Service %s:", service.uuid)
                for char in service.characteristics:
                    _LOGGER.debug("  Characteristic %s (properties: %s)", char.uuid, char.properties)
        except Exception as err:
            _LOGGER.warning("Could not enumerate services: %s", err)
        
        # Subscribe to status notifications to monitor device state
        try:
            await self.client.start_notify(CHAR_DEVICE_STATUS, self._handle_status_notification)
            _LOGGER.debug("Subscribed to device status notifications")
        except Exception as err:
            _LOGGER.warning("Could not subscribe to status notifications: %s", err)

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def set_fan_speed(self, speed: int) -> None:
        """Set the fan speed."""
        try:
            async with self._lock:
                # Update local state immediately for responsiveness
                old_speed = self.data["fan_speed"]
                self.data["fan_speed"] = speed
                
                # Try to send command to device
                if not self.client or not self.client.is_connected:
                    try:
                        _LOGGER.info("Connecting to send fan command...")
                        await self._connect()
                    except Exception as err:
                        _LOGGER.warning("Could not connect to device for fan control: %s", err)
                        # Keep the local state updated even if BLE fails
                        await self.async_request_refresh()
                        return
                
                # Send fan control command based on discovered protocol
                try:
                    # Check if characteristic exists before writing
                    if not self.client.services:
                        _LOGGER.warning("No services discovered yet for %s", self.address)
                        return
                    
                    if speed == 0:
                        await self.client.write_gatt_char(CHAR_FAN_CONTROL, FAN_CMD_OFF)
                        _LOGGER.info("Sent fan OFF command to %s", self.address)
                    else:
                        await self.client.write_gatt_char(CHAR_FAN_CONTROL, FAN_CMD_ON)
                        _LOGGER.info("Sent fan ON command (speed %s) to %s", speed, self.address)
                    
                except Exception as err:
                    _LOGGER.error("Failed to send fan command to device %s: %s", self.address, err)
                    # Revert state if command failed
                    self.data["fan_speed"] = old_speed
                    raise
        except Exception as err:
            _LOGGER.error("Error in set_fan_speed for %s: %s", self.address, err)
            # Don't raise - let the UI stay responsive
        
        await self.async_request_refresh()

    async def set_light_state(self, on: bool) -> None:
        """Turn the light on or off."""
        try:
            async with self._lock:
                # Update local state immediately for responsiveness
                old_state = self.data["light_on"]
                self.data["light_on"] = on
                
                # Try to send command to device
                if not self.client or not self.client.is_connected:
                    try:
                        _LOGGER.info("Connecting to send light command...")
                        await self._connect()
                    except Exception as err:
                        _LOGGER.warning("Could not connect to device for light control: %s", err)
                        # Keep the local state updated even if BLE fails
                        await self.async_request_refresh()
                        return
                
                # Send light control command based on discovered protocol
                try:
                    # Check if characteristic exists before writing
                    if not self.client.services:
                        _LOGGER.warning("No services discovered yet for %s", self.address)
                        return
                    
                    if on:
                        await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, LIGHT_CMD_ON)
                        _LOGGER.info("Sent light ON command to %s", self.address)
                    else:
                        await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, LIGHT_CMD_OFF)
                        _LOGGER.info("Sent light OFF command to %s", self.address)
                    
                except Exception as err:
                    _LOGGER.error("Failed to send light command to device %s: %s", self.address, err)
                    # Revert state if command failed
                    self.data["light_on"] = old_state
                    raise
        except Exception as err:
            _LOGGER.error("Error in set_light_state for %s: %s", self.address, err)
            # Don't raise - let the UI stay responsive
        
        await self.async_request_refresh()

    async def set_light_brightness(self, brightness: int) -> None:
        """Set the light brightness."""
        async with self._lock:
            if not self.client or not self.client.is_connected:
                await self._connect()
            
            # TODO: Send actual command to device
            self.data["brightness"] = brightness
            _LOGGER.debug("Setting brightness to %s", brightness)
            
            # Placeholder for actual BLE write operation
            # await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, bytes([brightness]))
        
        await self.async_request_refresh()

    async def set_light_color(self, rgb: tuple[int, int, int]) -> None:
        """Set the light RGB color."""
        async with self._lock:
            if not self.client or not self.client.is_connected:
                await self._connect()
            
            # Send color control command based on discovered protocol
            try:
                # Color control uses 6 bytes. Format needs more analysis
                # For now, use basic color off command or attempt RGB mapping
                r, g, b = rgb
                if r == 0 and g == 0 and b == 0:
                    # Turn color off
                    await self.client.write_gatt_char(CHAR_COLOR_CONTROL, COLOR_CMD_OFF)
                    _LOGGER.debug("Sent color OFF command")
                else:
                    # Attempt RGB color command (format to be refined)
                    color_cmd = bytes([0x80, 0x25, r//10, g//10, b//10, 0x00])  # Rough approximation
                    await self.client.write_gatt_char(CHAR_COLOR_CONTROL, color_cmd)
                    _LOGGER.debug("Sent color command: %s", color_cmd.hex())
                
                self.data["rgb_color"] = rgb
                
            except Exception as err:
                _LOGGER.error("Failed to set light color: %s", err)
                raise
        
        await self.async_request_refresh()

    def _handle_status_notification(self, sender, data: bytes) -> None:
        """Handle status notifications from the device."""
        try:
            if len(data) >= 6:  # Ensure we have enough bytes
                # Decode status based on captured pattern analysis
                # Byte 5 (0-indexed): Always 0x41 (base state)
                # Byte 6 (0-indexed): Control state flags
                status_byte = data[5] if len(data) > 5 else 0x00
                
                # Interpret status flags
                fan_on = (status_byte & 0x80) != 0
                light_on = (status_byte & 0x60) != 0  # 0x20, 0x40, 0xA0, 0xC0 indicate light states
                
                # Update local state
                old_fan_speed = self.data["fan_speed"] 
                old_light_on = self.data["light_on"]
                
                self.data["fan_speed"] = 1 if fan_on else 0
                self.data["light_on"] = light_on
                
                _LOGGER.debug(
                    "Status notification: bytes=%s, fan=%s, light=%s", 
                    data.hex(), 
                    fan_on, 
                    light_on
                )
                
                # Trigger update if state changed
                if old_fan_speed != self.data["fan_speed"] or old_light_on != self.data["light_on"]:
                    self.async_set_updated_data(self.data)
            
        except Exception as err:
            _LOGGER.error("Error processing status notification: %s", err)