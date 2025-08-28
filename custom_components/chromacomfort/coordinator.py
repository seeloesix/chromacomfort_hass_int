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

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        try:
            async with self._lock:
                if not self.client or not self.client.is_connected:
                    _LOGGER.debug("Attempting to connect to device %s", self.address)
                    await self._connect()
                
                # Try to read device status periodically since notifications don't work
                try:
                    _LOGGER.debug("[UPDATE] Trying to read device status for periodic update")
                    status_data = await self.client.read_gatt_char(CHAR_DEVICE_STATUS)
                    if status_data:
                        _LOGGER.debug("[UPDATE] 📊 Periodic status read: %s", status_data.hex())
                        self._handle_status_notification(None, status_data)
                    else:
                        _LOGGER.debug("[UPDATE] No status data available")
                except Exception as read_err:
                    _LOGGER.debug("[UPDATE] Could not read status during update: %s", read_err)
                
                _LOGGER.debug("Returning current state for device %s: %s", self.address, self.data)
                return self.data
                
        except Exception as err:
            _LOGGER.error("Error communicating with device %s: %s", self.address, err)
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    async def _connect(self) -> None:
        """Connect to the device."""
        _LOGGER.info("[BLE] Starting connection process to %s", self.address)
        
        if self.client:
            _LOGGER.info("[BLE] Existing client found, disconnecting first")
            await self.disconnect()
        
        # Get device from Home Assistant's Bluetooth integration
        _LOGGER.debug("[BLE] Looking up device %s in HA Bluetooth registry", self.address)
        
        # Debug: Check what devices are available
        try:
            from homeassistant.components.bluetooth import async_discovered_service_info
            discovered = list(async_discovered_service_info(self.hass, connectable=True))
            _LOGGER.debug("[BLE] Found %d connectable devices in HA registry", len(discovered))
            for device in discovered:
                if device.address == self.address:
                    _LOGGER.info("[BLE] ✅ Target device found in registry: %s (%s) RSSI: %s", 
                               device.name, device.address, getattr(device, 'rssi', 'Unknown'))
                    break
            else:
                _LOGGER.warning("[BLE] ⚠️ Target device %s NOT found in current registry scan", self.address)
                _LOGGER.info("[BLE] Available devices: %s", [(d.name, d.address) for d in discovered[:5]])
        except Exception as e:
            _LOGGER.debug("[BLE] Could not check device registry: %s", e)
        
        # Note: async_ble_device_from_address is NOT async, despite the name
        self.device = async_ble_device_from_address(self.hass, self.address, connectable=True)
        if not self.device:
            _LOGGER.error("[BLE] Could not find BLE device with address %s in HA registry", self.address)
            _LOGGER.error("[BLE] Device may not be advertising or within range")
            raise UpdateFailed(f"Could not find device {self.address}")
        
        _LOGGER.info("[BLE] Found BLE device: %s at %s (RSSI: %s)", 
                    self.device.name, self.address, getattr(self.device, 'rssi', 'Unknown'))
        _LOGGER.debug("[BLE] Device details: %s", self.device)
        
        try:
            # Use retry connector for reliable connection
            _LOGGER.info("[BLE] Establishing BLE connection to %s using bleak-retry-connector", self.address)
            _LOGGER.debug("[BLE] Connection timeout: 30.0 seconds")
            
            self.client = await establish_connection(
                BleakClient,
                self.device,
                name=self.address,
                timeout=30.0,
            )
            
            _LOGGER.info("[BLE] ✅ Successfully connected to %s", self.address)
            _LOGGER.info("[BLE] Client connected: %s", self.client.is_connected)
            _LOGGER.debug("[BLE] Client details: %s", self.client)
            
            # Check if device is already paired/bonded
            try:
                is_paired = getattr(self.client, 'is_paired', False)
                if callable(is_paired):
                    is_paired = await is_paired() if hasattr(is_paired, '__await__') else is_paired()
                _LOGGER.info("[BLE] Device pairing status: %s", "Paired" if is_paired else "Not paired")
            except Exception:
                _LOGGER.debug("[BLE] Could not determine pairing status")
            
            # Do service discovery FIRST, then attempt pairing
            _LOGGER.info("[BLE] Performing service discovery before pairing attempt")
            try:
                services = self.client.services
                if not services:
                    _LOGGER.warning("[BLE] No services found - this may indicate auth is required first")
                else:
                    _LOGGER.info("[BLE] Found %d services without authentication", len(list(services)))
            except Exception as disc_err:
                _LOGGER.info("[BLE] Service discovery failed: %s", disc_err)
            
            # Establish control session - mimic iPhone app's connection workflow
            await self._establish_control_session()
            
        except Exception as err:
            _LOGGER.error("[BLE] ❌ Failed to establish BLE connection to %s: %s", self.address, err)
            _LOGGER.error("[BLE] Error type: %s", type(err).__name__)
            _LOGGER.error("[BLE] This could be due to: device out of range, already connected elsewhere, or BLE permissions")
            raise UpdateFailed(f"Could not connect to device: {err}") from err
        
        # Discover services and characteristics
        _LOGGER.info("[BLE] Discovering GATT services and characteristics")
        try:
            services = self.client.services
            # BleakGATTServiceCollection is iterable but not len()-able
            service_list = list(services) if services else []
            _LOGGER.info("[BLE] Found %d services", len(service_list))
            
            # Log all services and characteristics for debugging
            for i, service in enumerate(service_list, 1):
                _LOGGER.info("[BLE] Service %d: %s", i, service.uuid)
                _LOGGER.debug("[BLE]   Service description: %s", service.description)
                
                for j, char in enumerate(service.characteristics, 1):
                    _LOGGER.info("[BLE]   Characteristic %d.%d: %s (properties: %s)", 
                               i, j, char.uuid, char.properties)
                    _LOGGER.debug("[BLE]     Char description: %s", getattr(char, 'description', 'No description'))
                    
                    # Log if characteristic is writable
                    if hasattr(char, 'properties'):
                        if 'write' in char.properties or 'write-without-response' in char.properties:
                            _LOGGER.info("[BLE]     ✍️ WRITABLE characteristic")
                    
                    # Check if this matches our expected characteristics
                    if char.uuid.lower() in [uuid.lower() for uuid in [
                        "00001018-d102-11e1-9b23-00025b00a5a5",  # CHAR_FAN_CONTROL
                        "00001013-d102-11e1-9b23-00025b00a5a5",  # CHAR_LIGHT_CONTROL
                        "bb8a27e1-c37c-11e3-b954-0228ac012a70",  # CHAR_COLOR_CONTROL
                        "00001014-d102-11e1-9b23-00025b00a5a5",  # CHAR_DEVICE_STATUS
                    ]]:
                        _LOGGER.info("[BLE]     ✅ FOUND EXPECTED ChromaComfort characteristic: %s", char.uuid)
                        
        except Exception as err:
            _LOGGER.error("[BLE] ❌ Could not enumerate services: %s", err)
            _LOGGER.error("[BLE] This may indicate connection issues or unsupported device")
        
        # Try multiple approaches to get device status
        _LOGGER.info("[BLE] Attempting to get device status using multiple methods")
        
        # Method 1: Try to read current device status directly
        try:
            status_data = await self.client.read_gatt_char(CHAR_DEVICE_STATUS)
            _LOGGER.info("[BLE] 📊 Method 1 - Direct status read: %s", status_data.hex() if status_data else "No data")
            if status_data:
                self._handle_status_notification(None, status_data)
        except Exception as read_err:
            _LOGGER.info("[BLE] Method 1 failed - Could not read status directly: %s", read_err)
        
        # Method 2: Try to subscribe to status notifications  
        _LOGGER.info("[BLE] Method 2 - Attempting to subscribe to status notifications")
        _LOGGER.debug("[BLE] Status characteristic UUID: %s", CHAR_DEVICE_STATUS)
        try:
            await self.client.start_notify(CHAR_DEVICE_STATUS, self._handle_status_notification)
            _LOGGER.info("[BLE] ✅ Method 2 succeeded - Subscribed to device status notifications")
        except Exception as err:
            _LOGGER.info("[BLE] Method 2 failed - Could not subscribe to status notifications: %s", err)
            _LOGGER.debug("[BLE] Notification error type: %s", type(err).__name__)
        
        # Method 3: Check for alternative notification characteristics
        _LOGGER.info("[BLE] Method 3 - Looking for alternative notification characteristics")
        for service in self.client.services:
            for char in service.characteristics:
                if 'notify' in char.properties:
                    _LOGGER.info("[BLE] Found notify characteristic: %s (properties: %s)", char.uuid, char.properties)
                    if char.uuid.lower() != CHAR_DEVICE_STATUS.lower():
                        try:
                            _LOGGER.info("[BLE] Trying to subscribe to alternative characteristic: %s", char.uuid)
                            await self.client.start_notify(char.uuid, self._handle_alt_status_notification)
                            _LOGGER.info("[BLE] ✅ Subscribed to alternative notification: %s", char.uuid)
                            break
                        except Exception as alt_err:
                            _LOGGER.debug("[BLE] Alternative notification failed: %s", alt_err)
        
        _LOGGER.info("[BLE] Status monitoring setup completed - will work with available methods")

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self.client:
            _LOGGER.info("[BLE] Disconnecting from %s", self.address)
            try:
                await self.client.disconnect()
                _LOGGER.info("[BLE] ✅ Disconnected from %s", self.address)
            except Exception as err:
                _LOGGER.warning("[BLE] Error during disconnect: %s", err)
            finally:
                self.client = None
        else:
            _LOGGER.debug("[BLE] No active connection to disconnect")

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
                        _LOGGER.info("[FAN] No active connection, establishing connection for fan command")
                        await self._connect()
                    except Exception as err:
                        _LOGGER.warning("[FAN] ⚠️ Could not connect to device for fan control: %s", err)
                        # Keep the local state updated even if BLE fails
                        await self.async_request_refresh()
                        return
                
                # Send fan control command based on discovered protocol
                try:
                    # Check if characteristic exists before writing
                    if not self.client.services:
                        _LOGGER.warning("[FAN] ⚠️ No services discovered yet for %s", self.address)
                        return
                    
                    _LOGGER.info("[FAN] Preparing to send fan command to %s (speed: %s)", self.address, speed)
                    _LOGGER.debug("[FAN] Fan control characteristic: %s", CHAR_FAN_CONTROL)
                    
                    # Check if the characteristic exists
                    char_found = False
                    for service in self.client.services:
                        for char in service.characteristics:
                            if char.uuid.lower() == CHAR_FAN_CONTROL.lower():
                                char_found = True
                                _LOGGER.debug("[FAN] ✅ Found fan characteristic with properties: %s", char.properties)
                                break
                    
                    if not char_found:
                        _LOGGER.error("[FAN] ❌ Fan control characteristic %s not found!", CHAR_FAN_CONTROL)
                        _LOGGER.info("[FAN] Available characteristics: %s", 
                                   [char.uuid for service in self.client.services for char in service.characteristics])
                        return
                    
                    if speed == 0:
                        # Try multiple command formats for better compatibility
                        success = await self._try_fan_command("OFF", FAN_CMD_OFF, FAN_CMD_OFF_ALT)
                        if success:
                            _LOGGER.info("[FAN] ✅ Sent fan OFF command to %s", self.address)
                        else:
                            _LOGGER.error("[FAN] ❌ All fan OFF command formats failed for %s", self.address)
                    else:
                        # Try multiple command formats for better compatibility
                        success = await self._try_fan_command("ON", FAN_CMD_ON, FAN_CMD_ON_ALT)
                        if success:
                            _LOGGER.info("[FAN] ✅ Sent fan ON command (speed %s) to %s", speed, self.address)
                        else:
                            _LOGGER.error("[FAN] ❌ All fan ON command formats failed for %s", self.address)
                    
                except Exception as err:
                    _LOGGER.error("[FAN] ❌ Failed to send fan command to device %s: %s", self.address, err)
                    _LOGGER.error("[FAN] Error type: %s", type(err).__name__)
                    _LOGGER.debug("[FAN] Full error details:", exc_info=True)
                    # Revert state if command failed
                    self.data["fan_speed"] = old_speed
                    raise
        except Exception as err:
            _LOGGER.error("[FAN] ❌ Error in set_fan_speed for %s: %s", self.address, err)
            _LOGGER.error("[FAN] Error type: %s", type(err).__name__)
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
                        _LOGGER.warning("[LIGHT] ⚠️ No services discovered yet for %s", self.address)
                        return
                    
                    _LOGGER.info("[LIGHT] Preparing to send light command (on=%s) to %s", on, self.address)
                    _LOGGER.debug("[LIGHT] Light control characteristic: %s", CHAR_LIGHT_CONTROL)
                    
                    # Check if the characteristic exists
                    char_found = False
                    for service in self.client.services:
                        for char in service.characteristics:
                            if char.uuid.lower() == CHAR_LIGHT_CONTROL.lower():
                                char_found = True
                                _LOGGER.debug("[LIGHT] ✅ Found light characteristic with properties: %s", char.properties)
                                break
                    
                    if not char_found:
                        _LOGGER.error("[LIGHT] ❌ Light control characteristic %s not found!", CHAR_LIGHT_CONTROL)
                        _LOGGER.info("[LIGHT] Available characteristics: %s", 
                                   [char.uuid for service in self.client.services for char in service.characteristics])
                        return
                    
                    if on:
                        # Try multiple command formats for better compatibility
                        success = await self._try_light_command("ON", LIGHT_CMD_ON, LIGHT_CMD_ON_ALT)
                        if success:
                            _LOGGER.info("[LIGHT] ✅ Sent light ON command to %s", self.address)
                        else:
                            _LOGGER.error("[LIGHT] ❌ All light ON command formats failed for %s", self.address)
                    else:
                        # Try multiple command formats for better compatibility  
                        success = await self._try_light_command("OFF", LIGHT_CMD_OFF, LIGHT_CMD_OFF_ALT)
                        if success:
                            _LOGGER.info("[LIGHT] ✅ Sent light OFF command to %s", self.address)
                        else:
                            _LOGGER.error("[LIGHT] ❌ All light OFF command formats failed for %s", self.address)
                    
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

    async def _try_fan_command(self, action: str, cmd1: bytes, cmd2: bytes) -> bool:
        """Try different command formats and write methods for fan control."""
        commands_to_try = [
            ("Simple format", cmd1, False),
            ("Multi-byte format", cmd2, False), 
            ("Simple format (no response)", cmd1, True),
            ("Multi-byte format (no response)", cmd2, True),
        ]
        
        for desc, cmd, no_response in commands_to_try:
            try:
                _LOGGER.info("[FAN] Trying %s %s command: %s", action, desc.lower(), cmd.hex())
                if no_response:
                    await self.client.write_gatt_char(CHAR_FAN_CONTROL, cmd, response=False)
                else:
                    await self.client.write_gatt_char(CHAR_FAN_CONTROL, cmd, response=True)
                
                _LOGGER.info("[FAN] ✅ %s %s succeeded", action, desc)
                # Wait a moment to see if device responds
                await asyncio.sleep(1)
                return True
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'permission' in error_msg or 'authentication' in error_msg or 'pair' in error_msg:
                    _LOGGER.warning("[FAN] ❌ %s %s failed - Session/Permission issue: %s", action, desc, e)
                    _LOGGER.info("[FAN] Device may require proper control session establishment")
                elif 'not connected' in error_msg:
                    _LOGGER.warning("[FAN] ❌ %s %s failed - Connection lost: %s", action, desc, e)
                    _LOGGER.info("[FAN] Control session may have expired")
                else:
                    _LOGGER.warning("[FAN] ❌ %s %s failed: %s", action, desc, e)
                continue
        
        return False

    async def _try_light_command(self, action: str, cmd1: bytes, cmd2: bytes) -> bool:
        """Try different command formats and write methods for light control.""" 
        commands_to_try = [
            ("Simple format", cmd1, False),
            ("Multi-byte format", cmd2, False),
            ("Simple format (no response)", cmd1, True), 
            ("Multi-byte format (no response)", cmd2, True),
        ]
        
        for desc, cmd, no_response in commands_to_try:
            try:
                _LOGGER.info("[LIGHT] Trying %s %s command: %s", action, desc.lower(), cmd.hex())
                if no_response:
                    await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, cmd, response=False)
                else:
                    await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, cmd, response=True)
                
                _LOGGER.info("[LIGHT] ✅ %s %s succeeded", action, desc)
                # Wait a moment to see if device responds
                await asyncio.sleep(1)
                return True
                
            except Exception as e:
                error_msg = str(e).lower()
                if 'permission' in error_msg or 'authentication' in error_msg or 'pair' in error_msg:
                    _LOGGER.warning("[LIGHT] ❌ %s %s failed - Session/Permission issue: %s", action, desc, e)
                    _LOGGER.info("[LIGHT] Device may require proper control session establishment")
                elif 'not connected' in error_msg:
                    _LOGGER.warning("[LIGHT] ❌ %s %s failed - Connection lost: %s", action, desc, e)
                    _LOGGER.info("[LIGHT] Control session may have expired")
                else:
                    _LOGGER.warning("[LIGHT] ❌ %s %s failed: %s", action, desc, e)
                continue
        
        return False

    async def _establish_control_session(self) -> None:
        """Establish control session with device - mimic iPhone app workflow."""
        _LOGGER.info("[SESSION] 🎮 Establishing control session with device")
        
        try:
            # Step 1: Read device status to announce our presence
            _LOGGER.info("[SESSION] Step 1: Reading device status to establish presence")
            try:
                status_data = await self.client.read_gatt_char(CHAR_DEVICE_STATUS)
                _LOGGER.info("[SESSION] ✅ Device status read: %s", status_data.hex() if status_data else "No data")
                if status_data:
                    self._handle_status_notification(None, status_data)
            except Exception as status_err:
                _LOGGER.info("[SESSION] Status read failed: %s", status_err)
            
            # Step 2: Read all control characteristics to establish session
            _LOGGER.info("[SESSION] Step 2: Reading all control characteristics to establish session")
            
            control_chars = [
                (CHAR_LIGHT_CONTROL, "Light Control"),
                (CHAR_FAN_CONTROL, "Fan Control"), 
                (CHAR_COLOR_CONTROL, "Color Control"),
            ]
            
            for char_uuid, char_name in control_chars:
                try:
                    _LOGGER.info("[SESSION] Reading %s (%s)", char_name, char_uuid)
                    data = await self.client.read_gatt_char(char_uuid)
                    _LOGGER.info("[SESSION] ✅ %s current value: %s", char_name, 
                               data.hex() if data else "No data")
                except Exception as read_err:
                    _LOGGER.info("[SESSION] %s read failed: %s", char_name, read_err)
            
            # Step 3: Send "session start" handshake - try writing current state back
            _LOGGER.info("[SESSION] Step 3: Sending session handshake")
            try:
                # Try writing the light control's current value back to it (harmless echo)
                light_data = await self.client.read_gatt_char(CHAR_LIGHT_CONTROL)
                if light_data:
                    _LOGGER.info("[SESSION] Echoing light control value back: %s", light_data.hex())
                    await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, light_data)
                    _LOGGER.info("[SESSION] ✅ Session handshake successful")
                else:
                    # Try a neutral handshake command
                    handshake_cmd = bytes([0x00])
                    _LOGGER.info("[SESSION] Sending neutral handshake: %s", handshake_cmd.hex())
                    await self.client.write_gatt_char(CHAR_LIGHT_CONTROL, handshake_cmd)
                    _LOGGER.info("[SESSION] ✅ Neutral handshake successful")
            except Exception as handshake_err:
                _LOGGER.info("[SESSION] Handshake failed: %s", handshake_err)
            
            # Step 4: Subscribe to notifications (iPhone app likely does this)
            _LOGGER.info("[SESSION] Step 4: Subscribing to status notifications")
            try:
                await self.client.start_notify(CHAR_DEVICE_STATUS, self._handle_status_notification)
                _LOGGER.info("[SESSION] ✅ Status notifications enabled")
            except Exception as notify_err:
                _LOGGER.info("[SESSION] Status notification subscription failed: %s", notify_err)
            
            # Step 5: Try alternative notification characteristics
            _LOGGER.info("[SESSION] Step 5: Checking for additional notification characteristics")
            try:
                for service in self.client.services:
                    for char in service.characteristics:
                        if 'notify' in char.properties and char.uuid.lower() != CHAR_DEVICE_STATUS.lower():
                            try:
                                _LOGGER.info("[SESSION] Subscribing to additional notification: %s", char.uuid)
                                await self.client.start_notify(char.uuid, self._handle_alt_status_notification)
                                _LOGGER.info("[SESSION] ✅ Additional notification enabled: %s", char.uuid)
                                break  # Only subscribe to one additional for now
                            except Exception:
                                continue
            except Exception as alt_notify_err:
                _LOGGER.debug("[SESSION] Alternative notification setup failed: %s", alt_notify_err)
            
            _LOGGER.info("[SESSION] 🎮 Control session established - device should now accept commands")
            
        except Exception as err:
            _LOGGER.warning("[SESSION] ⚠️ Session establishment encountered error: %s", err)
            _LOGGER.info("[SESSION] Continuing - some session features may not work")

    def _handle_status_notification(self, sender, data: bytes) -> None:
        """Handle status notifications from the device."""
        try:
            _LOGGER.info("[STATUS] 📨 Received status notification: %s (%d bytes)", 
                        data.hex() if data else "No data", len(data) if data else 0)
            
            if not data or len(data) == 0:
                _LOGGER.warning("[STATUS] ⚠️ Received empty status notification")
                return
                
            # Log all bytes for debugging
            if len(data) > 0:
                byte_str = " ".join([f"byte[{i}]={data[i]:02x}" for i in range(len(data))])
                _LOGGER.info("[STATUS] 🔍 Status bytes: %s", byte_str)
                
            if len(data) >= 6:  # Ensure we have enough bytes
                # Decode status based on captured pattern analysis
                # Byte 5 (0-indexed): Always 0x41 (base state)
                # Byte 6 (0-indexed): Control state flags
                status_byte = data[5] if len(data) > 5 else 0x00
                
                # Interpret status flags
                fan_on = (status_byte & 0x80) != 0
                light_on = (status_byte & 0x60) != 0  # 0x20, 0x40, 0xA0, 0xC0 indicate light states
                
                _LOGGER.info("[STATUS] 🔍 Decoded from byte[5]=0x%02x: fan_on=%s, light_on=%s", 
                           status_byte, fan_on, light_on)
                
                # Update local state
                old_fan_speed = self.data["fan_speed"] 
                old_light_on = self.data["light_on"]
                
                self.data["fan_speed"] = 1 if fan_on else 0
                self.data["light_on"] = light_on
                
                _LOGGER.info("[STATUS] 📊 State change: fan %d→%d, light %s→%s", 
                           old_fan_speed, self.data["fan_speed"], old_light_on, light_on)
                
                # Trigger update if state changed
                if old_fan_speed != self.data["fan_speed"] or old_light_on != self.data["light_on"]:
                    _LOGGER.info("[STATUS] ✅ Triggering HA state update")
                    self.async_set_updated_data(self.data)
                else:
                    _LOGGER.debug("[STATUS] No state change, not triggering update")
            else:
                _LOGGER.warning("[STATUS] ⚠️ Status notification too short: %d bytes (expected ≥6)", len(data))
            
        except Exception as err:
            _LOGGER.error("[STATUS] ❌ Error processing status notification: %s", err, exc_info=True)

    def _handle_alt_status_notification(self, sender, data: bytes) -> None:
        """Handle status notifications from alternative characteristics."""
        try:
            _LOGGER.info("[ALT-STATUS] 📨 Received alternative notification: %s (%d bytes)", 
                        data.hex() if data else "No data", len(data) if data else 0)
            
            if data and len(data) > 0:
                # Log all bytes for analysis
                byte_str = " ".join([f"byte[{i}]={data[i]:02x}" for i in range(len(data))])
                _LOGGER.info("[ALT-STATUS] 🔍 Alternative notification bytes: %s", byte_str)
                
                # For now, just log the data to understand the format
                _LOGGER.info("[ALT-STATUS] This might contain status information to decode")
            
        except Exception as err:
            _LOGGER.error("[ALT-STATUS] ❌ Error processing alternative status notification: %s", err, exc_info=True)