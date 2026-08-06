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

# How long to keep the connection after an operation finishes. The fan accepts
# only one connection at a time and the vendor app wants it too, so we let go
# quickly -- but not instantly, or a burst of commands reconnects for each one.
DISCONNECT_DELAY: Final = 5.0

# Background state refresh. Each poll is a short connect/read/release, during
# which the phone app cannot connect, so the default is deliberately infrequent;
# Home Assistant learns the true state whenever it sends a command anyway.
CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL: Final = 3600
SCAN_INTERVAL_OPTIONS: Final = {
    0: "Never",
    300: "Every 5 minutes",
    900: "Every 15 minutes",
    1800: "Every 30 minutes",
    3600: "Every hour",
    7200: "Every 2 hours",
}
