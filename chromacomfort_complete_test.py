#!/usr/bin/env python3
"""
ChromaComfort Complete Testing Suite
Combines all authentication research and testing into a single comprehensive tool

Usage:
1. Physical Controller Monitoring: Monitor real device while using physical controller
2. Status Authentication: Test authentication using current device status
3. Advanced Authentication: Test cryptographic authentication methods
4. Direct Control: Test direct commands without authentication

Based on breakthrough research from 2025-09-06 physical controller analysis.
"""
import asyncio
from bleak import BleakClient, BleakScanner
import hashlib
import hmac
import struct
import time
from datetime import datetime

class ChromaComfortTestSuite:
    def __init__(self):
        self.device_mac = None
        self.client = None
        self.latest_notification = None
        self.all_notifications = []
        
        # Characteristics
        self.chars = {
            'fan_control': '00001018-d102-11e1-9b23-00025b00a5a5',
            'light_control': '00001013-d102-11e1-9b23-00025b00a5a5',
            'color_control': 'bb8a27e1-c37c-11e3-b954-0228ac012a70',
            'device_status': '00001014-d102-11e1-9b23-00025b00a5a5',
            'mystery_write': 'bb8a27e0-c37c-11e3-b953-0228ac012a70',
            'notification_char': 'b34ae89e-c37c-11e3-940e-0228ac012a70',
        }
        
        # Device status codes discovered from physical controller monitoring
        self.device_status_codes = {
            0x4100: "Base state (fan off, light off)",
            0x4180: "Fan ON (bit 7 set)",
            0x4140: "Light ON (bit 6 set)", 
            0x4120: "Special setting",
            0x41c0: "Fan + Light combo",
            0x41a0: "Advanced combination"
        }
        
        # Known device values for authentication
        self.known_values = {
            'light_state': bytes([0x01]),
            'color_state': bytes.fromhex('802500000000'),
            'unknown_read': bytes([0x06]),
            'device_manufacturer': 'GooWi Technology Co., Ltd.',
            'device_name': 'Chroma-Comfort'
        }
    
    async def scan_and_connect(self):
        """Find and connect to ChromaComfort device"""
        print('🔍 Scanning for ChromaComfort device...')
        
        devices = await BleakScanner.discover()
        for device in devices:
            name = device.name or "Unknown"
            if ('chroma' in name.lower() or 
                'comfort' in name.lower() or 
                device.address.upper() == '64:72:D8:CC:47:21'):
                self.device_mac = device.address
                print(f'✅ Found ChromaComfort: {name} ({device.address})')
                break
        
        if not self.device_mac:
            print('❌ ChromaComfort device not found')
            return False
        
        self.client = BleakClient(self.device_mac)
        try:
            await self.client.connect()
            print(f'✅ Connected to {self.device_mac}')
            return True
        except Exception as e:
            print(f'❌ Connection failed: {e}')
            return False
    
    def decode_status_notification(self, data):
        """Decode device status notification"""
        if len(data) < 19:
            return None
            
        header = struct.unpack('<I', data[0:4])[0]
        device_status = struct.unpack('<H', data[4:6])[0]
        brightness = data[6]
        speed = data[7]
        footer = data[16:19]
        
        return {
            'header': f'0x{header:08x}',
            'device_status': f'0x{device_status:04x}',
            'device_status_desc': self.device_status_codes.get(device_status, "Unknown"),
            'brightness': brightness,
            'speed': speed,
            'fan_on': (device_status & 0x80) != 0,
            'light_on': (device_status & 0x40) != 0,
            'footer': footer,
            'raw': data
        }
    
    async def monitor_physical_controller(self):
        """Monitor BLE traffic while using physical controller"""
        print('\n📱 PHYSICAL CONTROLLER MONITORING')
        print('='*60)
        print('Use the PHYSICAL CONTROLLER to control the device.')
        print('This will capture the real working protocol.')
        print()
        
        def notification_handler(sender, data):
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            self.latest_notification = data
            self.all_notifications.append((timestamp, data))
            
            status = self.decode_status_notification(data)
            if status:
                print(f'[{timestamp}] 📊 {status["device_status_desc"]} | '
                      f'Brightness: {status["brightness"]} | Speed: {status["speed"]} | '
                      f'Footer: {status["footer"].hex()}')
            else:
                print(f'[{timestamp}] 📢 Raw: {data.hex()}')
        
        await self.client.start_notify(self.chars['notification_char'], notification_handler)
        
        input("\n⚡ Use physical controller NOW, press ENTER when done...")
        
        print(f'\n📊 Captured {len(self.all_notifications)} notifications')
        if self.all_notifications:
            unique_patterns = set(data.hex() for _, data in self.all_notifications)
            print(f'🔍 Unique patterns: {len(unique_patterns)}')
            
            # Look for pattern changes (potential auth sequences)
            changes = []
            for i in range(len(self.all_notifications) - 1):
                current = self.all_notifications[i][1]
                next_data = self.all_notifications[i + 1][1]
                if current.hex() != next_data.hex():
                    changes.append((current, next_data))
            
            if changes:
                print(f'🔄 Pattern changes detected: {len(changes)}')
                for i, (before, after) in enumerate(changes[:5]):  # Show first 5
                    print(f'   {i+1}. {before.hex()} → {after.hex()}')
        
        return len(self.all_notifications) > 0
    
    async def test_status_based_authentication(self):
        """Test authentication using current device status"""
        print('\n🔐 STATUS-BASED AUTHENTICATION TEST')
        print('='*60)
        
        if not self.latest_notification:
            print('❌ No status notification available')
            return False
        
        status = self.decode_status_notification(self.latest_notification)
        if not status:
            print('❌ Could not decode status notification')
            return False
        
        print(f'📊 Current Status: {status["device_status_desc"]}')
        print(f'    Device Code: {status["device_status"]}')
        print(f'    Brightness: {status["brightness"]}, Speed: {status["speed"]}')
        print(f'    Footer: {status["footer"].hex()}')
        
        # Generate authentication keys from current status
        raw_status = status['raw']
        auth_keys = [
            ('Device-Code', raw_status[4:6]),
            ('Current-Values', raw_status[6:8]),
            ('Footer-Full', status['footer']),
            ('Footer-Last2', status['footer'][1:3]),
            ('XOR-Toggle', bytes([raw_status[4] ^ 0x80, raw_status[5]])),
        ]
        
        print(f'\n🧪 Testing {len(auth_keys)} status-based auth keys...')
        
        for key_name, key_bytes in auth_keys:
            success = await self.test_auth_key(key_name, key_bytes)
            if success:
                return True
        
        return False
    
    async def test_advanced_authentication(self):
        """Test advanced cryptographic authentication methods"""
        print('\n🔬 ADVANCED AUTHENTICATION TEST')
        print('='*60)
        
        if not self.latest_notification:
            print('❌ No challenge notification available')
            return False
        
        # Parse notification for advanced auth
        data = self.latest_notification
        if len(data) < 19:
            print('❌ Notification too short for advanced auth')
            return False
        
        challenge = data[6:16]
        device_id = data[4:6]
        footer = data[16:19]
        
        print(f'🔍 Challenge: {challenge.hex()}')
        print(f'   Device ID: {device_id.hex()}')
        print(f'   Footer: {footer.hex()}')
        
        # Generate advanced auth responses
        responses = []
        
        # HMAC-based with known values
        for key_name, key_value in self.known_values.items():
            if isinstance(key_value, bytes):
                try:
                    hmac_response = hmac.new(key_value, challenge, hashlib.sha256).digest()[:8]
                    responses.append((f'HMAC-{key_name}', hmac_response))
                except:
                    pass
        
        # MAC address based
        mac_bytes = bytes.fromhex('6472D8CC4721')
        mac_response = bytes([(mac_bytes[i % len(mac_bytes)] ^ challenge[i % len(challenge)]) for i in range(8)])
        responses.append(('MAC-based', mac_response))
        
        # Footer-based responses
        responses.append(('Footer-direct', footer))
        responses.append(('Footer-trimmed', footer[1:]))
        
        print(f'🧪 Testing {len(responses)} advanced auth methods...')
        
        for response_name, response_bytes in responses:
            success = await self.test_auth_key(response_name, response_bytes)
            if success:
                return True
        
        return False
    
    async def test_auth_key(self, key_name, key_bytes):
        """Test a specific authentication key"""
        print(f'\n🧪 Testing: {key_name}')
        print(f'   Auth Key: {key_bytes.hex()} ({len(key_bytes)} bytes)')
        
        try:
            # Send authentication key
            await self.client.write_gatt_char(self.chars['mystery_write'], key_bytes, response=False)
            print('   ✅ Auth key sent')
            await asyncio.sleep(1)
            
            # Test fan control
            await self.client.write_gatt_char(self.chars['fan_control'], bytes([0x01]), response=False)
            await asyncio.sleep(3)
            
            result = input('   ❓ Did the fan turn ON? (y/n): ').lower()
            if result in ['y', 'yes']:
                print(f'   🎉 SUCCESS! {key_name} authentication works!')
                print(f'   🔑 Working auth key: {key_bytes.hex()}')
                return True
            else:
                print(f'   ❌ {key_name} failed')
                return False
                
        except Exception as e:
            print(f'   ❌ Error: {e}')
            return False
    
    async def test_direct_control(self):
        """Test direct control without authentication"""
        print('\n🎮 DIRECT CONTROL TEST (NO AUTH)')
        print('='*60)
        
        commands = [
            ("Fan ON", self.chars['fan_control'], bytes([0x01])),
            ("Fan OFF", self.chars['fan_control'], bytes([0x00])),
            ("Light ON", self.chars['light_control'], bytes([0x01])),
            ("Light OFF", self.chars['light_control'], bytes([0x00])),
        ]
        
        for cmd_name, char_uuid, command in commands:
            print(f'\n🧪 Testing: {cmd_name}')
            try:
                await self.client.write_gatt_char(char_uuid, command, response=False)
                print(f'   ✅ Command sent: {command.hex()}')
                await asyncio.sleep(3)
                
                result = input(f'   ❓ Did {cmd_name} work? (y/n): ').lower()
                if result in ['y', 'yes']:
                    print(f'   🎉 SUCCESS: {cmd_name} works without auth!')
                    return True
            except Exception as e:
                print(f'   ❌ Error: {e}')
        
        return False
    
    async def run_complete_test_suite(self):
        """Run the complete ChromaComfort test suite"""
        print('🚀 CHROMACOMFORT COMPLETE TEST SUITE')
        print('='*80)
        print('Comprehensive testing based on physical controller analysis')
        print('This combines all authentication research into one tool.')
        print()
        
        if not await self.scan_and_connect():
            return
        
        # Setup notification monitoring
        def status_handler(sender, data):
            self.latest_notification = data
        
        await self.client.start_notify(self.chars['notification_char'], status_handler)
        await asyncio.sleep(2)  # Capture initial status
        
        print('\n🎯 TEST MENU:')
        print('1. Monitor Physical Controller (captures real protocol)')
        print('2. Test Status-Based Authentication (breakthrough method)')
        print('3. Test Advanced Authentication (cryptographic methods)')
        print('4. Test Direct Control (no authentication)')
        print('5. Run All Tests')
        
        choice = input('\nSelect test (1-5): ').strip()
        
        success = False
        
        if choice == '1':
            success = await self.monitor_physical_controller()
        elif choice == '2':
            success = await self.test_status_based_authentication()
        elif choice == '3':
            success = await self.test_advanced_authentication()
        elif choice == '4':
            success = await self.test_direct_control()
        elif choice == '5':
            # Run all tests
            print('\n🔄 Running complete test suite...')
            await self.monitor_physical_controller()
            if not await self.test_direct_control():
                if not await self.test_status_based_authentication():
                    success = await self.test_advanced_authentication()
                else:
                    success = True
        else:
            print('❌ Invalid choice')
        
        if success:
            print('\n🎉 BREAKTHROUGH ACHIEVED!')
            print('Authentication method discovered. Update coordinator.py with working auth.')
        else:
            print('\n📋 No breakthrough yet. Continue research:')
            print('1. Try different timing with physical controller')
            print('2. Analyze more status patterns')
            print('3. Test sequence authentication methods')
        
        await self.client.disconnect()
        print('\n✅ Test session complete')

async def main():
    """Main test execution"""
    print('ChromaComfort Complete Testing Suite')
    print('Based on 2025-09-06 physical controller breakthrough research')
    print()
    
    input('Press ENTER to start testing...')
    
    suite = ChromaComfortTestSuite()
    await suite.run_complete_test_suite()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n⏸️  Test interrupted')
    except Exception as e:
        print(f'\n❌ Error: {e}')
        import traceback
        traceback.print_exc()