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
    FAN_CMD_OFF_ALT,
    FAN_CMD_ON_ALT,
    LIGHT_CMD_OFF,
    LIGHT_CMD_ON,
    LIGHT_CMD_OFF_ALT,
    LIGHT_CMD_ON_ALT,
    COLOR_CMD_OFF,
)

_LOGGER = logging.getLogger(__name__)


class ChromaComfortCoordinator(DataUpdateCoordinator):
    """Data coordinator for ChromaComfort device - On-demand connection model."""

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
        self._disconnect_task = None  # Task to auto-disconnect after inactivity
        self._last_command_time = 0
        self._connection_timeout = 10  # Disconnect after 10 seconds of inactivity
        
        # Get custom name and room from config entry
        self.custom_name = entry.data.get(CONF_NAME, "ChromaComfort Fan")
        self.room = entry.data.get("room")
        
        # Device state - persists even when disconnected
        # This allows entities to remain available for commands
        self.data = {
            "fan_speed": 0,
            "light_on": False,
            "brightness": 255,
            "rgb_color": (255, 255, 255),
            "connected": False,  # Track connection status
        }
        
        # Build device info with custom name and area
        device_info_dict = {
            "identifiers": {(DOMAIN, address)},
            "name": self.custom_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": "1.0",
        }
        
        # Add suggested area if room is specified
        if self.room and self.room != "none":
            device_info_dict["suggested_area"] = self.room
        
        self.device_info = DeviceInfo(**device_info_dict)
        
        # Log initialization
        _LOGGER.info("[INIT] ChromaComfort coordinator initialized for %s", address)
        _LOGGER.info("[INIT] Device name: %s", self.custom_name)
        _LOGGER.info("[INIT] Room: %s", self.room or "None")
        _LOGGER.info("[INIT] On-demand connection model enabled")

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device periodically."""
        # On-demand model: Only connect for status updates if needed
        # Keep updates lightweight to not monopolize the device
        try:
            # Return cached data without connecting every time
            # Only connect periodically for status verification
            if self.hass.data.get("chromacomfort_force_update"):
                async with self._lock:
                    await self._connect_and_read_status()
                    self.hass.data["chromacomfort_force_update"] = False
            
            return self.data
                
        except Exception as err:
            _LOGGER.debug("Status update skipped (device may be in use by app): %s", err)
            # Return cached data even if update fails
            return self.data

    async def _connect_and_read_status(self) -> None:
        """Connect temporarily to read device status then disconnect."""
        _LOGGER.debug("[STATUS] Connecting for status update")
        try:
            # Quick connect
            await self._connect()
            
            # Read status
            try:
                status_data = await self.client.read_gatt_char(CHAR_DEVICE_STATUS)
                if status_data:
                    self._handle_status_notification(None, status_data)
                    _LOGGER.debug("[STATUS] Status read: %s", status_data.hex())
            except Exception:
                pass
            
            # Read other characteristics for state
            try:
                light_state = await self.client.read_gatt_char(CHAR_LIGHT_CONTROL)
                if light_state:
                    self.data["light_on"] = light_state[0] != 0 if light_state else False
            except Exception:
                pass
                
        finally:
            # Always disconnect after status read to free device
            await self._disconnect()
            _LOGGER.debug("[STATUS] Disconnected after status update")

    async def _connect(self) -> None:
        """Connect to the device and establish control session."""
        if self.client and self.client.is_connected:
            _LOGGER.debug("[BLE] Already connected")
            self._reset_disconnect_timer()
            return
        
        _LOGGER.info("[BLE] Connecting to %s for operation", self.address)
        
        # Get device from Home Assistant's Bluetooth integration
        self.device = async_ble_device_from_address(self.hass, self.address, connectable=True)
        if not self.device:
            _LOGGER.warning("[BLE] Device %s not found - may be out of range", self.address)
            raise UpdateFailed(f"Device {self.address} not found")
        
        try:
            # Connect with timeout
            self.client = await establish_connection(
                BleakClient,
                self.device,
                name=self.address,
                timeout=15.0,  # Shorter timeout for on-demand
            )
            
            _LOGGER.info("[BLE] Connected to %s", self.address)
            self.data["connected"] = True
            
            # Establish control session (mimics iOS app)
            await self._establish_control_session()
            
            # Start auto-disconnect timer
            self._reset_disconnect_timer()
            
        except Exception as err:
            _LOGGER.debug("[BLE] Connection failed (device may be in use): %s", err)
            self.data["connected"] = False
            raise

    async def _establish_control_session(self) -> None:
        """Establish control session with device - mimics iOS app workflow."""
        _LOGGER.debug("[SESSION] Establishing control session")
        
        try:
            # Step 1: Read device status to announce presence
            try:
                await self.client.read_gatt_char(CHAR_DEVICE_STATUS)
            except Exception:
                pass
            
            # Step 2: Read control characteristics to establish session
            for char_uuid in [CHAR_FAN_CONTROL, CHAR_LIGHT_CONTROL, CHAR_COLOR_CONTROL]:
                try:
                    await self.client.read_gatt_char(char_uuid)
                except Exception:
                    pass
            
            # Step 3: Subscribe to status notifications if possible
            try:
                await self.client.start_notify(CHAR_DEVICE_STATUS, self._handle_status_notification)
                _LOGGER.debug("[SESSION] Subscribed to status notifications")
            except Exception:
                _LOGGER.debug("[SESSION] Could not subscribe to notifications")
            
            _LOGGER.info("[SESSION] Control session established")
            
        except Exception as err:
            _LOGGER.warning("[SESSION] Session establishment incomplete: %s", err)

    async def _disconnect(self) -> None:
        """Disconnect from device to allow iOS app access."""
        if self.client:
            try:
                if self.client.is_connected:
                    # Unsubscribe from notifications
                    try:
                        await self.client.stop_notify(CHAR_DEVICE_STATUS)
                    except Exception:
                        pass
                    
                    await self.client.disconnect()
                    _LOGGER.info("[BLE] Disconnected from %s", self.address)
            except Exception as err:
                _LOGGER.debug("[BLE] Disconnect error: %s", err)
            finally:
                self.client = None
                self.data["connected"] = False

    def _reset_disconnect_timer(self) -> None:
        """Reset the auto-disconnect timer."""
        if self._disconnect_task:
            self._disconnect_task.cancel()
        
        async def auto_disconnect():
            await asyncio.sleep(self._connection_timeout)
            _LOGGER.debug("[BLE] Auto-disconnecting after %d seconds of inactivity", self._connection_timeout)
            await self._disconnect()
        
        self._disconnect_task = asyncio.create_task(auto_disconnect())

    def _handle_status_notification(self, sender: Any, data: bytes) -> None:
        """Handle status notification from device."""
        if data and len(data) >= 7:
            # Parse status based on discovered patterns
            # Byte 5 (0-indexed) = 0x41 base state
            # Byte 6 (0-indexed) = control flags
            # 0x00 = All off, 0x80 = Fan on, 0x20/0x40 = Light on
            
            if len(data) > 6:
                control_byte = data[6]
                
                # Fan state
                fan_on = (control_byte & 0x80) != 0
                self.data["fan_speed"] = 1 if fan_on else 0
                
                # Light state  
                light_on = (control_byte & 0x60) != 0  # 0x20 or 0x40
                self.data["light_on"] = light_on
                
                _LOGGER.debug("[STATUS] Fan: %s, Light: %s (byte: 0x%02x)", 
                            "ON" if fan_on else "OFF",
                            "ON" if light_on else "OFF", 
                            control_byte)

    async def disconnect(self) -> None:
        """Public method to disconnect from device."""
        async with self._lock:
            await self._disconnect()

    async def set_fan_speed(self, speed: int) -> None:
        """Set the fan speed (0=off, 1+=on)."""
        async with self._lock:
            try:
                # Connect on-demand for command
                await self._connect()
                
                old_speed = self.data["fan_speed"]
                self.data["fan_speed"] = speed
                
                # Send appropriate command
                if speed == 0:
                    success = await self._try_fan_command("OFF", FAN_CMD_OFF, FAN_CMD_OFF_ALT)
                else:
                    success = await self._try_fan_command("ON", FAN_CMD_ON, FAN_CMD_ON_ALT)
                
                if not success:
                    # Revert if command failed
                    self.data["fan_speed"] = old_speed
                    _LOGGER.error("[FAN] Command failed")
                
                # Reset disconnect timer after command
                self._reset_disconnect_timer()
                
            except Exception as err:
                _LOGGER.error("[FAN] Error: %s", err)

    async def set_light_state(self, is_on: bool) -> None:
        """Turn the light on or off."""
        async with self._lock:
            try:
                # Connect on-demand for command
                await self._connect()
                
                old_state = self.data["light_on"]
                self.data["light_on"] = is_on
                
                # Send appropriate command
                if is_on:
                    success = await self._try_light_command("ON", LIGHT_CMD_ON, LIGHT_CMD_ON_ALT)
                else:
                    success = await self._try_light_command("OFF", LIGHT_CMD_OFF, LIGHT_CMD_OFF_ALT)
                
                if not success:
                    # Revert if command failed
                    self.data["light_on"] = old_state
                    _LOGGER.error("[LIGHT] Command failed")
                
                # Reset disconnect timer after command
                self._reset_disconnect_timer()
                
            except Exception as err:
                _LOGGER.error("[LIGHT] Error: %s", err)

    async def set_light_brightness(self, brightness: int) -> None:
        """Set the light brightness."""
        # TODO: Implement once command format verified
        self.data["brightness"] = brightness
        _LOGGER.debug("[LIGHT] Brightness control not yet implemented")

    async def set_light_color(self, rgb: tuple[int, int, int]) -> None:
        """Set the light RGB color."""
        async with self._lock:
            try:
                # Connect on-demand for command
                await self._connect()
                
                # Send color command
                r, g, b = rgb
                if r == 0 and g == 0 and b == 0:
                    # Turn color off
                    await self.client.write_gatt_char(CHAR_COLOR_CONTROL, COLOR_CMD_OFF)
                    _LOGGER.debug("[COLOR] Sent OFF command")
                else:
                    # RGB command (format needs verification)
                    color_cmd = bytes([0x80, 0x25, r//10, g//10, b//10, 0x00])
                    await self.client.write_gatt_char(CHAR_COLOR_CONTROL, color_cmd)
                    _LOGGER.debug("[COLOR] Sent RGB command: %s", color_cmd.hex())
                
                self.data["rgb_color"] = rgb
                
                # Reset disconnect timer after command
                self._reset_disconnect_timer()
                
            except Exception as err:
                _LOGGER.error("[COLOR] Error: %s", err)

    async def _try_fan_command(self, action: str, cmd1: bytes, cmd2: bytes) -> bool:
        """Try different command formats for fan control."""
        for desc, cmd in [("Simple", cmd1), ("Multi-byte", cmd2)]:
            try:
                await self.client.write_gatt_char(CHAR_FAN_CONTROL, cmd, response=False)
                _LOGGER.info("[FAN] %s command sent (%s): %s", action, desc, cmd.hex())
                await asyncio.sleep(0.5)
                return True
            except Exception as e:
                _LOGGER.debug("[FAN] %s %s failed: %s", action, desc, e)
        return False

    async def _try_light_command(self, action: str, cmd1: bytes, cmd2: bytes) -> bool:
        """Try different command formats for light control."""
        for desc, cmd in [("Simple", cmd1), ("Multi-byte", cmd2)]:
            try:
                await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, cmd, response=False)
                _LOGGER.info("[LIGHT] %s command sent (%s): %s", action, desc, cmd.hex())
                await asyncio.sleep(0.5)
                return True
            except Exception as e:
                _LOGGER.debug("[LIGHT] %s %s failed: %s", action, desc, e)
        return False