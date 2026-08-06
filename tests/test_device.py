"""Connection lifecycle tests.

The fan allows one Bluetooth connection at a time and the vendor phone app needs
it too, so the rules these cover are what let the two coexist: never reconnect on
our own initiative, release promptly, and keep reporting state while detached.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "chromacomfort"

# Load device.py without the package __init__, which imports Home Assistant.
_pkg = types.ModuleType("ccdev")
_pkg.__path__ = [str(COMPONENT)]
sys.modules["ccdev"] = _pkg
for _name in ("protocol", "const", "device"):
    _spec = importlib.util.spec_from_file_location(f"ccdev.{_name}", COMPONENT / f"{_name}.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[f"ccdev.{_name}"] = _mod
    _spec.loader.exec_module(_mod)

device_mod = sys.modules["ccdev.device"]
p = sys.modules["ccdev.protocol"]
ChromaComfortDevice = device_mod.ChromaComfortDevice


def status_frame(mask: int = 0, brightness: int = 50) -> bytearray:
    frame = bytearray(bytes.fromhex("3a1105a04100003200000fd9001e0001011000"))
    frame[5] = mask
    frame[7] = brightness
    frame[18] = p.frame_crc(bytes(frame))
    return frame


class FakeBLEDevice:
    address = "AA:BB:CC:DD:EE:FF"
    name = "Chroma-Comfort"


def make_device(present: bool = True) -> ChromaComfortDevice:
    return ChromaComfortDevice(FakeBLEDevice(), presence_check=lambda: present)


class TestNoAutomaticReconnect:
    """The bug that made the phone app unusable was an unconditional retry loop."""

    def test_disconnect_does_not_schedule_anything(self):
        device = make_device()
        device._client = object()
        device._handle_disconnect(None)
        assert device._client is None
        # Nothing may be armed to grab the connection back.
        assert device._release_timer is None
        assert not hasattr(device, "_reconnect_task")

    def test_no_reconnect_machinery_exists(self):
        # Guards against the loop being reintroduced under another name.
        assert not hasattr(ChromaComfortDevice, "_reconnect")
        assert not hasattr(ChromaComfortDevice, "_schedule_reconnect")


class TestStateSurvivesDisconnect:
    def test_state_retained_so_entities_keep_their_values(self):
        device = make_device()
        device._handle_notification(None, status_frame(p.MASK_FAN))
        assert device.state is not None and device.state.fan_on

        device._handle_disconnect(None)
        assert device.state is not None, "state must outlive the connection"
        assert device.state.fan_on

    def test_available_while_disconnected_if_advertising(self):
        device = make_device(present=True)
        device._handle_notification(None, status_frame())
        device._handle_disconnect(None)
        assert device.connected is False
        assert device.available is True

    def test_unavailable_when_not_advertising(self):
        device = make_device(present=False)
        device._handle_notification(None, status_frame())
        assert device.available is False

    def test_unavailable_before_any_status(self):
        device = make_device(present=True)
        assert device.available is False


class TestReadiness:
    """The fan ignores commands until it starts streaming after a subscribe."""

    def test_ready_set_by_any_frame_even_an_unchanged_one(self):
        device = make_device()
        device._handle_notification(None, status_frame(p.MASK_FAN))
        device._ready.clear()
        # Same state as before: no change to publish, but the fan is streaming.
        device._handle_notification(None, status_frame(p.MASK_FAN))
        assert device._ready.is_set()

    def test_retained_state_does_not_imply_readiness(self):
        device = make_device()
        device._handle_notification(None, status_frame(p.MASK_FAN))
        device._handle_disconnect(None)
        assert device.state is not None
        assert not device._ready.is_set(), "stale state must not look like a live stream"

    def test_malformed_frames_ignored(self):
        device = make_device()
        device._handle_notification(None, bytearray(b"\x00\x01\x02"))
        assert device.state is None
        assert not device._ready.is_set()

    def test_corrupt_crc_ignored(self):
        device = make_device()
        frame = status_frame(p.MASK_FAN)
        frame[18] ^= 0xFF
        device._handle_notification(None, frame)
        assert device.state is None


class TestReleaseTimer:
    async def test_release_is_scheduled_after_an_operation(self):
        device = make_device()
        device._client = types.SimpleNamespace(is_connected=True)
        device._schedule_release()
        assert device._release_timer is not None
        device._cancel_release()

    async def test_new_operation_cancels_a_pending_release(self):
        device = make_device()
        device._client = types.SimpleNamespace(is_connected=True)
        device._schedule_release()
        pending = device._release_timer
        assert pending is not None

        device._cancel_release()
        assert device._release_timer is None
        assert pending.cancelled()

    async def test_no_release_scheduled_when_already_disconnected(self):
        device = make_device()
        device._client = None
        device._schedule_release()
        assert device._release_timer is None

    async def test_no_release_scheduled_while_closing(self):
        device = make_device()
        device._client = types.SimpleNamespace(is_connected=True)
        device._closing = True
        device._schedule_release()
        assert device._release_timer is None

    def test_delay_is_short_enough_to_hand_the_fan_back(self):
        assert 0 < device_mod.DISCONNECT_DELAY <= 15


class TestCallbacks:
    def test_entities_notified_on_change_and_on_disconnect(self):
        device = make_device()
        calls = []
        device.register_callback(lambda: calls.append(1))

        device._handle_notification(None, status_frame(p.MASK_FAN))
        assert len(calls) == 1
        device._handle_notification(None, status_frame(p.MASK_FAN))
        assert len(calls) == 1, "unchanged state should not churn entity updates"
        device._handle_notification(None, status_frame(p.MASK_LIGHT))
        assert len(calls) == 2
        device._handle_disconnect(None)
        assert len(calls) == 3, "availability may change, so entities need telling"

    def test_unregister(self):
        device = make_device()
        calls = []
        unregister = device.register_callback(lambda: calls.append(1))
        unregister()
        device._handle_notification(None, status_frame(p.MASK_FAN))
        assert calls == []


class TestCachedValues:
    def test_rgb_and_scene_survive_disconnect(self):
        device = make_device()
        device._rgb = (1, 2, 3)
        device._scene = "Rainbow"
        device._handle_disconnect(None)
        assert device.rgb == (1, 2, 3)
        assert device.scene == "Rainbow"
