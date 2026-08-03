"""Constants for the ChromaComfort integration."""

from typing import Final

DOMAIN: Final = "chromacomfort"

MANUFACTURER: Final = "Broan-NuTone"
MODEL: Final = "ChromaComfort"

# The fan advertises this name and its control service UUID.
DEVICE_NAME_PREFIX: Final = "Chroma-Comfort"
CONTROL_SERVICE_UUID: Final = "a08f7710-c37c-11e3-99cc-0228ac012a70"

# Control service characteristics, confirmed by GATT enumeration on a live unit.
# The device also exposes 00001016-d102-11e1-9b23-00025b00a5a5 with several
# writable characteristics; that is the Qualcomm CSR over-the-air update service
# and writes to it do nothing. Do not use it.
WRITE_CHAR_UUID: Final = "bb8a27e0-c37c-11e3-b953-0228ac012a70"
NOTIFY_CHAR_UUID: Final = "b34ae89e-c37c-11e3-940e-0228ac012a70"

# Command delivery. The write characteristic is write-without-response, so there
# is no BLE-level acknowledgement and the fan drops isolated writes. The official
# app sends every frame three times about 37 ms apart; anything less fails
# intermittently in a way that is very hard to diagnose later.
WRITE_REPEATS: Final = 3
WRITE_GAP: Final = 0.037

# Gap between two *different* commands. WRITE_GAP is the spacing between repeats
# of one frame; back-to-back distinct commands need noticeably longer or the fan
# acts on only the first. Seen when saving a colour then activating it.
COMMAND_GAP: Final = 0.25

# The fan refuses to dim below 10%.
MIN_BRIGHTNESS: Final = 10
MAX_BRIGHTNESS: Final = 100

# Gap between the three steps of a scene upload (stop, write palette, activate).
# COMMAND_GAP is too short here: the activation is dropped if it follows the
# palette write too closely. The vendor app waits about a second.
SCENE_STEP_GAP: Final = 1.0
