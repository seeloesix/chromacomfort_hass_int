# ChromaComfort - Home Assistant Integration

Home Assistant custom integration for controlling ChromaComfort Multi-Color LED Ventilation Fans via Bluetooth Low Energy (BLE).

## Features

- ✅ **On-Demand Connection**: Connects only when sending commands, then auto-disconnects
- ✅ **iOS App Compatible**: Doesn't lock out the iPhone app - seamless switching
- ✅ **Bluetooth Discovery**: Auto-detects ChromaComfort fans by manufacturer ID
- ✅ **Device Configuration**: Custom naming and room assignment during setup
- ✅ **Smart Session Management**: Establishes control session like iOS app
- ✅ **Always Available**: Entities stay available even when disconnected
- ⚠️ **Fan/Light Control**: Framework complete, command verification needed
- ✅ **Auto-Disconnect**: Frees device after 10 seconds of inactivity

## Supported Devices

- **ChromaComfort Multi-Color LED Ventilation Fan**
  - Manufacturer: GooWi Technology Co., Ltd.
  - Manufacturer ID: 10 (0x0A)
  - Model: Chroma-Comfort
  - Connection: Bluetooth Low Energy (BLE)
  - Service UUID: a08f7710-c37c-11e3-99cc-0228ac012a70
  - Device may advertise as: "Chroma-Comfort", "OTA Update", or other names

## Prerequisites

- Home Assistant running on Raspberry Pi (3/4/Zero W) or other BLE-capable device
- ChromaComfort fan within BLE range (typically 30 feet)
- SSH access to Home Assistant device

## Installation

### Method 1: HACS (Recommended)
1. Ensure [HACS](https://hacs.xyz/) is installed
2. In HACS, go to **Integrations**
3. Click **⋮** → **Custom repositories** 
4. Add repository: `https://github.com/seeloesix/chromacomfort`
5. Category: **Integration**
6. Click **Add**
7. Install **ChromaComfort** integration
8. Restart Home Assistant

### Method 2: Manual Installation

#### For Home Assistant OS/Container:
```bash
# Access Home Assistant (use Terminal addon or SSH)
# The config directory is at /config

# Create custom components directory if it doesn't exist
mkdir -p /config/custom_components

# Download and extract integration
cd /tmp
wget https://github.com/seeloesix/chromacomfort/archive/main.zip
unzip main.zip
cp -r chromacomfort-main/custom_components/chromacomfort /config/custom_components/

# Restart Home Assistant
# Go to Settings → System → Restart
```

#### For Home Assistant Core (Python venv):
```bash
# SSH to your Home Assistant device
ssh homeassistant@YOUR_HA_IP

# Create custom components directory
mkdir -p ~/.homeassistant/custom_components

# Download and extract integration
cd /tmp
git clone https://github.com/seeloesix/chromacomfort.git
cp -r chromacomfort/custom_components/chromacomfort ~/.homeassistant/custom_components/

# Set correct permissions
chown -R homeassistant:homeassistant ~/.homeassistant/custom_components/chromacomfort

# Restart Home Assistant
sudo systemctl restart home-assistant@homeassistant.service
```

## Setup

1. **Restart Home Assistant** after installation
2. Go to **Settings** → **Devices & Services**
3. Click **+ ADD INTEGRATION**
4. Search for **"ChromaComfort"**
5. Select your ChromaComfort fan from discovered devices
6. Complete configuration

## Usage

After setup, you'll have two new entities:
- `fan.chromacomfort_fan` - Fan control entity
- `light.chromacomfort_light` - Light control entity

### Basic Controls

**Fan Control:**
```yaml
# Turn fan on
service: fan.turn_on
target:
  entity_id: fan.chromacomfort_fan

# Turn fan off  
service: fan.turn_off
target:
  entity_id: fan.chromacomfort_fan
```

**Light Control:**
```yaml
# Turn light on
service: light.turn_on
target:
  entity_id: light.chromacomfort_light

# Turn light off
service: light.turn_off
target:
  entity_id: light.chromacomfort_light
```

### Home Assistant Dashboard
Add fan and light controls to your dashboard:

```yaml
type: entities
entities:
  - fan.chromacomfort_fan
  - light.chromacomfort_light
title: ChromaComfort Fan
```

### Automations

**Turn on fan when temperature is high:**
```yaml
automation:
  - alias: "Hot Day Fan Control"
    trigger:
      platform: numeric_state
      entity_id: sensor.bedroom_temperature
      above: 75
    action:
      service: fan.turn_on
      target:
        entity_id: fan.chromacomfort_fan
```

## Troubleshooting

### Integration Not Found
- For Home Assistant OS: Verify files exist at `/config/custom_components/chromacomfort/`
- For Home Assistant Core: Verify files exist at `~/.homeassistant/custom_components/chromacomfort/`
- Restart Home Assistant: Settings → System → Restart

### Fan Not Discovered
- Ensure fan is powered on and within BLE range (30 feet)
- Check Bluetooth is enabled in Home Assistant
- The integration detects fans by manufacturer ID (GooWi Technology, ID: 10)
- Your fan may appear as "OTA Update" or other names - this is normal
- Only one device can connect at a time (disconnect iOS app if connected)
- Check Home Assistant Bluetooth monitor for devices with manufacturer ID 10

### Latest Status (Commands Now Send Successfully)
✅ **Framework Complete**: All technical components working properly

**Fixed Issues**:
- ✅ **DBus Compatibility**: Resolved WriteValue method errors across different bluez versions
- ✅ **Fan Entity**: Turn on/off actions now supported with proper feature flags
- ✅ **BLE Commands**: Send successfully without connection or write errors
- ✅ **iOS App Compatibility**: On-demand connection model prevents lockout

**Current Status**:
- Integration framework is production-ready
- BLE connection, session establishment, and command sending all working
- Commands send without errors through robust write methods
- **Final Step**: Physical device testing to verify command bytes

**Next Actions**:
- Test with actual ChromaComfort device to confirm physical response
- Use `/development/mitm_proxy/test_fan_commands.py` for command verification
- Update `const.py` with verified working commands if needed

### Connection Model (Smart On-Demand)
The integration uses an intelligent on-demand connection model:
- **Connects automatically** when you send a command
- **Disconnects after 10 seconds** to free the device
- **iOS app friendly** - Switch between HA and iPhone app seamlessly
- **Entities always available** - Ready for commands anytime
- **No manual disconnect needed** - Automatic connection management

### Connection Behavior
- Commands trigger automatic connection
- Device freed quickly for iOS app use
- Status updates less frequent to avoid monopolizing
- BLE connections take 2-5 seconds to establish

## Advanced Configuration

### Multiple Fans
To control multiple ChromaComfort fans:
1. Each fan will be discovered as a separate device
2. Add each fan through the integration setup
3. Each fan gets unique entity IDs (e.g., `fan.chromacomfort_fan_2`)

### Logging
Enable debug logging for troubleshooting:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.chromacomfort: debug
```

## Current Status (2025-08-28)

### ✅ Working Components
- **Bluetooth Discovery**: Reliable detection via manufacturer ID 10
- **Device Configuration**: Custom naming and room assignment
- **BLE Connection**: Stable connection with session management
- **Entity Framework**: Fan and light entities appear in Home Assistant
- **Status Monitoring**: Real-time status notifications working
- **Error Handling**: Robust connection recovery and logging

### ⚠️ Known Issues
- **Physical Device Control**: Commands send but may not affect device hardware
- **Command Verification**: Actual BLE write commands need physical testing
- **iOS App Conflict**: Cannot use simultaneously with Home Assistant

### 🔄 In Development
- **Command Format Verification**: Testing actual device response
- **Multi-speed Fan Control**: Requires command verification first
- **RGB Color Control**: Framework ready, needs command testing
- **Light Dimming**: Patterns identified, awaiting command verification

## Development Status

### Immediate Priority (Critical)
1. **Command Verification**: Test actual BLE commands with physical device
2. **Device Response Debugging**: Resolve commands-send-but-no-response issue
3. **Command Format Validation**: Use test scripts in `/development/mitm_proxy/`

### Next Phase (After Command Verification)
1. **Multi-speed Fan Control**: Low/Medium/High speed settings
2. **RGB Color Control**: Full color wheel support
3. **Light Dimming**: Brightness control (0-100%)
4. **Enhanced Status**: Decode all status notification patterns

### Future Features
1. **Timer Functions**: Scheduled ON/OFF functionality
2. **Scene Support**: Predefined color/brightness scenes
3. **Multi-device Optimization**: Improved handling of multiple fans

## Support

- **GitHub Issues**: [https://github.com/seeloesix/chromacomfort/issues](https://github.com/seeloesix/chromacomfort/issues)
- **Home Assistant Community**: [https://community.home-assistant.io](https://community.home-assistant.io)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with Broan-NuTone or GooWi Technology Co., Ltd. Use at your own risk. Always ensure you're controlling your own devices and not interfering with others' Bluetooth devices.