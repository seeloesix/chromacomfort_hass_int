#!/usr/bin/env python3
"""
Debug script to test Home Assistant Bluetooth device discovery.
This can be used to see what devices HA is discovering without going through the config flow.
"""

import asyncio
import logging
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.core import HomeAssistant

# Setup logging
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

async def debug_bluetooth_discovery(hass: HomeAssistant):
    """Debug function to list all discovered Bluetooth devices."""
    _LOGGER.info("=== ChromaComfort Bluetooth Discovery Debug ===")
    
    # Get all discovered devices
    all_discovered = list(async_discovered_service_info(hass, False))
    _LOGGER.info("Total discovered Bluetooth devices: %d", len(all_discovered))
    
    # Log all device details
    chromacomfort_devices = []
    for i, discovery_info in enumerate(all_discovered):
        device_name = discovery_info.name or "(No Name)"
        _LOGGER.info("Device %d: Name='%s', Address='%s', RSSI=%s", 
                    i + 1, device_name, discovery_info.address, 
                    getattr(discovery_info, 'rssi', 'N/A'))
        
        # Check for ChromaComfort matches
        if device_name and ("ChromaComfort" in device_name or "Chroma-Comfort" in device_name):
            chromacomfort_devices.append(discovery_info)
            _LOGGER.info("*** FOUND CHROMACOMFORT DEVICE: '%s' (%s) ***", 
                        device_name, discovery_info.address)
    
    _LOGGER.info("=== Summary ===")
    _LOGGER.info("Total devices: %d", len(all_discovered))
    _LOGGER.info("ChromaComfort devices: %d", len(chromacomfort_devices))
    
    if chromacomfort_devices:
        _LOGGER.info("ChromaComfort devices found:")
        for device in chromacomfort_devices:
            _LOGGER.info("  - '%s' (%s)", device.name, device.address)
    else:
        _LOGGER.warning("No ChromaComfort devices found!")
    
    return chromacomfort_devices

# This function can be called from the Home Assistant developer tools
# or imported and used for debugging
if __name__ == "__main__":
    print("This is a debug module for Home Assistant Bluetooth discovery.")
    print("Import this in Home Assistant and call debug_bluetooth_discovery(hass)")