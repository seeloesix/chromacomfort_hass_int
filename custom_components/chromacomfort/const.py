"""Constants for the ChromaComfort integration."""
from typing import Final

DOMAIN: Final = "chromacomfort"

# Device info (discovered from reverse engineering)
MANUFACTURER: Final = "GooWi Technology Co., Ltd."
MODEL: Final = "ChromaComfort Multi-Color LED Ventilation Fan"

# Bluetooth characteristics (discovered from ChromaComfort fan)
CHAR_FAN_CONTROL: Final = "00001018-d102-11e1-9b23-00025b00a5a5"  # Fan speed control
CHAR_LIGHT_CONTROL: Final = "00001013-d102-11e1-9b23-00025b00a5a5"  # Light on/off control  
CHAR_COLOR_CONTROL: Final = "bb8a27e1-c37c-11e3-b954-0228ac012a70"  # RGB color control
CHAR_DEVICE_STATUS: Final = "00001014-d102-11e1-9b23-00025b00a5a5"  # Device status notifications

# Discovered BLE Command Patterns (from GATT capture analysis)

# UART Command Formats (GWLE1010B Module - Primary)
# Format: [Start][Command ID][Data][Checksum/End]
# Based on GWLE1010B datasheet and UART interface analysis

# Fan Control Commands (write to CHAR_FAN_CONTROL)
FAN_CMD_OFF: Final = bytes([0xAA, 0x01, 0x00, 0xBB])  # UART format: Start + Cmd + Data + End
FAN_CMD_ON: Final = bytes([0xAA, 0x01, 0x01, 0xBB])   # UART format: Start + Cmd + Data + End

# Alternative UART formats to test
FAN_CMD_OFF_ALT: Final = bytes([0x55, 0x01, 0x00, 0xAA])  # Alternative start/end bytes
FAN_CMD_ON_ALT: Final = bytes([0x55, 0x01, 0x01, 0xAA])   # Alternative start/end bytes

# Light Control Commands (write to CHAR_LIGHT_CONTROL)
LIGHT_CMD_OFF: Final = bytes([0xAA, 0x02, 0x00, 0xBB])  # Different command ID for light
LIGHT_CMD_ON: Final = bytes([0xAA, 0x02, 0x01, 0xBB])   # Different command ID for light

# Alternative light UART formats
LIGHT_CMD_OFF_ALT: Final = bytes([0x55, 0x02, 0x00, 0xAA])  # Alternative format
LIGHT_CMD_ON_ALT: Final = bytes([0x55, 0x02, 0x01, 0xAA])   # Alternative format

# Color Control Commands (write to CHAR_COLOR_CONTROL - 6 bytes UART format)
COLOR_CMD_OFF: Final = bytes([0xAA, 0x03, 0x00, 0x00, 0x00, 0xBB])  # UART RGB format
COLOR_CMD_RED: Final = bytes([0xAA, 0x03, 0xFF, 0x00, 0x00, 0xBB])  # Red
COLOR_CMD_GREEN: Final = bytes([0xAA, 0x03, 0x00, 0xFF, 0x00, 0xBB])  # Green
COLOR_CMD_BLUE: Final = bytes([0xAA, 0x03, 0x00, 0x00, 0xFF, 0xBB])  # Blue
COLOR_CMD_WHITE: Final = bytes([0xAA, 0x03, 0xFF, 0xFF, 0xFF, 0xBB])  # White

# Alternative Color Commands (4 bytes RGB + Brightness - for testing)
COLOR_CMD_OFF_ALT: Final = bytes([0x00, 0x00, 0x00, 0x00])  # RGB + Brightness off
COLOR_CMD_RED_ALT: Final = bytes([0xFF, 0x00, 0x00, 0xFF])  # Red with max brightness
COLOR_CMD_GREEN_ALT: Final = bytes([0x00, 0xFF, 0x00, 0xFF])  # Green with max brightness
COLOR_CMD_BLUE_ALT: Final = bytes([0x00, 0x00, 0xFF, 0xFF])  # Blue with max brightness
COLOR_CMD_WHITE_ALT: Final = bytes([0xFF, 0xFF, 0xFF, 0xFF])  # White with max brightness

# Legacy Raw Commands (Fallback - for testing compatibility)
FAN_CMD_OFF_RAW: Final = bytes([0x00])  # Original raw format
FAN_CMD_ON_RAW: Final = bytes([0x01])   # Original raw format
LIGHT_CMD_OFF_RAW: Final = bytes([0x00])  # Original raw format
LIGHT_CMD_ON_RAW: Final = bytes([0x01])   # Original raw format

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