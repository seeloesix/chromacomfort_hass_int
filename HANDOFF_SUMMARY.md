# ChromaComfort Integration - Handoff Summary

## Project Overview
Home Assistant custom integration for ChromaComfort Multi-Color LED Ventilation Fans via Bluetooth Low Energy (BLE).

## Current Status
- ✅ **Basic Integration Working**: Fan and light control entities
- ✅ **Bluetooth Discovery Fixed**: Now detects by manufacturer ID instead of device name
- ✅ **Repository Renamed**: From chromafi to chromacomfort
- ✅ **Custom Device Names**: Users can set custom names during setup
- ✅ **Room Assignment**: Optional room/area selection during configuration
- ⚠️ **Partial Control**: ON/OFF works, advanced features in development

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

### Device Setup Process
1. **Discovery**: Detects devices by manufacturer ID 10 (GooWi Technology)
2. **Selection**: Choose from list of discovered ChromaComfort fans
3. **Customization** (NEW):
   - Set custom device name (default: "ChromaComfort Fan")
   - Select room/area (optional, integrates with HA areas)
4. **Completion**: Creates device with custom name in specified room

### Config Entry Data
- `address`: BLE MAC address
- `name`: Custom device name
- `room`: Selected room/area ID

## Known Issues & Limitations

### Current Limitations
1. **Fan Speed**: Only ON/OFF (no speed control yet)
2. **RGB Colors**: Framework in place but needs command refinement
3. **Brightness**: Not yet implemented
4. **iOS App Conflict**: Cannot use simultaneously with HA

### Common Problems
1. **Fan Not Found**: Usually due to:
   - iOS app connected (disconnect it)
   - Fan out of range (stay within 30 feet)
   - Bluetooth not enabled in HA

2. **Connection Drops**: BLE connections can be unstable
   - Integration has retry logic
   - May need manual reconnection

## Development Roadmap

### Next Steps
1. **Multi-speed fan control** (Low/Medium/High)
2. **RGB color implementation** (needs command format analysis)
3. **Brightness control** (0-100%)
4. **Scene support** (preset colors/modes)

### Testing Needed
1. Test with multiple fans simultaneously
2. Verify manufacturer ID is consistent across all units
3. Capture more BLE traffic for advanced features
4. Test stability over extended periods

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

---
Last Updated: 2025-08-27
Integration Version: 0.1.0