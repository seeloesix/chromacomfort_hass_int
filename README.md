# ChromaComfort - Home Assistant Integration

Home Assistant custom integration for controlling ChromaComfort Multi-Color LED Ventilation Fans via Bluetooth Low Energy (BLE).

## Features

- **Bluetooth Discovery**: Auto-detects ChromaComfort fans by manufacturer ID
- **On-Demand Connection**: Connects when you control the device, disconnects when idle
- **iOS App Compatible**: Doesn't monopolize the device - switch between HA and iPhone app
- **Fan Control**: Turn fan on/off
- **Light Control**: Turn light on/off with RGB color support
- **Auto-Disconnect**: Frees device after 10 seconds of inactivity
- **Always Available**: Entities stay responsive even when disconnected

## Supported Devices

- **ChromaComfort Multi-Color LED Ventilation Fan**
  - Manufacturer: GooWi Technology Co., Ltd.
  - Manufacturer ID: 10 (0x0A)
  - Default Pairing PIN: **1234**
  - Connection: Bluetooth Low Energy (BLE)
  - Service UUID: a08f7710-c37c-11e3-99cc-0228ac012a70

## How It Works

This integration mirrors the iOS app workflow:

1. **Scan** - Discovers ChromaComfort devices via Bluetooth
2. **Select** - User picks their fan from the list
3. **Configure** - Name the device and assign a room
4. **Connect** - On first command, pairs using PIN 1234
5. **Control** - Send commands (fan on/off, light on/off)
6. **Disconnect** - Automatically disconnects after 10 seconds of inactivity

## Prerequisites

- Home Assistant with Bluetooth support
- ChromaComfort fan powered on and within BLE range (~30 feet)
- Fan not currently connected to iOS app (only one connection at a time)

## Installation

### Method 1: HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed
2. Go to **HACS** → **Integrations**
3. Click **⋮** → **Custom repositories**
4. Add: `https://github.com/seeloesix/chromacomfort`
5. Category: **Integration**
6. Install **ChromaComfort**
7. Restart Home Assistant

### Method 2: Manual Installation

```bash
# For Home Assistant OS/Container
mkdir -p /config/custom_components
cd /tmp
wget https://github.com/seeloesix/chromacomfort/archive/main.zip
unzip main.zip
cp -r chromacomfort-main/custom_components/chromacomfort /config/custom_components/

# Restart Home Assistant via UI: Settings → System → Restart
```

## Setup

1. **Restart Home Assistant** after installation
2. Go to **Settings** → **Devices & Services**
3. Click **+ ADD INTEGRATION**
4. Search for **"ChromaComfort"**
5. Select your fan from the discovered devices
6. Name the device and assign a room
7. Done! The device will pair automatically (PIN 1234) on first use

## Usage

After setup, you'll have two entities:
- `fan.<device_name>_fan` - Fan control
- `light.<device_name>_light` - Light control

### Dashboard Card

```yaml
type: entities
title: Bathroom Fan
entities:
  - entity: fan.bathroom_fan
  - entity: light.bathroom_light
```

### Service Calls

```yaml
# Turn fan on
service: fan.turn_on
target:
  entity_id: fan.bathroom_fan

# Turn fan off
service: fan.turn_off
target:
  entity_id: fan.bathroom_fan

# Turn light on with color
service: light.turn_on
target:
  entity_id: light.bathroom_light
data:
  rgb_color: [255, 0, 0]  # Red
```

### Automation Example

```yaml
automation:
  - alias: "Turn on fan when humid"
    trigger:
      - platform: numeric_state
        entity_id: sensor.bathroom_humidity
        above: 70
    action:
      - service: fan.turn_on
        target:
          entity_id: fan.bathroom_fan
```

## Troubleshooting

### Fan Not Discovered

- Ensure fan is powered on
- Close the iOS ChromaComfort app (disconnect from fan)
- Check fan is within Bluetooth range (~30 feet)
- Restart Home Assistant and try again

### Connection Fails

- Only one device can connect at a time
- Disconnect iOS app before using Home Assistant
- Wait a few seconds after disconnecting iOS app
- The PIN code is always **1234**

### Commands Don't Work

- Check Home Assistant logs for errors
- Enable debug logging (see below)
- Ensure you're controlling the correct device

### Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.chromacomfort: debug
```

## Architecture

```
┌─────────────────────────────────────────┐
│           Home Assistant                │
├─────────────────────────────────────────┤
│  Fan Entity          Light Entity       │
│  (fan.py)            (light.py)         │
└──────────────┬───────────────┬──────────┘
               │               │
        ┌──────┴───────────────┴──────┐
        │     ChromaComfortCoordinator│
        │     (coordinator.py)        │
        │                             │
        │  • On-demand connection     │
        │  • Auto-disconnect (10s)    │
        │  • Command queueing         │
        │  • Status notifications     │
        └─────────────┬───────────────┘
                      │
              ┌───────┴───────┐
              │   BLE/Bleak   │
              │   PIN: 1234   │
              └───────┬───────┘
                      │
              ┌───────┴───────┐
              │ ChromaComfort │
              │     Fan       │
              └───────────────┘
```

## Current Status

### Working
- Device discovery via Bluetooth
- Configuration flow with custom naming
- Fan on/off control
- Light on/off control
- RGB color support (framework)
- Auto-disconnect after inactivity
- iOS app compatibility

### In Development
- Light brightness control
- Fan speed control (currently single speed)
- Scene/preset support

## Support

- **Issues**: [GitHub Issues](https://github.com/seeloesix/chromacomfort/issues)
- **Community**: [Home Assistant Forums](https://community.home-assistant.io)

## License

MIT License - see [LICENSE](LICENSE) file.

## Disclaimer

This integration is not affiliated with Broan-NuTone or GooWi Technology. Use at your own risk.
