# ChromaComfort - Home Assistant Integration

Home Assistant custom integration for controlling ChromaComfort Multi-Color LED Ventilation Fans via Bluetooth Low Energy (BLE).

## Features

- ✅ **Fan Control**: Turn fan ON/OFF via Home Assistant
- ✅ **Light Control**: Control built-in LED light ON/OFF
- ✅ **Real-time Status**: Automatic state updates in Home Assistant
- ✅ **Multi-device Support**: Control multiple ChromaComfort fans
- ✅ **BLE Connection Management**: Automatic reconnection handling

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

### Commands Not Working
- Check Home Assistant logs: `sudo journalctl -u home-assistant@homeassistant.service -f | grep -i chromacomfort`
- Verify fan is within 30 feet of Home Assistant device
- Restart integration: **Settings** → **Devices & Services** → **ChromaComfort** → **⋮** → **Reload**

### Connection Issues
- Only one device can connect to the fan at a time
- If using iOS app, disconnect it before using Home Assistant
- BLE connections may take a few seconds to establish

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

## Current Limitations

- **Fan Speed Control**: Currently ON/OFF only (multi-speed support planned)
- **Color Control**: Basic framework implemented (RGB control in development)
- **Light Dimming**: Pattern identified (brightness control in development)
- **iOS App Compatibility**: Cannot use simultaneously with Home Assistant

## Development Roadmap

- 🔄 **Multi-speed Fan Control**: Low/Medium/High speed settings
- 🔄 **RGB Color Control**: Full color wheel support
- 🔄 **Light Dimming**: Brightness control (0-100%)
- 🔄 **Timer Functions**: Scheduled ON/OFF functionality
- 🔄 **Scene Support**: Predefined color/brightness scenes

## Support

- **GitHub Issues**: [https://github.com/seeloesix/chromacomfort/issues](https://github.com/seeloesix/chromacomfort/issues)
- **Home Assistant Community**: [https://community.home-assistant.io](https://community.home-assistant.io)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with Broan-NuTone or GooWi Technology Co., Ltd. Use at your own risk. Always ensure you're controlling your own devices and not interfering with others' Bluetooth devices.