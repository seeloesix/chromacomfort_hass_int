# ChromaComfort Installation Guide

## Quick Installation

### Option 1: HACS (Recommended)
1. Install [HACS](https://hacs.xyz/) if not already installed
2. In HACS: **Integrations** → **⋮** → **Custom repositories**
3. Add: `https://github.com/seeloesix/chromacomfort` (Category: Integration)
4. Install **ChromaComfort**
5. Restart Home Assistant
6. Add integration: **Settings** → **Devices & Services** → **+ ADD INTEGRATION** → **ChromaComfort**

### Option 2: Manual Installation

#### For Home Assistant OS:
```bash
# Use Terminal addon or SSH addon to access Home Assistant
# The config directory is at /config

# Download integration
cd /tmp
wget https://github.com/seeloesix/chromacomfort/archive/main.zip
unzip main.zip

# Install to Home Assistant
cp -r chromacomfort-main/custom_components/chromacomfort /config/custom_components/

# Restart Home Assistant from UI
# Settings → System → Restart
```

#### For Home Assistant Core:
```bash
# SSH to Home Assistant device
ssh homeassistant@YOUR_HA_IP

# Download integration
cd /tmp
git clone https://github.com/seeloesix/chromacomfort.git

# Install to Home Assistant
cp -r chromacomfort/custom_components/chromacomfort ~/.homeassistant/custom_components/

# Restart Home Assistant
sudo systemctl restart home-assistant@homeassistant.service
```

## Setup ChromaComfort Fan

1. **Power on your ChromaComfort fan**
2. **Ensure it's within BLE range** (30 feet) of Home Assistant device
3. **Disconnect iOS app** if currently connected (only one connection allowed)
4. **Add integration**:
   - **Settings** → **Devices & Services** → **+ ADD INTEGRATION**
   - Search **"ChromaComfort"**
   - Select your fan from discovered devices
   - Complete setup

## Verification

After setup, check for these entities:
- `fan.chromacomfort_fan` - Fan control
- `light.chromacomfort_light` - Light control

Test basic functionality:
```yaml
# In Developer Tools → Services
service: fan.turn_on
target:
  entity_id: fan.chromacomfort_fan
```

## Troubleshooting

### Fan Not Found
- Verify fan is powered and within range
- Disconnect iOS app from fan
- Check Bluetooth: `sudo systemctl status bluetooth`

### Integration Errors  
- Check logs: **Settings** → **System** → **Logs**
- Look for "chromacomfort" entries
- Restart integration if needed

### Connection Issues
- Only one device can connect at a time
- BLE connections may take 5-10 seconds
- Keep fan within 30 feet of Home Assistant

## Support

For issues: [GitHub Issues](https://github.com/seeloesix/chromacomfort/issues)