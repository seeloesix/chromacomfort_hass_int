"""Wire protocol for Broan-NuTone ChromaComfort bath fans.

The fan carries a GooWi GWLE1010B module (Qualcomm CSR1010) which relays 19-byte
framed packets between its BLE GATT service and the host MCU's UART. Both
directions use the same frame shape::

    [0]  0x3A  header
    [1]  0x11  length (17 bytes follow)
    [2]  version   0x01 outbound, 0x05 inbound
    [3]  control 1 0x00 outbound, 0xA0 inbound
    [4]  control 2 0x40 command/ack, 0x41 status
    ...  payload
    [18] trailer

See PROTOCOL.md for the full field reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

FRAME_LENGTH: Final = 19

HEADER: Final = 0x3A
LENGTH: Final = 0x11

# Outbound commands must use version 1. The fan silently ignores any other
# value -- including the 5 it uses in its own status replies.
TX_VERSION: Final = 0x01
RX_VERSION: Final = 0x05

TX_CONTROL_1: Final = 0x00
RX_CONTROL_1: Final = 0xA0
CONTROL_2_COMMAND: Final = 0x40
CONTROL_2_STATUS: Final = 0x41

# Sweep colour defaults, sent unchanged on every command.
SWEEP_1_DEFAULT: Final = 0x01
SWEEP_2_DEFAULT: Final = 0x18

# Command opcodes.
CMD_FAN_ON: Final = 0x01
CMD_FAN_OFF: Final = 0x02
CMD_LIGHT_ON: Final = 0x03
CMD_LIGHT_OFF: Final = 0x04
CMD_WALL_RGB_ON: Final = 0x05
CMD_WALL_RGB_OFF: Final = 0x06
CMD_FAVORITE_ON: Final = 0x0B
CMD_FAVORITE_OFF: Final = 0x0C
CMD_SAVE_FAVORITE: Final = 0x0D
CMD_COUNTDOWN_ON: Final = 0x11
CMD_COUNTDOWN_OFF: Final = 0x12
CMD_PATTERN_ON: Final = 0x20
CMD_PATTERN_OFF: Final = 0x21
CMD_PATTERN_SAVE: Final = 0x2A

# Saving a favourite colour is the one command that carries a non-zero speed.
SAVE_FAVORITE_SPEED: Final = 30

# Status mask bits, frame byte 5.
MASK_FAN: Final = 0x80
MASK_LIGHT: Final = 0x40
MASK_WALL_RGB: Final = 0x20
MASK_RGB_SWEEP: Final = 0x10
MASK_FAVORITE_1: Final = 0x08
MASK_FAVORITE_2: Final = 0x04
MASK_USER_PATTERN: Final = 0x02


def crc8_maxim(data: bytes) -> int:
    """CRC-8/MAXIM (Dallas 1-Wire): poly 0x31 reflected, init 0x00, no final XOR."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8C if crc & 1 else crc >> 1
    return crc


def frame_crc(frame: bytes) -> int:
    """Return the CRC the fan computes over a frame, i.e. across bytes 1..17."""
    return crc8_maxim(frame[1:18])


class ChromaComfortProtocolError(ValueError):
    """A received frame is not a well-formed ChromaComfort packet."""


@dataclass(frozen=True, slots=True)
class ChromaComfortState:
    """Decoded device state from a status notification."""

    fan_on: bool
    light_on: bool
    wall_rgb_on: bool
    rgb_sweep_on: bool
    favorite_1_on: bool
    favorite_2_on: bool
    user_pattern_on: bool
    brightness: int
    mask: int

    @property
    def any_color_on(self) -> bool:
        """True when any of the mutually exclusive colour modes is active."""
        return self.wall_rgb_on or self.favorite_1_on or self.favorite_2_on


def build_command(
    opcode: int,
    *,
    red: int = 0,
    green: int = 0,
    blue: int = 0,
    dimmer: int = 0,
    speed: int = 0,
    duration: int = 0,
) -> bytes:
    """Build a 19-byte command frame.

    The fan does not verify the trailer on inbound commands, so it is sent as
    zero to match the reference implementation. RGB values are raw 0-255 with no
    gamma correction; dimmer is a 0-100 percentage.
    """
    for name, value in (
        ("opcode", opcode),
        ("red", red),
        ("green", green),
        ("blue", blue),
        ("speed", speed),
        ("duration", duration),
    ):
        if not 0 <= value <= 0xFF:
            raise ValueError(f"{name} must be 0-255, got {value}")
    if not 0 <= dimmer <= 100:
        raise ValueError(f"dimmer must be 0-100, got {dimmer}")

    return bytes(
        (
            HEADER,
            LENGTH,
            TX_VERSION,
            TX_CONTROL_1,
            CONTROL_2_COMMAND,
            opcode,
            red,
            green,
            blue,
            dimmer,
            speed,
            SWEEP_1_DEFAULT,
            SWEEP_2_DEFAULT,
            duration,
            0,  # timer 1
            0,  # timer 2
            0,  # timer 3
            0,  # timer 4
            0,  # trailer, not validated by the fan
        )
    )


def save_favorite_color(red: int, green: int, blue: int) -> bytes:
    """Store an RGB colour as favourite 1. Activate it with CMD_FAVORITE_ON."""
    return build_command(
        CMD_SAVE_FAVORITE,
        red=red,
        green=green,
        blue=blue,
        speed=SAVE_FAVORITE_SPEED,
    )


def is_status_frame(frame: bytes) -> bool:
    """True when the frame is a device status report."""
    return (
        len(frame) == FRAME_LENGTH
        and frame[0] == HEADER
        and frame[3] == RX_CONTROL_1
        and frame[4] == CONTROL_2_STATUS
    )


def is_ack_frame(frame: bytes) -> bool:
    """True when the frame is a command acknowledgement."""
    return len(frame) >= 5 and frame[0] == HEADER and frame[3] == RX_CONTROL_1 and frame[4] == CONTROL_2_COMMAND


def parse_status(frame: bytes, *, verify_crc: bool = True) -> ChromaComfortState:
    """Decode a status notification.

    Raises ChromaComfortProtocolError if the frame is malformed. CRC verification
    is on by default: the fan does emit a valid CRC-8/MAXIM trailer on status
    frames, so a mismatch means a corrupt or truncated notification.
    """
    if len(frame) != FRAME_LENGTH:
        raise ChromaComfortProtocolError(f"expected {FRAME_LENGTH} bytes, got {len(frame)}")
    if frame[0] != HEADER:
        raise ChromaComfortProtocolError(f"bad header 0x{frame[0]:02x}")
    if frame[1] != LENGTH:
        raise ChromaComfortProtocolError(f"bad length byte 0x{frame[1]:02x}")
    if frame[3] != RX_CONTROL_1 or frame[4] != CONTROL_2_STATUS:
        raise ChromaComfortProtocolError(
            f"not a status frame: control bytes 0x{frame[3]:02x} 0x{frame[4]:02x}"
        )
    if verify_crc:
        expected = frame_crc(frame)
        if frame[18] != expected:
            raise ChromaComfortProtocolError(
                f"CRC mismatch: got 0x{frame[18]:02x}, expected 0x{expected:02x}"
            )

    mask = frame[5]
    return ChromaComfortState(
        fan_on=bool(mask & MASK_FAN),
        light_on=bool(mask & MASK_LIGHT),
        wall_rgb_on=bool(mask & MASK_WALL_RGB),
        rgb_sweep_on=bool(mask & MASK_RGB_SWEEP),
        favorite_1_on=bool(mask & MASK_FAVORITE_1),
        favorite_2_on=bool(mask & MASK_FAVORITE_2),
        user_pattern_on=bool(mask & MASK_USER_PATTERN),
        brightness=frame[7],
        mask=mask,
    )
