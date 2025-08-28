# ChromaComfort Package Structure

## For End Users

**Main Integration Files:**
- `README.md` - Installation and usage instructions
- `INSTALLATION.md` - Quick installation guide  
- `LICENSE` - MIT license
- `hacs.json` - HACS integration configuration
- `custom_components/chromacomfort/` - **The actual Home Assistant integration**

## Project Organization

```
ChromaComfort/
├── README.md                    # Main documentation
├── INSTALLATION.md              # Installation guide
├── LICENSE                      # MIT license
├── hacs.json                   # HACS configuration
├── custom_components/chromacomfort/  # Home Assistant integration
│   ├── __init__.py
│   ├── manifest.json
│   ├── config_flow.py
│   ├── coordinator.py
│   ├── fan.py
│   ├── light.py
│   ├── const.py
│   └── translations/
├── development/                 # Development tools (optional)
│   ├── chromacomfort_gatt_logger.py
│   ├── mitm_proxy/
│   └── ble/
└── research/                    # Research documentation (optional)
    ├── CHROMACOMFORT_COMMANDS_DISCOVERED.md
    └── Various reverse engineering docs
```

## What You Need

**For Installation:**
- Copy `custom_components/chromacomfort/` to your Home Assistant
- Follow `INSTALLATION.md` or `README.md`

**Everything Else:**
- `development/` - Tools used to create the integration (not needed)
- `research/` - Reverse engineering documentation (not needed)

## Current Status (2025-08-28)

**Package Organization**: ✅ Complete
- ✅ **End users**: Simple installation via HACS or manual
- ✅ **HACS compatibility**: Proper structure and metadata
- ✅ **Integration Framework**: BLE connection, entities, UI working
- ✅ **Developers**: Command testing tools available
- ✅ **Research**: Comprehensive reverse engineering documentation

**Integration Status**: ⚠️ Command Verification Needed
- ✅ **Discovery & Connection**: Fully functional
- ✅ **Home Assistant Integration**: Entities created, UI responsive
- ⚠️ **Physical Device Control**: Commands send but need verification
- 🔄 **Command Testing**: Tools available in `/development/mitm_proxy/`

**For Developers**: Use `/development/mitm_proxy/test_fan_commands.py` to verify and update command formats in `custom_components/chromacomfort/const.py`