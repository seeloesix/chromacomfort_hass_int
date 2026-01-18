"""Constants for the ChromaComfort integration."""
from typing import Final

DOMAIN: Final = "chromacomfort"

# Device info (discovered from reverse engineering)
MANUFACTURER: Final = "GooWi Technology Co., Ltd."
MODEL: Final = "ChromaComfort Multi-Color LED Ventilation Fan"

# BLE Pairing Configuration
DEFAULT_PIN_CODE: Final = "1234"  # Default Bluetooth pairing PIN for ChromaComfort devices
PAIRING_TIMEOUT: Final = 30  # Seconds to wait for pairing to complete
CONNECTION_TIMEOUT: Final = 15  # Seconds to wait for BLE connection

# Bluetooth characteristics (discovered from ChromaComfort fan)
CHAR_FAN_CONTROL: Final = "00001018-d102-11e1-9b23-00025b00a5a5"  # Fan speed control
CHAR_LIGHT_CONTROL: Final = "00001013-d102-11e1-9b23-00025b00a5a5"  # Light on/off control  
CHAR_COLOR_CONTROL: Final = "bb8a27e1-c37c-11e3-b954-0228ac012a70"  # RGB color control
CHAR_DEVICE_STATUS: Final = "00001014-d102-11e1-9b23-00025b00a5a5"  # Device status notifications

# Discovered BLE Command Patterns (from GATT capture analysis)
# Based on reverse engineering from CHROMAFI_COMMANDS_DISCOVERED.md

# Fan Control Commands (write to CHAR_FAN_CONTROL)
# Simple single-byte commands confirmed from GATT analysis
FAN_CMD_OFF: Final = bytes([0x00])  # Turn fan off
FAN_CMD_ON: Final = bytes([0x01])   # Turn fan on

# Alternative fan commands to try if simple bytes don't work
FAN_CMD_OFF_ALT: Final = bytes([0xAA, 0x01, 0x00, 0xBB])  # UART format fallback
FAN_CMD_ON_ALT: Final = bytes([0xAA, 0x01, 0x01, 0xBB])   # UART format fallback

# Light Control Commands (write to CHAR_LIGHT_CONTROL)
# Simple single-byte commands confirmed from GATT analysis
LIGHT_CMD_OFF: Final = bytes([0x00])  # Turn light off
LIGHT_CMD_ON: Final = bytes([0x01])   # Turn light on (white)

# Alternative light commands to try if simple bytes don't work
LIGHT_CMD_OFF_ALT: Final = bytes([0xAA, 0x02, 0x00, 0xBB])  # UART format fallback
LIGHT_CMD_ON_ALT: Final = bytes([0xAA, 0x02, 0x01, 0xBB])   # UART format fallback

# Color Control Commands (write to CHAR_COLOR_CONTROL - 6 bytes)
# Format discovered: 80 25 XX XX XX XX (color mode)
COLOR_CMD_OFF: Final = bytes([0x80, 0x25, 0x00, 0x00, 0x00, 0x00])  # Color mode off

# Color presets (need verification)
COLOR_CMD_RED: Final = bytes([0x80, 0x25, 0xFF, 0x00, 0x00, 0x00])
COLOR_CMD_GREEN: Final = bytes([0x80, 0x25, 0x00, 0xFF, 0x00, 0x00])
COLOR_CMD_BLUE: Final = bytes([0x80, 0x25, 0x00, 0x00, 0xFF, 0x00])
COLOR_CMD_WHITE: Final = bytes([0x80, 0x25, 0xFF, 0xFF, 0xFF, 0x00])

# Status-based Authentication Constants
STATUS_AUTH_ENABLED: Final = True  # Enable status-based authentication
STATUS_BYTES_LENGTH: Final = 4     # Number of status bytes to prepend

# Status byte interpretation (from status notifications)
# Byte 5 (0-indexed): Always 0x41 (base state)
# Byte 6 (0-indexed): Control state flags
#   0x00 = Fan OFF, Light OFF  
#   0x20 = Light ON (various dimmer levels)
#   0x40 = Light ON (different mode)
#   0x80 = Fan ON
#   0xA0 = Fan ON + Light ON
#   0xC0 = Fan ON + Light ON (different mode)

# Fan is single speed only (on/off)
# No speed constants needed

# Update interval (seconds)
UPDATE_INTERVAL: Final = 30