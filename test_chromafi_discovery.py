#!/usr/bin/env python3
"""
ChromaFi Discovery Test Script for Home Assistant SSH Terminal

This script tests the ChromaFi integration discovery process with comprehensive logging.
Run this via SSH on your Home Assistant system to debug device discovery issues.

Usage:
1. Copy this file to your Home Assistant system (e.g., /config/test_chromafi_discovery.py)
2. SSH into Home Assistant
3. Run: python3 /config/test_chromafi_discovery.py

This will show you exactly what Bluetooth devices are discovered and why your fan
might not be found by the integration.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Setup comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
_LOGGER = logging.getLogger(__name__)

# Add Home Assistant paths
sys.path.insert(0, '/usr/src/homeassistant')
sys.path.insert(0, '/config')

try:
    from homeassistant.core import HomeAssistant
    from homeassistant.components.bluetooth import async_discovered_service_info, async_ble_device_from_address
    from homeassistant.config import async_hass_config_yaml
    from homeassistant.setup import async_setup_component
    from homeassistant import bootstrap
    import homeassistant.util.dt as dt_util
    _LOGGER.info("Successfully imported Home Assistant modules")
except ImportError as e:
    _LOGGER.error("Failed to import Home Assistant modules: %s", e)
    _LOGGER.error("Make sure you're running this from within the Home Assistant environment")
    sys.exit(1)

async def test_bluetooth_discovery():
    """Test Bluetooth discovery functionality."""
    _LOGGER.info("=" * 80)
    _LOGGER.info("ChromaFi Bluetooth Discovery Test")
    _LOGGER.info("=" * 80)
    
    # Initialize minimal Home Assistant instance
    try:
        _LOGGER.info("Initializing Home Assistant core...")
        hass = HomeAssistant("/config")
        hass.config.time_zone = dt_util.DEFAULT_TIME_ZONE
        
        # Setup Bluetooth component
        _LOGGER.info("Setting up Bluetooth component...")
        bluetooth_setup = await async_setup_component(hass, "bluetooth", {})
        if not bluetooth_setup:
            _LOGGER.error("Failed to setup Bluetooth component")
            return False
            
        _LOGGER.info("Bluetooth component setup successful")
        
        # Wait a moment for discovery to populate
        _LOGGER.info("Waiting 3 seconds for device discovery...")
        await asyncio.sleep(3)
        
        # Get all discovered devices
        _LOGGER.info("-" * 60)
        _LOGGER.info("DISCOVERING BLUETOOTH DEVICES")
        _LOGGER.info("-" * 60)
        
        all_discovered = list(async_discovered_service_info(hass, False))
        _LOGGER.info("Total discovered Bluetooth devices: %d", len(all_discovered))
        
        if not all_discovered:
            _LOGGER.warning("No Bluetooth devices discovered!")
            _LOGGER.warning("This could indicate:")
            _LOGGER.warning("  1. Bluetooth adapter is not working")
            _LOGGER.warning("  2. No devices are broadcasting nearby") 
            _LOGGER.warning("  3. Home Assistant Bluetooth integration is not running")
            return False
        
        # Log all devices with detailed info
        chromacomfort_devices = []
        for i, discovery_info in enumerate(all_discovered, 1):
            device_name = discovery_info.name or "(No Name)"
            rssi = getattr(discovery_info, 'rssi', 'N/A')
            
            _LOGGER.info("Device %d:", i)
            _LOGGER.info("  Name: '%s'", device_name)
            _LOGGER.info("  Address: %s", discovery_info.address)
            _LOGGER.info("  RSSI: %s", rssi)
            
            # Test ChromaFi matching logic
            device_name_lower = device_name.lower()
            chroma_comfort_match = "chromacomfort" in device_name_lower
            chroma_comfort_hyphen_match = "chroma-comfort" in device_name_lower  
            chroma_match = "chroma" in device_name_lower and "comfort" in device_name_lower
            
            _LOGGER.info("  ChromaFi Matching:")
            _LOGGER.info("    - ChromaComfort: %s", chroma_comfort_match)
            _LOGGER.info("    - Chroma-Comfort: %s", chroma_comfort_hyphen_match)
            _LOGGER.info("    - Contains Chroma+Comfort: %s", chroma_match)
            
            is_chromacomfort = chroma_comfort_match or chroma_comfort_hyphen_match or chroma_match
            if is_chromacomfort:
                _LOGGER.info("  *** CHROMACOMFORT DEVICE FOUND! ***")
                chromacomfort_devices.append(discovery_info)
            
            _LOGGER.info("")  # Empty line for readability
        
        # Summary
        _LOGGER.info("-" * 60)
        _LOGGER.info("DISCOVERY SUMMARY")
        _LOGGER.info("-" * 60)
        _LOGGER.info("Total devices discovered: %d", len(all_discovered))
        _LOGGER.info("ChromaComfort devices found: %d", len(chromacomfort_devices))
        
        if chromacomfort_devices:
            _LOGGER.info("ChromaComfort devices:")
            for device in chromacomfort_devices:
                _LOGGER.info("  - '%s' (%s)", device.name, device.address)
        else:
            _LOGGER.warning("No ChromaComfort devices found!")
            _LOGGER.warning("This means your fan is either:")
            _LOGGER.warning("  1. Not powered on or not broadcasting")
            _LOGGER.warning("  2. Using a different device name")
            _LOGGER.warning("  3. Not in range of the Bluetooth adapter")
        
        # Test connection to ChromaComfort devices
        if chromacomfort_devices:
            await test_device_connections(hass, chromacomfort_devices)
        
        return len(chromacomfort_devices) > 0
        
    except Exception as e:
        _LOGGER.error("Error during Bluetooth discovery test: %s", e, exc_info=True)
        return False

async def test_device_connections(hass: HomeAssistant, devices):
    """Test connections to discovered ChromaComfort devices."""
    _LOGGER.info("-" * 60)
    _LOGGER.info("TESTING DEVICE CONNECTIONS")
    _LOGGER.info("-" * 60)
    
    for device_info in devices:
        _LOGGER.info("Testing connection to '%s' (%s)...", device_info.name, device_info.address)
        
        try:
            # Get BLE device
            ble_device = await async_ble_device_from_address(hass, device_info.address, connectable=True)
            if ble_device:
                _LOGGER.info("  ✓ BLE device found and connectable")
                _LOGGER.info("    Device details: %s", ble_device)
            else:
                _LOGGER.warning("  ✗ Could not get BLE device for address %s", device_info.address)
                
        except Exception as e:
            _LOGGER.error("  ✗ Error testing connection: %s", e)

def test_chromafi_imports():
    """Test if ChromaFi integration files can be imported."""
    _LOGGER.info("-" * 60)
    _LOGGER.info("TESTING CHROMAFI IMPORTS")
    _LOGGER.info("-" * 60)
    
    try:
        # Test if custom component exists
        chromafi_path = Path("/config/custom_components/chromafi")
        if not chromafi_path.exists():
            _LOGGER.error("ChromaFi custom component not found at: %s", chromafi_path)
            return False
        
        _LOGGER.info("ChromaFi component found at: %s", chromafi_path)
        
        # List files
        files = list(chromafi_path.glob("*.py"))
        _LOGGER.info("ChromaFi files found: %s", [f.name for f in files])
        
        # Try importing
        sys.path.insert(0, str(chromafi_path.parent))
        
        try:
            from chromafi.config_flow import ConfigFlow
            _LOGGER.info("  ✓ config_flow.py imported successfully")
        except Exception as e:
            _LOGGER.error("  ✗ Failed to import config_flow.py: %s", e)
        
        try:
            from chromafi.coordinator import ChromaFiCoordinator
            _LOGGER.info("  ✓ coordinator.py imported successfully") 
        except Exception as e:
            _LOGGER.error("  ✗ Failed to import coordinator.py: %s", e)
            
        try:
            from chromafi.const import DOMAIN
            _LOGGER.info("  ✓ const.py imported successfully - DOMAIN: %s", DOMAIN)
        except Exception as e:
            _LOGGER.error("  ✗ Failed to import const.py: %s", e)
        
        return True
        
    except Exception as e:
        _LOGGER.error("Error testing ChromaFi imports: %s", e)
        return False

async def main():
    """Main test function."""
    _LOGGER.info("Starting ChromaFi Integration Discovery Test")
    _LOGGER.info("Python version: %s", sys.version)
    _LOGGER.info("Working directory: %s", Path.cwd())
    _LOGGER.info("")
    
    # Test imports first
    imports_ok = test_chromafi_imports()
    _LOGGER.info("")
    
    # Test Bluetooth discovery
    discovery_ok = await test_bluetooth_discovery()
    
    # Final summary
    _LOGGER.info("=" * 80)
    _LOGGER.info("TEST RESULTS SUMMARY")
    _LOGGER.info("=" * 80)
    _LOGGER.info("ChromaFi imports: %s", "✓ PASS" if imports_ok else "✗ FAIL")
    _LOGGER.info("Device discovery: %s", "✓ PASS" if discovery_ok else "✗ FAIL")
    
    if imports_ok and discovery_ok:
        _LOGGER.info("🎉 All tests passed! ChromaFi should work with your device.")
    elif imports_ok:
        _LOGGER.info("⚠️  ChromaFi files are OK, but no devices found. Check your fan is on and broadcasting.")
    else:
        _LOGGER.info("❌ ChromaFi integration has issues. Check the errors above.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _LOGGER.info("Test interrupted by user")
    except Exception as e:
        _LOGGER.error("Unexpected error: %s", e, exc_info=True)