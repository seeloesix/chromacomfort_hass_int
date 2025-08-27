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

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{address}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.address = address
        self.device: BLEDevice | None = None
        self.client: BleakClient | None = None
        self._lock = asyncio.Lock()
        
        # Device state (will be populated during reverse engineering)
        self.data = {
            "fan_speed": 0,
            "light_on": False,
            "brightness": 255,
            "rgb_color": (255, 255, 255),
        }
        
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name="ChromaComfort Fan",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        try:
            async with self._lock:
                if not self.client or not self.client.is_connected:
                    await self._connect()
                
                # TODO: Read actual device state via Bluetooth
                # For now, return current state
                return self.data
                
        except Exception as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    async def _connect(self) -> None:
        """Connect to the device."""
        if self.client:
            await self.disconnect()
        
        # Get device from Home Assistant's Bluetooth integration
        self.device = await async_ble_device_from_address(self.hass, self.address, connectable=True)
        if not self.device:
            raise UpdateFailed(f"Could not find device {self.address}")
        
        # Use retry connector for reliable connection
        self.client = await establish_connection(
            BleakClient,
            self.device,
            name=self.address,
            timeout=30.0,
        )
        
        # Discover services and characteristics
        services = self.client.services
        _LOGGER.debug("Discovered services: %s", services)
        
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
        async with self._lock:
            if not self.client or not self.client.is_connected:
                await self._connect()
            
            # Send fan control command based on discovered protocol
            try:
                if speed == 0:
                    await self.client.write_gatt_char(CHAR_FAN_CONTROL, FAN_CMD_OFF)
                    _LOGGER.debug("Sent fan OFF command")
                else:
                    await self.client.write_gatt_char(CHAR_FAN_CONTROL, FAN_CMD_ON)
                    _LOGGER.debug("Sent fan ON command (speed %s)", speed)
                
                self.data["fan_speed"] = speed
                
            except Exception as err:
                _LOGGER.error("Failed to set fan speed: %s", err)
                raise
        
        await self.async_request_refresh()

    async def set_light_state(self, on: bool) -> None:
        """Turn the light on or off."""
        async with self._lock:
            if not self.client or not self.client.is_connected:
                await self._connect()
            
            # Send light control command based on discovered protocol
            try:
                if on:
                    await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, LIGHT_CMD_ON)
                    _LOGGER.debug("Sent light ON command")
                else:
                    await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, LIGHT_CMD_OFF)
                    _LOGGER.debug("Sent light OFF command")
                
                self.data["light_on"] = on
                
            except Exception as err:
                _LOGGER.error("Failed to set light state: %s", err)
                raise
        
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