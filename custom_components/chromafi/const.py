"""Constants for the ChromaFi integration."""
from typing import Final

DOMAIN: Final = "chromafi"

# Device info (discovered from reverse engineering)
MANUFACTURER: Final = "GooWi Technology Co., Ltd."
MODEL: Final = "ChromaComfort Multi-Color LED Ventilation Fan"

# Bluetooth characteristics (discovered from ChromaComfort fan)
CHAR_FAN_CONTROL: Final = "00001018-d102-11e1-9b23-00025b00a5a5"  # Fan speed control
CHAR_LIGHT_CONTROL: Final = "00001013-d102-11e1-9b23-00025b00a5a5"  # Light on/off control  
CHAR_COLOR_CONTROL: Final = "bb8a27e1-c37c-11e3-b954-0228ac012a70"  # RGB color control
CHAR_DEVICE_STATUS: Final = "00001014-d102-11e1-9b23-00025b00a5a5"  # Device status notifications

# Discovered BLE Command Patterns (from GATT capture analysis)

# Fan Control Commands (write to CHAR_FAN_CONTROL)
FAN_CMD_OFF: Final = bytes([0x00])  # Fan OFF command
FAN_CMD_ON: Final = bytes([0x01])   # Fan ON command (basic speed)

# Light Control Commands (write to CHAR_LIGHT_CONTROL) 
LIGHT_CMD_OFF: Final = bytes([0x00])  # Light OFF
LIGHT_CMD_ON: Final = bytes([0x01])   # Light ON (white)

# Color Control Commands (write to CHAR_COLOR_CONTROL - 6 bytes)
COLOR_CMD_OFF: Final = bytes([0x80, 0x25, 0x00, 0x00, 0x00, 0x00])  # Color OFF (initial state)

# Status byte interpretation (from status notifications)
# Byte 5 (0-indexed): Always 0x41 (base state)
# Byte 6 (0-indexed): Control state flags
#   0x00 = Fan OFF, Light OFF  
#   0x20 = Light ON (various dimmer levels)
#   0x40 = Light ON (different mode)
#   0x80 = Fan ON
#   0xA0 = Fan ON + Light ON
#   0xC0 = Fan ON + Light ON (different mode)

# Fan speeds (to be refined with more testing)
FAN_SPEED_OFF: Final = 0
FAN_SPEED_LOW: Final = 1  
FAN_SPEED_MEDIUM: Final = 2
FAN_SPEED_HIGH: Final = 3

# Update interval (seconds)
UPDATE_INTERVAL: Final = 30