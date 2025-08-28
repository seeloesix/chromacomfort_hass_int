# ChromaComfort Integration - Handoff Summary

## Project Overview
Home Assistant custom integration for ChromaComfort Multi-Color LED Ventilation Fans via Bluetooth Low Energy (BLE).

## Current Status (2025-08-28)
- ✅ **Basic Integration Working**: Fan and light control entities created
- ✅ **Bluetooth Discovery Fixed**: Detects by manufacturer ID 10 (GooWi Technology)
- ✅ **Repository Renamed**: From chromafi to chromacomfort
- ✅ **Single Config Window**: Streamlined setup with device info, name, and room selection
- ✅ **Enhanced Logging**: Comprehensive BLE connection debugging
- ✅ **Error Recovery**: Entities work even if BLE connection fails
- ⚠️ **BLE Connection Issues**: Commands appear to send but device doesn't respond
- ⚠️ **Partial Control**: Framework complete, needs command verification

## Key Technical Details

### Bluetooth Discovery
- **Manufacturer ID**: 10 (0x0A) - GooWi Technology Co., Ltd.
- **Service UUID**: a08f7710-c37c-11e3-99cc-0228ac012a70
- **Device Names**: Variable - may show as "OTA Update", "Chroma-Comfort", etc.
- **Discovery Method**: Uses manufacturer ID for reliable detection (not device name)

### BLE Characteristics (Discovered)
```python
CHAR_FAN_CONTROL = "00001018-d102-11e1-9b23-00025b00a5a5"  # Fan speed control
CHAR_LIGHT_CONTROL = "00001013-d102-11e1-9b23-00025b00a5a5"  # Light on/off control  
CHAR_COLOR_CONTROL = "bb8a27e1-c37c-11e3-b954-0228ac012a70"  # RGB color control
CHAR_DEVICE_STATUS = "00001014-d102-11e1-9b23-00025b00a5a5"  # Device status notifications
```

### Command Patterns (Reverse Engineered)
- **Fan OFF**: `0x00`
- **Fan ON**: `0x01`
- **Light OFF**: `0x00`
- **Light ON**: `0x01`
- **Color OFF**: `0x80 0x25 0x00 0x00 0x00 0x00`

## File Structure
```
chromacomfort/
├── custom_components/chromacomfort/   # Main integration
│   ├── __init__.py                   # Integration setup
│   ├── manifest.json                  # HA integration manifest
│   ├── config_flow.py                 # Device discovery & setup
│   ├── coordinator.py                 # BLE communication coordinator
│   ├── fan.py                         # Fan entity
│   ├── light.py                       # Light entity
│   ├── const.py                       # Constants & BLE commands
│   └── translations/en.json          # UI translations
├── README.md                          # User documentation
├── INSTALLATION.md                    # Installation guide
├── HANDOFF_SUMMARY.md                 # This file
└── hacs.json                          # HACS configuration
```

## Installation Paths

### Home Assistant OS (Most Common)
- Config directory: `/config/`
- Integration path: `/config/custom_components/chromacomfort/`
- No sudo required, restart via UI

### Home Assistant Core
- Config directory: `~/.homeassistant/`
- Integration path: `~/.homeassistant/custom_components/chromacomfort/`

## Configuration Flow

### Device Setup Process (Updated)
1. **Bluetooth Discovery**: Auto-detects by manufacturer ID 10
2. **Single Configuration Window**:
   - Shows device info (Model, Manufacturer, Address)
   - Custom name field (editable)
   - Room/area dropdown (optional, defaults to "No Room")
3. **Device Creation**: Immediate entity creation with selected settings

### Config Entry Data
- `address`: BLE MAC address (e.g., "64:72:D8:CC:47:21")
- `name`: Custom device name (user-defined)
- `room`: Selected room/area ID or "none"

## Known Issues & Limitations

### Critical Issues (2025-08-28)
1. **BLE Commands Not Working**: 
   - Commands send successfully but device doesn't respond
   - Status notifications subscribe OK
   - Possible characteristic UUID mismatch
   - Need to verify actual command format

2. **Fan Entity Issues**:
   - Fixed: FanEntityFeature must return enum not int
   - Fixed: Added sync wrappers for turn_on/turn_off
   - Working: Entity creates and UI responds

### Current Limitations
1. **Fan Speed**: Only ON/OFF (no speed control)
2. **RGB Colors**: Framework complete, commands untested
3. **Brightness**: Not implemented
4. **iOS App Conflict**: Cannot use simultaneously

### Common Problems
1. **Device Not Found**:
   - Ensure manufacturer ID 10 in advertisement
   - Device may show as "OTA Update" or "Chroma-Comfort"
   - Check Bluetooth adapter is enabled

2. **"Skip and Finish" Button**:
   - This is Home Assistant's default device page
   - Cannot be removed (HA limitation)
   - Just a confirmation screen, not configuration

## Development Roadmap

### Immediate Priority
1. **Fix BLE Command Execution**:
   - Verify characteristic UUIDs match device
   - Confirm command format (may need different bytes)
   - Test with direct BLE tools (gatttool/bluetoothctl)
   - Capture traffic from working iOS app

2. **Debug Current Connection**:
   - Log shows successful connection but commands fail
   - Check if write requires response vs write-without-response
   - Verify characteristic properties and permissions

### Next Steps
1. **Multi-speed fan control** (after basic commands work)
2. **RGB color implementation** (needs protocol analysis)
3. **Brightness control** (0-100%)
4. **Scene support** (preset colors/modes)

### Testing Needed
1. Verify actual characteristic UUIDs on device
2. Capture BLE traffic from working iOS app
3. Test write vs write-without-response
4. Confirm command byte format

## Research & Development Files

### Debugging Scripts
- `test_chromacomfort_discovery.py` - Test discovery on HA
- `simple_ble_scan.py` - Basic BLE scanner
- `debug_bluetooth_discovery.py` - HA Bluetooth debug
- `safe_ha_bluetooth_test.py` - Template for HA Developer Tools
- `bluetooth_debug_sensor.yaml` - Debug sensors for configuration.yaml

### Reverse Engineering Notes
- Manufacturer data format: `10 0x64 [MAC address bytes]`
- Status byte interpretation documented in const.py
- Color commands need more testing for RGB mapping

## GitHub Repository
- **URL**: https://github.com/seeloesix/chromacomfort
- **Issues**: Report bugs and feature requests
- **HACS Compatible**: Can be installed via HACS custom repository

## Support Contacts
- **Developer**: @seeloesix
- **Home Assistant Community**: Post in custom components forum
- **GitHub Issues**: Primary support channel

## Quick Test Commands

### Check if fan is detected (in HA Terminal):
```bash
# List all Bluetooth devices
bluetoothctl devices

# Check for manufacturer ID 10
# In Developer Tools > Template:
{{ integration_entities("bluetooth") | selectattr("manufacturer_id", "eq", 10) | list }}
```

### Manual Installation (Home Assistant OS):
```bash
cd /config
wget https://github.com/seeloesix/chromacomfort/archive/main.zip
unzip main.zip
cp -r chromacomfort-main/custom_components/chromacomfort /config/custom_components/
# Restart HA from UI
```

## Notes for Next Developer
1. The integration uses manufacturer ID for detection, not device names
2. BLE connection code is in coordinator.py - uses bleak library
3. Status notifications are partially decoded (see _handle_status_notification)
4. Color commands need reverse engineering for full RGB support
5. Consider implementing a service for raw BLE commands for testing

## Recent Fixes (2025-08-28)

### Configuration Flow
- Consolidated to single window with device info display
- Fixed FanEntityFeature type error (must be enum not int)
- Added comprehensive BLE logging with prefixes ([BLE], [FAN], [LIGHT], etc.)
- Fixed BleakGATTServiceCollection len() error

### Entity Improvements
- Added sync wrappers for fan turn_on/turn_off compatibility
- Entities stay available even if BLE disconnects
- Better error handling to prevent UI freezing

### Logging Enhancements
- Step-by-step BLE connection tracking
- Service/characteristic discovery logging
- Command verification before sending
- Hex command values shown in debug logs

---
Last Updated: 2025-08-28
Integration Version: 0.1.0
Python: 3.11+
Home Assistant: 2023.1.0+