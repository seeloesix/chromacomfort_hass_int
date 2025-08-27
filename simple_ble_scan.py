#!/usr/bin/env python3
"""
Simple BLE Scanner for ChromaComfort Fans

This is a standalone script that uses Bleak directly to scan for Bluetooth devices.
Use this if the full Home Assistant test script has import issues.

Usage:
1. SSH into Home Assistant  
2. Run: python3 simple_ble_scan.py

This will show all BLE devices and highlight any ChromaComfort fans found.
"""

import asyncio
import logging
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
_LOGGER = logging.getLogger(__name__)

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    _LOGGER.info("Successfully imported Bleak BLE library")
except ImportError as e:
    _LOGGER.error("Failed to import Bleak: %s", e)
    _LOGGER.error("Install with: pip install bleak")
    sys.exit(1)

async def scan_for_chromacomfort():
    """Scan for Bluetooth devices and look for ChromaComfort fans."""
    _LOGGER.info("=" * 80)
    _LOGGER.info("Simple BLE Scanner for ChromaComfort Fans")
    _LOGGER.info("Started at: %s", datetime.now())
    _LOGGER.info("=" * 80)
    
    try:
        _LOGGER.info("Starting Bluetooth LE scan (10 seconds)...")
        scanner = BleakScanner()
        devices = await scanner.discover(timeout=10.0)
        
        _LOGGER.info("Scan completed. Found %d devices", len(devices))
        _LOGGER.info("")
        
        if not devices:
            _LOGGER.warning("No Bluetooth devices found!")
            _LOGGER.warning("This could mean:")
            _LOGGER.warning("  - Bluetooth is disabled")
            _LOGGER.warning("  - No devices are advertising nearby")
            _LOGGER.warning("  - Permission issues")
            return
        
        # Analyze all devices
        chromacomfort_devices = []
        
        _LOGGER.info("-" * 60)
        _LOGGER.info("ALL DISCOVERED DEVICES")
        _LOGGER.info("-" * 60)
        
        for i, device in enumerate(devices, 1):
            device_name = device.name or "(No Name)"
            rssi = getattr(device, 'rssi', 'N/A')
            
            _LOGGER.info("Device %d:", i)
            _LOGGER.info("  Name: '%s'", device_name)
            _LOGGER.info("  Address: %s", device.address)
            _LOGGER.info("  RSSI: %s dBm", rssi)
            
            # Test ChromaComfort matching (same logic as integration)
            device_name_lower = device_name.lower()
            chroma_comfort_match = "chromacomfort" in device_name_lower
            chroma_comfort_hyphen_match = "chroma-comfort" in device_name_lower  
            chroma_match = "chroma" in device_name_lower and "comfort" in device_name_lower
            
            _LOGGER.info("  ChromaComfort Matching:")
            _LOGGER.info("    - 'chromacomfort': %s", chroma_comfort_match)
            _LOGGER.info("    - 'chroma-comfort': %s", chroma_comfort_hyphen_match)
            _LOGGER.info("    - contains 'chroma' + 'comfort': %s", chroma_match)
            
            # Check if it matches our criteria
            is_chromacomfort = chroma_comfort_match or chroma_comfort_hyphen_match or chroma_match
            
            if is_chromacomfort:
                _LOGGER.info("  🎯 *** CHROMACOMFORT FAN FOUND! ***")
                chromacomfort_devices.append(device)
            elif "chroma" in device_name_lower or "comfort" in device_name_lower:
                _LOGGER.info("  🔍 Partial match (contains 'chroma' or 'comfort')")
            
            _LOGGER.info("")  # Empty line for readability
        
        # Summary
        _LOGGER.info("=" * 80)
        _LOGGER.info("SCAN RESULTS SUMMARY")
        _LOGGER.info("=" * 80)
        _LOGGER.info("Total devices found: %d", len(devices))
        _LOGGER.info("ChromaComfort fans found: %d", len(chromacomfort_devices))
        
        if chromacomfort_devices:
            _LOGGER.info("")
            _LOGGER.info("🎉 ChromaComfort fan(s) detected:")
            for device in chromacomfort_devices:
                rssi = getattr(device, 'rssi', 'N/A')
                _LOGGER.info("  ✓ '%s' (%s) - Signal: %s dBm", 
                           device.name, device.address, rssi)
            
            _LOGGER.info("")
            _LOGGER.info("✅ These devices should be discoverable by the ChromaComfort integration!")
            
            # Test connectivity
            await test_connectivity(chromacomfort_devices[0])
            
        else:
            _LOGGER.warning("❌ No ChromaComfort fans found!")
            _LOGGER.warning("")
            _LOGGER.warning("Troubleshooting suggestions:")
            _LOGGER.warning("1. Make sure your ChromaComfort fan is powered on")
            _LOGGER.warning("2. Check if the fan is in pairing/discoverable mode")
            _LOGGER.warning("3. Move closer to the fan (within 10 feet)")
            _LOGGER.warning("4. Check if the fan name is different than expected")
            _LOGGER.warning("")
            _LOGGER.warning("If you see a device that should be your fan, check its name")
            _LOGGER.warning("and update the ChromaComfort integration matching logic.")
        
    except Exception as e:
        _LOGGER.error("Error during BLE scan: %s", e, exc_info=True)

async def test_connectivity(device: BLEDevice):
    """Test if we can connect to a ChromaComfort device."""
    _LOGGER.info("-" * 60)
    _LOGGER.info("TESTING CONNECTIVITY")
    _LOGGER.info("-" * 60)
    
    try:
        from bleak import BleakClient
        
        _LOGGER.info("Testing connection to '%s' (%s)...", device.name, device.address)
        
        async with BleakClient(device, timeout=20.0) as client:
            _LOGGER.info("✅ Successfully connected!")
            
            # Get services
            services = client.services
            _LOGGER.info("Device has %d services:", len(services))
            
            for service in services:
                _LOGGER.info("  Service: %s", service.uuid)
                for char in service.characteristics:
                    properties = ", ".join(char.properties)
                    _LOGGER.info("    Characteristic: %s (%s)", char.uuid, properties)
            
            # Check for known ChromaComfort characteristics
            known_chars = {
                "00001018-d102-11e1-9b23-00025b00a5a5": "Fan Control",
                "00001013-d102-11e1-9b23-00025b00a5a5": "Light Control", 
                "bb8a27e1-c37c-11e3-b954-0228ac012a70": "Color Control",
                "00001014-d102-11e1-9b23-00025b00a5a5": "Device Status"
            }
            
            found_chars = []
            for char_uuid, char_name in known_chars.items():
                try:
                    char = client.services.get_characteristic(char_uuid)
                    if char:
                        found_chars.append(char_name)
                        _LOGGER.info("✅ Found %s characteristic", char_name)
                except:
                    pass
            
            if found_chars:
                _LOGGER.info("🎉 This appears to be a valid ChromaComfort fan!")
                _LOGGER.info("Found characteristics: %s", ", ".join(found_chars))
            else:
                _LOGGER.warning("⚠️  No known ChromaComfort characteristics found")
                _LOGGER.warning("This might not be a ChromaComfort fan, or it uses different UUIDs")
            
    except Exception as e:
        _LOGGER.error("❌ Connection failed: %s", e)
        _LOGGER.error("This could mean:")
        _LOGGER.error("  - Device is not connectable")
        _LOGGER.error("  - Device is already connected to another client")
        _LOGGER.error("  - Bluetooth permissions issue")

if __name__ == "__main__":
    try:
        asyncio.run(scan_for_chromacomfort())
    except KeyboardInterrupt:
        _LOGGER.info("Scan interrupted by user")
    except Exception as e:
        _LOGGER.error("Unexpected error: %s", e, exc_info=True)