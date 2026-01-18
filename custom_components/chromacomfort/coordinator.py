"""Data coordinator for ChromaComfort integration.

This coordinator manages BLE communication with ChromaComfort fans.
It follows the same workflow as the iOS app:
1. Scan and discover devices
2. Connect to selected device
3. Pair using PIN 1234 (handled by Bleak/OS)
4. Send commands while connected
5. Disconnect when idle
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection, BleakNotFoundError

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
    CONNECTION_TIMEOUT,
    DEFAULT_PIN_CODE,
)

_LOGGER = logging.getLogger(__name__)

# Auto-disconnect after this many seconds of inactivity
DISCONNECT_DELAY = 10


class ChromaComfortCoordinator(DataUpdateCoordinator):
    """Coordinator for ChromaComfort device communication.

    Mirrors iOS app behavior:
    - Connect on-demand when user wants to control device
    - Stay connected while actively sending commands
    - Disconnect after period of inactivity
    - Reconnect automatically when needed
    """

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
        self.client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._disconnect_timer: asyncio.TimerHandle | None = None

        # Get custom name and room from config entry
        self.custom_name = entry.data.get(CONF_NAME, "ChromaComfort Fan")
        self.room = entry.data.get("room")

        # Device state - persists even when disconnected
        self.data = {
            "fan_on": False,
            "light_on": False,
            "brightness": 255,
            "rgb_color": (255, 255, 255),
            "connected": False,
        }

        # Build device info
        device_info_dict = {
            "identifiers": {(DOMAIN, address)},
            "name": self.custom_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
            "sw_version": "1.0",
        }

        if self.room and self.room != "none":
            device_info_dict["suggested_area"] = self.room

        self.device_info = DeviceInfo(**device_info_dict)

        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )
        _LOGGER.info(
            "  ChromaComfort Integration Initialized"
        )
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )
        _LOGGER.info("  Device Name: %s", self.custom_name)
        _LOGGER.info("  BLE Address: %s", address)
        _LOGGER.info("  Room: %s", self.room or "Not assigned")
        _LOGGER.info("  Pairing PIN: %s", DEFAULT_PIN_CODE)
        _LOGGER.info("  Auto-disconnect: %d seconds", DISCONNECT_DELAY)
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from device (called periodically by HA)."""
        # Return cached data - we don't poll the device to avoid
        # keeping connection open and blocking iOS app
        return self.data

    async def async_connect(self) -> bool:
        """Connect to the device.

        This mirrors how the iOS app connects:
        1. Get the BLE device
        2. Establish connection (Bleak handles pairing with PIN 1234)
        3. Subscribe to status notifications
        """
        if self.client and self.client.is_connected:
            _LOGGER.debug("  [BLE] Already connected to %s", self.address)
            self._schedule_disconnect()
            return True

        _LOGGER.info(
            "───────────────────────────────────────────────────────────────"
        )
        _LOGGER.info("  [BLE] CONNECTING to %s", self.address)
        _LOGGER.info(
            "───────────────────────────────────────────────────────────────"
        )

        # Get device from Home Assistant's Bluetooth integration
        _LOGGER.info("  [BLE] Step 1: Looking up device in Home Assistant...")
        device = async_ble_device_from_address(self.hass, self.address, connectable=True)

        if not device:
            _LOGGER.error("  [BLE] ✗ FAILED: Device %s not found!", self.address)
            _LOGGER.error("  [BLE]   → Is the fan powered on?")
            _LOGGER.error("  [BLE]   → Is it within Bluetooth range (~30 feet)?")
            _LOGGER.error("  [BLE]   → Is the iOS app disconnected?")
            return False

        _LOGGER.info("  [BLE] ✓ Device found: %s", device.name or "Unknown")

        try:
            _LOGGER.info("  [BLE] Step 2: Establishing BLE connection...")
            _LOGGER.info("  [BLE]   → Timeout: %d seconds", CONNECTION_TIMEOUT)
            _LOGGER.info("  [BLE]   → If prompted, PIN is: %s", DEFAULT_PIN_CODE)

            # Connect using bleak-retry-connector for robustness
            self.client = await establish_connection(
                BleakClient,
                device,
                self.address,
                disconnected_callback=self._on_disconnect,
                timeout=CONNECTION_TIMEOUT,
            )

            _LOGGER.info("  [BLE] ✓ Connected successfully!")
            self.data["connected"] = True

            # Log discovered services
            _LOGGER.info("  [BLE] Step 3: Discovering BLE services...")
            if self.client.services:
                service_count = len(list(self.client.services))
                _LOGGER.info("  [BLE] ✓ Found %d services", service_count)

                for service in self.client.services:
                    _LOGGER.debug("  [BLE]   Service: %s", service.uuid)
                    for char in service.characteristics:
                        props = ", ".join(char.properties)
                        _LOGGER.debug("  [BLE]     └─ Char: %s [%s]", char.uuid[-8:], props)

            # Subscribe to status notifications
            _LOGGER.info("  [BLE] Step 4: Subscribing to status notifications...")
            try:
                await self.client.start_notify(CHAR_DEVICE_STATUS, self._on_status_notification)
                _LOGGER.info("  [BLE] ✓ Subscribed to status notifications")
            except Exception as e:
                _LOGGER.warning("  [BLE] ⚠ Could not subscribe to notifications: %s", e)

            # Read initial status
            _LOGGER.info("  [BLE] Step 5: Reading initial device status...")
            await self._read_device_status()

            # Schedule auto-disconnect
            _LOGGER.info("  [BLE] Step 6: Scheduling auto-disconnect in %ds...", DISCONNECT_DELAY)
            self._schedule_disconnect()

            _LOGGER.info(
                "───────────────────────────────────────────────────────────────"
            )
            _LOGGER.info("  [BLE] ✓ CONNECTION COMPLETE - Ready to send commands")
            _LOGGER.info(
                "───────────────────────────────────────────────────────────────"
            )

            return True

        except BleakNotFoundError:
            _LOGGER.error("  [BLE] ✗ FAILED: Device not found during connection")
            self.data["connected"] = False
            return False
        except BleakError as e:
            _LOGGER.error("  [BLE] ✗ FAILED: BLE error - %s", e)
            _LOGGER.error("  [BLE]   → Try closing the iOS app and retry")
            self.data["connected"] = False
            return False
        except asyncio.TimeoutError:
            _LOGGER.error("  [BLE] ✗ FAILED: Connection timed out after %ds", CONNECTION_TIMEOUT)
            self.data["connected"] = False
            return False
        except Exception as e:
            _LOGGER.error("  [BLE] ✗ FAILED: Unexpected error - %s", e)
            _LOGGER.exception("  [BLE] Full traceback:")
            self.data["connected"] = False
            return False

    async def async_disconnect(self) -> None:
        """Disconnect from the device."""
        self._cancel_disconnect_timer()

        if self.client:
            _LOGGER.info("  [BLE] Disconnecting from %s...", self.address)
            try:
                if self.client.is_connected:
                    # Unsubscribe from notifications
                    try:
                        await self.client.stop_notify(CHAR_DEVICE_STATUS)
                        _LOGGER.debug("  [BLE] Unsubscribed from notifications")
                    except Exception:
                        pass

                    await self.client.disconnect()
                    _LOGGER.info("  [BLE] ✓ Disconnected - Device is now free for iOS app")
            except Exception as e:
                _LOGGER.debug("  [BLE] Disconnect error (ignored): %s", e)
            finally:
                self.client = None
                self.data["connected"] = False

    def _on_disconnect(self, client: BleakClient) -> None:
        """Handle unexpected disconnection."""
        _LOGGER.warning("  [BLE] ⚠ Device disconnected unexpectedly!")
        self.client = None
        self.data["connected"] = False
        self._cancel_disconnect_timer()

    def _schedule_disconnect(self) -> None:
        """Schedule auto-disconnect after inactivity period."""
        self._cancel_disconnect_timer()

        self._disconnect_timer = self.hass.loop.call_later(
            DISCONNECT_DELAY,
            lambda: asyncio.create_task(self._auto_disconnect())
        )
        _LOGGER.debug("  [BLE] Auto-disconnect scheduled in %ds", DISCONNECT_DELAY)

    def _cancel_disconnect_timer(self) -> None:
        """Cancel any pending disconnect timer."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
            self._disconnect_timer = None

    async def _auto_disconnect(self) -> None:
        """Auto-disconnect after inactivity (like iOS app does when backgrounded)."""
        _LOGGER.info("  [BLE] Auto-disconnecting after %ds of inactivity...", DISCONNECT_DELAY)
        await self.async_disconnect()

    def _on_status_notification(self, sender: Any, data: bytes) -> None:
        """Handle status notification from device."""
        if not data or len(data) < 7:
            _LOGGER.debug("  [STATUS] Received short notification (%d bytes)", len(data) if data else 0)
            return

        # Log raw data
        _LOGGER.debug("  [STATUS] Raw data: %s", data.hex())

        # Parse status byte (byte 6) to determine fan/light state
        control_byte = data[6]

        old_fan = self.data["fan_on"]
        old_light = self.data["light_on"]

        fan_on = (control_byte & 0x80) != 0
        light_on = (control_byte & 0x60) != 0

        self.data["fan_on"] = fan_on
        self.data["light_on"] = light_on

        # Log state changes
        if fan_on != old_fan or light_on != old_light:
            _LOGGER.info(
                "  [STATUS] State update: Fan=%s, Light=%s (control byte: 0x%02X)",
                "ON" if fan_on else "OFF",
                "ON" if light_on else "OFF",
                control_byte
            )
        else:
            _LOGGER.debug(
                "  [STATUS] Fan=%s, Light=%s (0x%02X)",
                "ON" if fan_on else "OFF",
                "ON" if light_on else "OFF",
                control_byte
            )

    async def _read_device_status(self) -> None:
        """Read current device status."""
        if not self.client or not self.client.is_connected:
            return

        try:
            _LOGGER.debug("  [STATUS] Reading status characteristic...")
            data = await self.client.read_gatt_char(CHAR_DEVICE_STATUS)
            if data:
                _LOGGER.info("  [STATUS] ✓ Read %d bytes: %s", len(data), data.hex())
                self._on_status_notification(None, data)
            else:
                _LOGGER.warning("  [STATUS] ⚠ No data returned from status read")
        except Exception as e:
            _LOGGER.warning("  [STATUS] ⚠ Could not read status: %s", e)

    async def _write_command(self, char_uuid: str, command: bytes, description: str = "") -> bool:
        """Write a command to a characteristic."""
        if not self.client or not self.client.is_connected:
            _LOGGER.error("  [CMD] ✗ Cannot write - not connected!")
            return False

        char_short = char_uuid[-8:]
        cmd_hex = command.hex()

        _LOGGER.info("  [CMD] Writing to %s: %s %s", char_short, cmd_hex, description)

        try:
            # Try write without response first (faster)
            await self.client.write_gatt_char(char_uuid, command, response=False)
            _LOGGER.info("  [CMD] ✓ Write successful (no response)")
            return True
        except Exception as e1:
            _LOGGER.debug("  [CMD] Write without response failed: %s", e1)
            # Fall back to write with response
            try:
                await self.client.write_gatt_char(char_uuid, command, response=True)
                _LOGGER.info("  [CMD] ✓ Write successful (with response)")
                return True
            except Exception as e2:
                _LOGGER.error("  [CMD] ✗ Write FAILED!")
                _LOGGER.error("  [CMD]   Error 1: %s", e1)
                _LOGGER.error("  [CMD]   Error 2: %s", e2)
                return False

    async def set_fan_state(self, turn_on: bool) -> bool:
        """Turn fan on or off."""
        action = "ON" if turn_on else "OFF"

        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )
        _LOGGER.info("  [FAN] Turn %s requested", action)
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )

        async with self._lock:
            # Connect if not connected
            _LOGGER.info("  [FAN] Step 1: Ensuring connection...")
            if not await self.async_connect():
                _LOGGER.error("  [FAN] ✗ FAILED: Could not connect to device")
                return False

            command = FAN_CMD_ON if turn_on else FAN_CMD_OFF
            alt_command = FAN_CMD_ON_ALT if turn_on else FAN_CMD_OFF_ALT

            _LOGGER.info("  [FAN] Step 2: Sending %s command...", action)
            _LOGGER.info("  [FAN]   Primary command: %s", command.hex())

            # Try simple command first
            success = await self._write_command(
                CHAR_FAN_CONTROL,
                command,
                f"(Fan {action})"
            )

            if not success:
                _LOGGER.info("  [FAN] Step 2b: Trying alternative command format...")
                _LOGGER.info("  [FAN]   Alternative command: %s", alt_command.hex())
                success = await self._write_command(
                    CHAR_FAN_CONTROL,
                    alt_command,
                    f"(Fan {action} ALT)"
                )

            if success:
                self.data["fan_on"] = turn_on
                _LOGGER.info("  [FAN] Step 3: Resetting disconnect timer...")
                self._schedule_disconnect()

                # Read status to verify
                _LOGGER.info("  [FAN] Step 4: Verifying state change...")
                await asyncio.sleep(0.5)
                await self._read_device_status()

                _LOGGER.info(
                    "═══════════════════════════════════════════════════════════════"
                )
                _LOGGER.info("  [FAN] ✓ Fan %s command completed successfully", action)
                _LOGGER.info(
                    "═══════════════════════════════════════════════════════════════"
                )
            else:
                _LOGGER.error(
                    "═══════════════════════════════════════════════════════════════"
                )
                _LOGGER.error("  [FAN] ✗ Fan %s command FAILED", action)
                _LOGGER.error(
                    "═══════════════════════════════════════════════════════════════"
                )

            return success

    async def set_light_state(self, turn_on: bool) -> bool:
        """Turn light on or off."""
        action = "ON" if turn_on else "OFF"

        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )
        _LOGGER.info("  [LIGHT] Turn %s requested", action)
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )

        async with self._lock:
            # Connect if not connected
            _LOGGER.info("  [LIGHT] Step 1: Ensuring connection...")
            if not await self.async_connect():
                _LOGGER.error("  [LIGHT] ✗ FAILED: Could not connect to device")
                return False

            command = LIGHT_CMD_ON if turn_on else LIGHT_CMD_OFF
            alt_command = LIGHT_CMD_ON_ALT if turn_on else LIGHT_CMD_OFF_ALT

            _LOGGER.info("  [LIGHT] Step 2: Sending %s command...", action)
            _LOGGER.info("  [LIGHT]   Primary command: %s", command.hex())

            # Try simple command first
            success = await self._write_command(
                CHAR_LIGHT_CONTROL,
                command,
                f"(Light {action})"
            )

            if not success:
                _LOGGER.info("  [LIGHT] Step 2b: Trying alternative command format...")
                _LOGGER.info("  [LIGHT]   Alternative command: %s", alt_command.hex())
                success = await self._write_command(
                    CHAR_LIGHT_CONTROL,
                    alt_command,
                    f"(Light {action} ALT)"
                )

            if success:
                self.data["light_on"] = turn_on
                _LOGGER.info("  [LIGHT] Step 3: Resetting disconnect timer...")
                self._schedule_disconnect()

                # Read status to verify
                _LOGGER.info("  [LIGHT] Step 4: Verifying state change...")
                await asyncio.sleep(0.5)
                await self._read_device_status()

                _LOGGER.info(
                    "═══════════════════════════════════════════════════════════════"
                )
                _LOGGER.info("  [LIGHT] ✓ Light %s command completed successfully", action)
                _LOGGER.info(
                    "═══════════════════════════════════════════════════════════════"
                )
            else:
                _LOGGER.error(
                    "═══════════════════════════════════════════════════════════════"
                )
                _LOGGER.error("  [LIGHT] ✗ Light %s command FAILED", action)
                _LOGGER.error(
                    "═══════════════════════════════════════════════════════════════"
                )

            return success

    async def set_light_color(self, rgb: tuple[int, int, int]) -> bool:
        """Set light color."""
        r, g, b = rgb

        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )
        _LOGGER.info("  [COLOR] Set RGB(%d, %d, %d) requested", r, g, b)
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )

        async with self._lock:
            _LOGGER.info("  [COLOR] Step 1: Ensuring connection...")
            if not await self.async_connect():
                _LOGGER.error("  [COLOR] ✗ FAILED: Could not connect to device")
                return False

            if r == 0 and g == 0 and b == 0:
                command = COLOR_CMD_OFF
                _LOGGER.info("  [COLOR] Step 2: Sending color OFF command...")
            else:
                # Format: 80 25 RR GG BB 00
                command = bytes([0x80, 0x25, r, g, b, 0x00])
                _LOGGER.info("  [COLOR] Step 2: Sending color command...")

            _LOGGER.info("  [COLOR]   Command: %s", command.hex())

            success = await self._write_command(
                CHAR_COLOR_CONTROL,
                command,
                f"(RGB {r},{g},{b})"
            )

            if success:
                self.data["rgb_color"] = rgb
                self._schedule_disconnect()
                _LOGGER.info(
                    "═══════════════════════════════════════════════════════════════"
                )
                _LOGGER.info("  [COLOR] ✓ Color command completed successfully")
                _LOGGER.info(
                    "═══════════════════════════════════════════════════════════════"
                )
            else:
                _LOGGER.error(
                    "═══════════════════════════════════════════════════════════════"
                )
                _LOGGER.error("  [COLOR] ✗ Color command FAILED")
                _LOGGER.error(
                    "═══════════════════════════════════════════════════════════════"
                )

            return success

    async def set_light_brightness(self, brightness: int) -> bool:
        """Set light brightness (0-255)."""
        _LOGGER.info("  [BRIGHTNESS] Set brightness to %d requested", brightness)
        _LOGGER.warning("  [BRIGHTNESS] ⚠ Brightness control not yet implemented")
        self.data["brightness"] = brightness
        return True
