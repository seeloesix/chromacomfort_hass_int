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

from bleak.exc import BleakError  # noqa: E402
from homeassistant.components.fan import FanEntityFeature  # noqa: E402
from homeassistant.components.light import ColorMode  # noqa: E402
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError  # noqa: E402

from chromacomfort import protocol as p  # noqa: E402
from chromacomfort.config_flow import _display_name  # noqa: E402
from chromacomfort.fan import ChromaComfortFan  # noqa: E402
from chromacomfort.light import ChromaComfortColorLight, ChromaComfortWhiteLight  # noqa: E402
from chromacomfort.select import OPTION_OFF, ChromaComfortSceneSelect  # noqa: E402
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
        self.async_turn_color_off = AsyncMock()
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
            ChromaComfortSceneSelect(device).unique_id,
            ChromaComfortColorCycle(device).unique_id,
        }
        assert len(ids) == 5


class TestSceneSelect:
    def test_options_are_off_plus_every_scene(self):
        entity = ChromaComfortSceneSelect(StubDevice(make_state(0)))
        assert entity.options[0] == OPTION_OFF
        assert set(entity.options[1:]) == set(p.BUILTIN_SCENES)

    def test_reports_off_when_no_scene_runs(self):
        assert ChromaComfortSceneSelect(StubDevice(make_state(0))).current_option == OPTION_OFF
        assert (
            ChromaComfortSceneSelect(StubDevice(make_state(p.MASK_FAVORITE_1))).current_option
            == OPTION_OFF
        )

    def test_reports_running_scene(self):
        device = StubDevice(make_state(p.MASK_USER_PATTERN))
        device.scene = "Rainbow"
        assert ChromaComfortSceneSelect(device).current_option == "Rainbow"

    def test_reports_unknown_for_a_scene_started_by_the_app(self):
        # The fan does not say which scene is loaded; if playback started
        # outside Home Assistant, the honest answer is unknown.
        device = StubDevice(make_state(p.MASK_USER_PATTERN))
        device.scene = None
        assert ChromaComfortSceneSelect(device).current_option is None

    def test_unknown_before_first_status(self):
        assert ChromaComfortSceneSelect(StubDevice(None)).current_option is None

    async def test_selecting_a_scene_starts_it(self):
        device = StubDevice(make_state(0))
        entity = ChromaComfortSceneSelect(device)
        await entity.async_select_option("Christmas")
        device.async_set_scene.assert_awaited_with("Christmas")
        device.async_stop_scene.assert_not_awaited()

    async def test_selecting_off_stops_playback(self):
        device = StubDevice(make_state(p.MASK_USER_PATTERN))
        entity = ChromaComfortSceneSelect(device)
        await entity.async_select_option(OPTION_OFF)
        device.async_stop_scene.assert_awaited()
        device.async_set_scene.assert_not_awaited()

    async def test_transport_failure_surfaces_cleanly(self):
        device = StubDevice(make_state(0))
        device.async_set_scene.side_effect = BleakError("busy")
        entity = ChromaComfortSceneSelect(device)
        with pytest.raises(HomeAssistantError):
            await entity.async_select_option("Spa")



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

    async def test_turn_off_delegates_the_mode_decision_to_the_device(self):
        # The entity must not branch on its own cached state: that can predate a
        # change made from the phone app while we were disconnected.
        for mask in (p.MASK_USER_PATTERN, p.MASK_FAVORITE_1):
            device = StubDevice(make_state(mask))
            await ChromaComfortColorLight(device).async_turn_off()
            device.async_turn_color_off.assert_awaited()
            device.async_set_color_light.assert_not_awaited()
            device.async_stop_scene.assert_not_awaited()

    async def test_unknown_effect_raises_validation_error_not_keyerror(self):
        # HA passes the effect string through unvalidated; a typo in an
        # automation must surface as a clean service error.
        device = StubDevice(make_state(0))
        entity = ChromaComfortColorLight(device)
        with pytest.raises(ServiceValidationError):
            await entity.async_turn_on(effect="rainbow")  # wrong case on purpose
        device.async_set_scene.assert_not_awaited()


class TestTransportErrors:
    """BLE failures are routine (the phone app holds the fan) and must read
    as a clear message, not an unexpected-error traceback."""

    async def test_bleak_error_becomes_homeassistant_error(self):
        device = StubDevice(make_state(0))
        device.async_set_fan.side_effect = BleakError("connection busy")
        entity = ChromaComfortFan(device)
        with pytest.raises(HomeAssistantError):
            await entity.async_turn_on()

    async def test_timeout_becomes_homeassistant_error(self):
        device = StubDevice(make_state(0))
        device.async_set_wall_cycle.side_effect = TimeoutError()
        entity = ChromaComfortColorCycle(device)
        with pytest.raises(HomeAssistantError):
            await entity.async_turn_on()


class TestDiscoveryNameSanitisation:
    """The advertised name is attacker-controlled radio data and is rendered
    in the frontend's markdown dialogs."""

    def test_passthrough_for_the_real_name(self):
        assert _display_name("Chroma-Comfort 1234") == "Chroma-Comfort 1234"

    def test_none_and_empty_fall_back(self):
        assert _display_name(None) == "ChromaComfort"
        assert _display_name("") == "ChromaComfort"
        assert _display_name("[]()") == "ChromaComfort"

    def test_markdown_link_is_neutralised(self):
        cleaned = _display_name("Chroma-Comfort [Approve](https://evil.example)")
        assert "[" not in cleaned and "(" not in cleaned

    def test_length_is_bounded(self):
        assert len(_display_name("x" * 500)) <= 40

    def test_control_characters_stripped(self):
        assert _display_name("Chroma\x00\x1b[31mComfort") == "Chroma31mComfort"
