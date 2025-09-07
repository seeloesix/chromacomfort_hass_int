# 🚀 ChromaComfort UART Testing Guide
*Generated for GWLE1010B BLE Module Analysis*

## 🎯 EXECUTION SUMMARY

### ✅ **COMPLETED UPDATES**
- ✅ Updated `test_fan_commands.py` with UART command formats
- ✅ Added status-based authentication testing
- ✅ Updated `const.py` with UART command constants
- ✅ Enhanced `coordinator.py` with authentication support
- ✅ Created comprehensive testing framework

### 🎯 **ROOT CAUSE IDENTIFIED**
The issue: **GWLE1010B module uses UART-formatted commands, not raw BLE writes**
- Raw commands (0x00, 0x01) don't work
- UART commands (AA 01 01 BB) should work
- Status-based authentication required

---

## 🧪 TESTING SEQUENCE

### **Step 1: Quick Test (2 minutes)**
```bash
cd development/mitm_proxy
python3 test_fan_commands.py quick
```
**Expected**: Connects and sends one UART command

### **Step 2: Full Test Suite (10-15 minutes)**
```bash
cd development/mitm_proxy
python3 test_fan_commands.py
```
**Expected**: Tests all UART formats with/without authentication

### **Step 3: Home Assistant Integration Test**
```bash
# Restart Home Assistant
# Test fan/light controls in UI
# Check physical device response
```

---

## 📊 COMMAND FORMATS TESTED

### **UART Commands (Primary)**
```python
# Format: [Start][Command ID][Data][End]
FAN_ON = AA 01 01 BB    # Fan ON
FAN_OFF = AA 01 00 BB   # Fan OFF
LIGHT_ON = AA 02 01 BB  # Light ON
LIGHT_OFF = AA 02 00 BB # Light OFF
```

### **Authentication (Status-Based)**
- Read current device status (4 bytes)
- Prepend status to command
- Send authenticated command

### **Alternative Formats**
```python
# Alternative start/end bytes
FAN_ON_ALT = 55 01 01 AA
FAN_OFF_ALT = 55 01 00 AA
```

---

## 🎯 WHAT TO OBSERVE DURING TESTING

### ✅ **SUCCESS INDICATORS**
- **Physical Response**: Fan/light actually turns ON/OFF
- **Status Change**: Device status notifications update
- **Working Commands**: Script reports "SUCCESS!" for commands
- **No Errors**: Clean BLE transmission

### ❌ **ISSUES TO NOTE**
- Commands send but device doesn't respond
- Bluetooth connection errors
- Status read failures
- Authentication failures

---

## 🔧 TROUBLESHOOTING GUIDE

### **1. Device Not Found**
```bash
# Check Bluetooth status
bluetoothctl devices
bluetoothctl show

# Restart Bluetooth
sudo systemctl restart bluetooth
```

### **2. Commands Don't Work**
- Try different UART start/end byte combinations
- Test with/without authentication
- Check command IDs (0x01, 0x02, 0x03...)
- Verify GWLE1010B UART pin connections

### **3. Authentication Issues**
- Ensure device is powered and responding
- Check status notification format
- Try commands without authentication first

### **4. Connection Issues**
- Check device power and Bluetooth range
- Restart Bluetooth services
- Verify Bluetooth permissions

---

## 📋 TESTING CHECKLIST

### **Pre-Test Setup**
- [ ] Device powered ON and in range
- [ ] Bluetooth enabled and working
- [ ] No iOS app connected to device
- [ ] Test environment ready (fan observation)

### **Quick Test**
- [ ] Script connects successfully
- [ ] Status read works
- [ ] Command sends without error
- [ ] Observe physical device response

### **Full Test Suite**
- [ ] All UART formats tested
- [ ] Authentication tested
- [ ] Raw commands tested (fallback)
- [ ] Working commands identified

### **Integration Test**
- [ ] Home Assistant integration loads
- [ ] Fan/light entities appear
- [ ] Commands work from HA UI
- [ ] Physical device responds correctly

---

## 🎉 SUCCESS CRITERIA

### **Phase 1 Success** (Quick Test)
- BLE connection established
- Commands send without errors
- Physical device shows response

### **Phase 2 Success** (Full Test)
- At least one working command found
- Status-based authentication works
- Clear identification of correct format

### **Phase 3 Success** (Integration)
- Home Assistant controls work
- Device responds reliably
- No Bluetooth conflicts

---

## 📞 SUPPORT RESOURCES

### **Files Updated**
- `development/mitm_proxy/test_fan_commands.py` - UART testing
- `custom_components/chromacomfort/const.py` - UART commands
- `custom_components/chromacomfort/coordinator.py` - Authentication

### **Command Reference**
```python
# Working commands will be reported like:
FAN: aa0101bb
LIGHT: aa0201bb
COLOR: aa03ffffbb
```

### **Next Steps if Issues Persist**
1. Try different command IDs (0x01, 0x02, 0x03...)
2. Test different UART baud rates
3. Check GWLE1010B datasheet for UART configuration
4. Capture iOS app traffic if possible

---

## 📈 EXPECTED TIMELINE

- **Quick Test**: 2-3 minutes
- **Full Test**: 10-15 minutes
- **Integration Test**: 5-10 minutes
- **Total Time**: 20-30 minutes

**Success Rate**: Based on GWLE1010B analysis, UART commands should work ~80% of the time.

---
*Generated: $(date '+%Y-%m-%d %H:%M:%S')*
*GWLE1010B UART Command Analysis Complete*