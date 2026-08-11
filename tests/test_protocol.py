"""Protocol tests, validated against real captured traffic.

The golden data is 651 status notifications captured from a live fan on
2025-08-25. Every frame must pass CRC verification and decode to a plausible
state -- this turns the capture archive into a regression suite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "chromacomfort"))

import protocol as p  # noqa: E402

CAPTURE = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "captured_status_frames.json"
)


def load_captured_frames() -> list[bytes]:
    frames = [bytes.fromhex(h) for h in json.loads(CAPTURE.read_text())]
    assert frames, "capture fixture is empty"
    return frames


CAPTURED = load_captured_frames()
UNIQUE = sorted(set(CAPTURED))


class TestCrc:
    def test_known_vector(self):
        # CRC-8/MAXIM of b"123456789" is 0xA1.
        assert p.crc8_maxim(b"123456789") == 0xA1

    def test_empty(self):
        assert p.crc8_maxim(b"") == 0

    @pytest.mark.parametrize("frame", UNIQUE, ids=lambda f: f.hex())
    def test_every_captured_frame_has_valid_crc(self, frame):
        assert p.frame_crc(frame) == frame[18]

    def test_all_651_captured_frames(self):
        assert all(p.frame_crc(f) == f[18] for f in CAPTURED)
        assert len(CAPTURED) == 651


class TestParseStatus:
    @pytest.mark.parametrize("frame", UNIQUE, ids=lambda f: f.hex())
    def test_captured_frames_parse(self, frame):
        state = p.parse_status(frame)
        assert 0 <= state.brightness <= 100
        assert state.mask == frame[5]

    def test_all_off(self):
        state = p.parse_status(bytes.fromhex("3a1105a04100003200000fd9001e0001011007"))
        assert not state.fan_on
        assert not state.light_on
        assert not state.wall_rgb_on
        assert state.brightness == 50

    def test_fan_on(self):
        state = p.parse_status(bytes.fromhex("3a1105a04180003200000fd9001e0001011033"))
        assert state.fan_on
        assert not state.light_on
        assert state.brightness == 50

    def test_white_light_on(self):
        state = p.parse_status(bytes.fromhex("3a1105a04140002800000fd9001e00010110b5"))
        assert not state.fan_on
        assert state.light_on
        assert state.brightness == 40

    def test_wall_rgb_on(self):
        state = p.parse_status(bytes.fromhex("3a1105a04120000a00000fda001e0001011085"))
        assert state.wall_rgb_on
        assert not state.light_on
        assert state.brightness == 10

    def test_fan_and_wall_rgb(self):
        state = p.parse_status(bytes.fromhex("3a1105a041a0006400000fda001e00010110ef"))
        assert state.fan_on
        assert state.wall_rgb_on
        assert state.brightness == 100

    def test_fan_and_white_light(self):
        state = p.parse_status(bytes.fromhex("3a1105a041c0006400000fda001e00010110f8"))
        assert state.fan_on
        assert state.light_on
        assert state.brightness == 100

    def test_rejects_wrong_length(self):
        with pytest.raises(p.ChromaComfortProtocolError, match="expected 19 bytes"):
            p.parse_status(b"\x3a\x11\x05")

    def test_rejects_bad_header(self):
        frame = bytearray(UNIQUE[0])
        frame[0] = 0x00
        with pytest.raises(p.ChromaComfortProtocolError, match="bad header"):
            p.parse_status(bytes(frame))

    def test_rejects_command_frame(self):
        with pytest.raises(p.ChromaComfortProtocolError, match="not a status frame"):
            p.parse_status(p.build_command(p.CMD_FAN_ON))

    def test_rejects_corrupt_crc(self):
        frame = bytearray(UNIQUE[0])
        frame[18] ^= 0xFF
        with pytest.raises(p.ChromaComfortProtocolError, match="CRC mismatch"):
            p.parse_status(bytes(frame))

    def test_crc_check_can_be_disabled(self):
        frame = bytearray(UNIQUE[0])
        frame[18] ^= 0xFF
        assert p.parse_status(bytes(frame), verify_crc=False).mask == frame[5]

    def test_rejects_wrong_version_even_with_valid_crc(self):
        # A structurally valid frame from a peripheral speaking a different
        # dialect must not be trusted just because its CRC checks out.
        frame = bytearray(UNIQUE[0])
        frame[2] = 0x01
        frame[18] = p.frame_crc(bytes(frame))
        with pytest.raises(p.ChromaComfortProtocolError, match="bad version"):
            p.parse_status(bytes(frame))

    def test_rejects_out_of_range_brightness_even_with_valid_crc(self):
        # The dimmer field is 0-100; 255 here means a malfunctioning or hostile
        # device, not a brighter light.
        frame = bytearray(UNIQUE[0])
        frame[7] = 255
        frame[18] = p.frame_crc(bytes(frame))
        with pytest.raises(p.ChromaComfortProtocolError, match="brightness"):
            p.parse_status(bytes(frame))

    def test_accepts_all_mask_bits_set(self):
        # An impossible mode combination decodes without error -- each bit is
        # reported independently and downstream code treats them as booleans.
        frame = bytearray(UNIQUE[0])
        frame[5] = 0xFF
        frame[18] = p.frame_crc(bytes(frame))
        state = p.parse_status(bytes(frame))
        assert state.fan_on and state.light_on and state.user_pattern_on


class TestFrameClassification:
    @pytest.mark.parametrize("frame", UNIQUE, ids=lambda f: f.hex())
    def test_captured_frames_are_status(self, frame):
        assert p.is_status_frame(frame)
        assert not p.is_ack_frame(frame)

    def test_ack_recognised(self):
        assert p.is_ack_frame(bytes([0x3A, 0x11, 0x05, 0xA0, 0x40]))

    def test_command_is_neither(self):
        cmd = p.build_command(p.CMD_FAN_ON)
        assert not p.is_status_frame(cmd)
        assert not p.is_ack_frame(cmd)


class TestBuildCommand:
    def test_length_and_envelope(self):
        cmd = p.build_command(p.CMD_FAN_ON)
        assert len(cmd) == 19
        assert cmd[0] == 0x3A
        assert cmd[1] == 0x11
        assert cmd[2] == 0x01, "version must be 1 or the fan ignores the command"
        assert cmd[3] == 0x00
        assert cmd[4] == 0x40

    def test_field_offsets(self):
        cmd = p.build_command(p.CMD_FAVORITE_ON, red=1, green=2, blue=3, dimmer=55)
        assert cmd[5] == p.CMD_FAVORITE_ON
        assert (cmd[6], cmd[7], cmd[8]) == (1, 2, 3)
        assert cmd[9] == 55
        assert cmd[10] == 0, "speed must be zero on normal commands"
        assert cmd[11] == 0x01
        assert cmd[12] == 0x18
        assert cmd[13:] == bytes(6)

    def test_matches_reference_implementation(self):
        # Byte-for-byte against the reference ESP32 firmware's TxCmd struct:
        # header, len, ver=1, ctrl 00 40, type, r g b, dimmer, speed,
        # sweep 1/24, duration, four timers, trailer.
        assert p.build_command(p.CMD_FAN_ON) == bytes(
            [0x3A, 0x11, 0x01, 0x00, 0x40, 0x01, 0, 0, 0, 0, 0, 0x01, 0x18, 0, 0, 0, 0, 0, 0]
        )
        assert p.build_command(p.CMD_LIGHT_ON, dimmer=75) == bytes(
            [0x3A, 0x11, 0x01, 0x00, 0x40, 0x03, 0, 0, 0, 75, 0, 0x01, 0x18, 0, 0, 0, 0, 0, 0]
        )
        # Orange 255,165,4 goes out gamma-corrected as 255,44,0.
        assert p.save_favorite_color(0xFF, 0xA5, 0x04) == bytes(
            [0x3A, 0x11, 0x01, 0x00, 0x40, 0x0D, 0xFF, 44, 0, 0, 30, 0x01, 0x18, 0, 0, 0, 0, 0, 0]
        )

    def test_save_favorite_sets_speed(self):
        cmd = p.save_favorite_color(255, 165, 4)
        assert cmd[5] == p.CMD_SAVE_FAVORITE
        assert cmd[10] == p.SAVE_FAVORITE_SPEED

    def test_rgb_is_gamma_corrected(self):
        # Primaries are fixed points, which is why this went unnoticed until the
        # vendor app confirmed the gamma-4 encoding.
        assert p.save_favorite_color(255, 0, 255)[6:9] == bytes([255, 0, 255])
        assert p.save_favorite_color(255, 165, 4)[6:9] == bytes([255, 44, 0])

    @pytest.mark.parametrize("dimmer", [-1, 101, 255])
    def test_rejects_out_of_range_dimmer(self, dimmer):
        with pytest.raises(ValueError, match="dimmer must be 0-100"):
            p.build_command(p.CMD_LIGHT_ON, dimmer=dimmer)

    @pytest.mark.parametrize("field", ["red", "green", "blue"])
    def test_rejects_out_of_range_rgb(self, field):
        with pytest.raises(ValueError, match=f"{field} must be 0-255"):
            p.build_command(p.CMD_SAVE_FAVORITE, **{field: 256})


class TestGamma:
    def test_endpoints_are_fixed(self):
        assert p.apply_gamma(0) == 0
        assert p.apply_gamma(255) == 255

    def test_midtones_are_crushed(self):
        # This is why primaries looked correct before gamma was implemented and
        # mixed colours did not.
        assert p.apply_gamma(128) == 16
        assert p.apply_gamma(200) == 96

    def test_monotonic(self):
        values = [p.apply_gamma(v) for v in range(256)]
        assert values == sorted(values)

    def test_save_favorite_gamma_corrects(self):
        cmd = p.save_favorite_color(255, 128, 0)
        assert (cmd[6], cmd[7], cmd[8]) == (255, 16, 0)


class TestSceneFrames:
    def test_matches_vendor_app_output(self):
        # Reproduces the frames the vendor app emits for Sunrise, derived from
        # its decompiled bundle.
        first, second = p.scene_frames("Sunrise")
        assert first == bytes.fromhex("3a110100402aff0300ff2504ffa207ff030000")
        assert second == bytes.fromhex("3a11010040ff2504ffa207ff0300ff25040300")

    def test_first_frame_carries_opcode_second_does_not(self):
        first, second = p.scene_frames("Rainbow")
        assert first[5] == p.CMD_PATTERN_SAVE
        assert first[:5] == second[:5] == bytes([0x3A, 0x11, 0x01, 0x00, 0x40])

    def test_count_byte_holds_real_palette_length(self):
        for name, (colors, _) in p.BUILTIN_SCENES.items():
            _, second = p.scene_frames(name)
            assert second[17] == len(colors), name

    def test_short_palettes_repeat_cyclically(self):
        red, green, blue = (255, 0, 0), (0, 255, 0), (0, 0, 255)
        first, second = p.build_scene_frames([red, green, blue])
        # Eight slots filled from a three-colour palette: slots 0-3 in frame 1,
        # 4-7 in frame 2, each colors[slot % 3].
        assert (first[6], first[7], first[8]) == red
        assert (first[9], first[10], first[11]) == green
        assert (first[12], first[13], first[14]) == blue
        assert (first[15], first[16], first[17]) == red
        assert (second[5], second[6], second[7]) == green

    def test_all_frames_are_19_bytes(self):
        for name in p.BUILTIN_SCENES:
            first, second = p.scene_frames(name)
            assert len(first) == len(second) == 19, name

    @pytest.mark.parametrize("count", [0, 9, 20])
    def test_rejects_bad_palette_size(self, count):
        with pytest.raises(ValueError, match="1-8 colours"):
            p.build_scene_frames([(255, 0, 0)] * count)

    def test_hex_parsing(self):
        assert p.hex_to_rgb("#FF8000") == (255, 128, 0)
        assert p.hex_to_rgb("FFFFFF") == (255, 255, 255)


class TestSceneCatalogue:
    def test_app_scenes_present(self):
        assert set(p.APP_SCENES) == {
            "Sunset", "Sunrise", "Tropical Forest", "Rainbow",
            "Night Sky", "Underwater", "Northern Lights",
        }

    def test_catalogue_is_union(self):
        assert set(p.BUILTIN_SCENES) == set(p.APP_SCENES) | set(p.EXTRA_SCENES)

    def test_every_scene_is_valid(self):
        for name, (colors, cycle) in p.BUILTIN_SCENES.items():
            assert 1 <= len(colors) <= p.MAX_SCENE_COLORS, name
            assert 30 <= cycle <= 240 and cycle % 30 == 0, name
            for value in colors:
                assert len(value) == 7 and value[0] == "#", f"{name}: {value}"
                p.hex_to_rgb(value)

    def test_scenes_are_visually_distinct_after_gamma(self):
        # Gamma-4 can collapse similar palettes; make sure none encode identically.
        encoded = {name: p.scene_frames(name) for name in p.BUILTIN_SCENES}
        assert len(set(encoded.values())) == len(encoded)
