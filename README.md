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
  - Model: Chroma-Comfort
  - Connection: Bluetooth Low Energy (BLE)

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
```bash
# SSH to your Home Assistant device
ssh homeassistant@YOUR_HA_IP

# Create custom components directory
sudo mkdir -p /home/homeassistant/.homeassistant/custom_components

# Download and extract integration
cd /tmp
git clone https://github.com/seeloesix/chromacomfort.git
sudo cp -r chromacomfort/custom_components/chromacomfort /home/homeassistant/.homeassistant/custom_components/

# Set correct permissions
sudo chown -R homeassistant:homeassistant /home/homeassistant/.homeassistant/custom_components/chromacomfort

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
- Verify files exist: `/home/homeassistant/.homeassistant/custom_components/chromacomfort/`
- Check file permissions: `sudo chown -R homeassistant:homeassistant /home/homeassistant/.homeassistant/custom_components/`
- Restart Home Assistant: `sudo systemctl restart home-assistant@homeassistant.service`

### Fan Not Discovered
- Ensure fan is powered on and within BLE range
- Check Bluetooth service: `sudo systemctl status bluetooth`
- Test BLE scan: `sudo hcitool lescan | grep -i chroma`
- Only one device can connect at a time (disconnect iOS app if connected)

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