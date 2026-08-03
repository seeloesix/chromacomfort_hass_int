"""Entity behaviour tests against the real Home Assistant classes.

Skipped automatically when Home Assistant isn't installed, so the protocol suite
still runs in a bare environment.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("homeassistant")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components"))

from homeassistant.components.fan import FanEntityFeature  # noqa: E402
from homeassistant.components.light import ColorMode  # noqa: E402

from chromacomfort import protocol as p  # noqa: E402
from chromacomfort.fan import ChromaComfortFan  # noqa: E402
from chromacomfort.light import ChromaComfortColorLight, ChromaComfortWhiteLight  # noqa: E402
from chromacomfort.switch import ChromaComfortColorCycle  # noqa: E402

ADDRESS = "AA:BB:CC:DD:EE:FF"


def make_state(mask: int, brightness: int = 50) -> p.ChromaComfortState:
    frame = bytearray(bytes.fromhex("3a1105a04100003200000fd9001e0001011000"))
    frame[5] = mask
    frame[7] = brightness
    frame[18] = p.frame_crc(bytes(frame))
    return p.parse_status(bytes(frame))


class StubDevice:
    """Stands in for ChromaComfortDevice without touching Bluetooth."""

    def __init__(self, state: p.ChromaComfortState | None = None) -> None:
        self.address = ADDRESS
        self.name = "Chroma-Comfort"
        self.state = state
        self.available = state is not None
        self.rgb = (10, 20, 30)
        self.async_set_fan = AsyncMock()
        self.async_set_white_light = AsyncMock()
        self.async_set_color_light = AsyncMock()
        self.async_set_wall_cycle = AsyncMock()
        self.async_set_scene = AsyncMock()
        self.async_stop_scene = AsyncMock()
        self.scene = None

    def register_callback(self, callback):
        return lambda: None


class TestFan:
    def test_features_and_identity(self):
        entity = ChromaComfortFan(StubDevice(make_state(0)))
        assert entity.unique_id == f"{ADDRESS}_fan"
        assert entity.supported_features & FanEntityFeature.TURN_ON
        assert entity.supported_features & FanEntityFeature.TURN_OFF
        assert entity.device_info["identifiers"] == {("chromacomfort", ADDRESS)}

    def test_reflects_state(self):
        assert ChromaComfortFan(StubDevice(make_state(p.MASK_FAN))).is_on is True
        assert ChromaComfortFan(StubDevice(make_state(0))).is_on is False

    def test_unknown_and_unavailable_before_first_status(self):
        entity = ChromaComfortFan(StubDevice(None))
        assert entity.is_on is None
        assert entity.available is False

    async def test_turn_on_off(self):
        device = StubDevice(make_state(0))
        entity = ChromaComfortFan(device)
        await entity.async_turn_on()
        device.async_set_fan.assert_awaited_with(True)
        await entity.async_turn_off()
        device.async_set_fan.assert_awaited_with(False)


class TestWhiteLight:
    def test_color_mode(self):
        entity = ChromaComfortWhiteLight(StubDevice(make_state(0)))
        assert entity.supported_color_modes == {ColorMode.BRIGHTNESS}
        assert entity.unique_id == f"{ADDRESS}_white_light"

    def test_brightness_scales_to_ha_range(self):
        entity = ChromaComfortWhiteLight(StubDevice(make_state(p.MASK_LIGHT, 100)))
        assert entity.is_on is True
        assert entity.brightness == 255

    def test_off_when_color_light_active(self):
        entity = ChromaComfortWhiteLight(StubDevice(make_state(p.MASK_FAVORITE_1)))
        assert entity.is_on is False

    async def test_turn_on_passes_brightness(self):
        device = StubDevice(make_state(0))
        entity = ChromaComfortWhiteLight(device)
        await entity.async_turn_on(brightness=128)
        device.async_set_white_light.assert_awaited_with(True, 128)


class TestColorLight:
    def test_color_mode(self):
        entity = ChromaComfortColorLight(StubDevice(make_state(0)))
        assert entity.supported_color_modes == {ColorMode.RGB}
        assert entity.unique_id == f"{ADDRESS}_color_light"

    def test_tracks_favorite_bit_not_white_bit(self):
        assert ChromaComfortColorLight(StubDevice(make_state(p.MASK_FAVORITE_1))).is_on is True
        assert ChromaComfortColorLight(StubDevice(make_state(p.MASK_LIGHT))).is_on is False

    def test_rgb_comes_from_device_memory(self):
        entity = ChromaComfortColorLight(StubDevice(make_state(p.MASK_FAVORITE_1)))
        assert entity.rgb_color == (10, 20, 30)

    async def test_turn_on_passes_brightness_and_color(self):
        device = StubDevice(make_state(0))
        entity = ChromaComfortColorLight(device)
        await entity.async_turn_on(brightness=200, rgb_color=(1, 2, 3))
        device.async_set_color_light.assert_awaited_with(True, 200, (1, 2, 3))


class TestColorCycle:
    def test_tracks_wall_rgb_bit(self):
        assert ChromaComfortColorCycle(StubDevice(make_state(p.MASK_WALL_RGB))).is_on is True
        assert ChromaComfortColorCycle(StubDevice(make_state(0))).is_on is False

    async def test_turn_on_off(self):
        device = StubDevice(make_state(0))
        entity = ChromaComfortColorCycle(device)
        await entity.async_turn_on()
        device.async_set_wall_cycle.assert_awaited_with(True)
        await entity.async_turn_off()
        device.async_set_wall_cycle.assert_awaited_with(False)


class TestUniqueIds:
    def test_all_entities_have_distinct_ids(self):
        device = StubDevice(make_state(0))
        ids = {
            ChromaComfortFan(device).unique_id,
            ChromaComfortWhiteLight(device).unique_id,
            ChromaComfortColorLight(device).unique_id,
            ChromaComfortColorCycle(device).unique_id,
        }
        assert len(ids) == 4



class TestColorLightEffects:
    def test_effect_list_covers_all_scenes(self):
        entity = ChromaComfortColorLight(StubDevice(make_state(0)))
        assert set(entity.effect_list) == set(p.BUILTIN_SCENES)
        assert len(entity.effect_list) == 19

    def test_on_when_either_solid_or_scene_active(self):
        assert ChromaComfortColorLight(StubDevice(make_state(p.MASK_FAVORITE_1))).is_on is True
        assert ChromaComfortColorLight(StubDevice(make_state(p.MASK_USER_PATTERN))).is_on is True
        assert ChromaComfortColorLight(StubDevice(make_state(0))).is_on is False

    def test_effect_reported_only_while_scene_runs(self):
        device = StubDevice(make_state(p.MASK_USER_PATTERN))
        device.scene = "Rainbow"
        assert ChromaComfortColorLight(device).effect == "Rainbow"

        solid = StubDevice(make_state(p.MASK_FAVORITE_1))
        solid.scene = "Rainbow"
        assert ChromaComfortColorLight(solid).effect is None

    async def test_turn_on_with_effect_starts_scene(self):
        device = StubDevice(make_state(0))
        entity = ChromaComfortColorLight(device)
        await entity.async_turn_on(effect="Christmas", brightness=200)
        device.async_set_scene.assert_awaited_with("Christmas", 200)
        device.async_set_color_light.assert_not_awaited()

    async def test_turn_on_with_color_leaves_scene_mode(self):
        device = StubDevice(make_state(p.MASK_USER_PATTERN))
        entity = ChromaComfortColorLight(device)
        await entity.async_turn_on(rgb_color=(1, 2, 3))
        device.async_set_color_light.assert_awaited_with(True, None, (1, 2, 3))
        device.async_set_scene.assert_not_awaited()

    async def test_turn_off_stops_whichever_mode_is_running(self):
        scene = StubDevice(make_state(p.MASK_USER_PATTERN))
        await ChromaComfortColorLight(scene).async_turn_off()
        scene.async_stop_scene.assert_awaited()

        solid = StubDevice(make_state(p.MASK_FAVORITE_1))
        await ChromaComfortColorLight(solid).async_turn_off()
        solid.async_set_color_light.assert_awaited_with(False)
