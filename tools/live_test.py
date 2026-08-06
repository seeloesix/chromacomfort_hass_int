#!/usr/bin/env python3
"""End-to-end test of the shipped device layer against a real fan.

Exercises exactly the code path the Home Assistant integration uses, including
the callback fan-out and brightness conversions, then restores the fan to off.

    python tools/live_test.py <address>
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from bleak import BleakScanner

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "chromacomfort"

# Load device.py as part of a synthetic package. The real package __init__ pulls
# in Home Assistant, which isn't installed here -- but device.py itself has no HA
# dependency, which is exactly what makes this test possible.
import importlib.util  # noqa: E402
import types  # noqa: E402

_pkg = types.ModuleType("cc")
_pkg.__path__ = [str(COMPONENT)]
sys.modules["cc"] = _pkg
for _name in ("protocol", "const", "device"):
    _spec = importlib.util.spec_from_file_location(f"cc.{_name}", COMPONENT / f"{_name}.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[f"cc.{_name}"] = _mod
    _spec.loader.exec_module(_mod)

ChromaComfortDevice = sys.modules["cc.device"].ChromaComfortDevice
brightness_to_device = sys.modules["cc.device"].brightness_to_device
brightness_to_ha = sys.modules["cc.device"].brightness_to_ha

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))
    print(f"  [{PASS if ok else FAIL}] {name}{'  ' + detail if detail else ''}")


async def settle(device: ChromaComfortDevice, seconds: float = 3.5) -> None:
    await asyncio.sleep(seconds)


async def main(address: str) -> int:
    print("Conversion helpers")
    check("brightness_to_device(255) == 100", brightness_to_device(255) == 100)
    check("brightness_to_device(0) clamps to 10", brightness_to_device(0) == 10)
    check("brightness_to_device(128) == 50", brightness_to_device(128) == 50)
    check("brightness_to_ha(100) == 255", brightness_to_ha(100) == 255)

    print(f"\nConnecting to {address}")
    ble_device = await BleakScanner.find_device_by_address(address, timeout=15.0)
    if ble_device is None:
        print(f"  Could not find {address}")
        return 1

    device = ChromaComfortDevice(ble_device)
    updates = 0

    def on_update() -> None:
        nonlocal updates
        updates += 1

    device.register_callback(on_update)
    await device.connect()
    await settle(device, 2.0)

    check("connected and reporting status", device.available)
    check("callback fired on first status", updates > 0, f"({updates} updates)")
    print(f"  initial state: {device.state}")

    try:
        print("\nFan")
        await device.async_set_fan(True)
        await settle(device)
        check("fan reports on", bool(device.state and device.state.fan_on))
        await device.async_set_fan(False)
        await settle(device)
        check("fan reports off", bool(device.state and not device.state.fan_on))

        print("\nWhite light")
        await device.async_set_white_light(True, brightness=255)
        await settle(device)
        check("white light on", bool(device.state and device.state.light_on))
        check(
            "brightness reports 255",
            bool(device.state and brightness_to_ha(device.state.brightness) == 255),
            f"(device={device.state.brightness}%)",
        )
        await device.async_set_white_light(True, brightness=64)
        await settle(device)
        check(
            "dimmed to ~25%",
            bool(device.state and 20 <= device.state.brightness <= 30),
            f"(device={device.state.brightness}%)",
        )
        await device.async_set_white_light(False)
        await settle(device)
        check("white light off", bool(device.state and not device.state.light_on))

        print("\nColor light")
        await device.async_set_color_light(True, brightness=200, rgb=(0, 255, 128))
        await settle(device)
        check("color light on", bool(device.state and device.state.favorite_1_on))
        check("rgb tracked locally", device.rgb == (0, 255, 128), f"{device.rgb}")
        await device.async_set_color_light(False)
        await settle(device)
        check("color light off", bool(device.state and not device.state.favorite_1_on))

        print("\nColor cycle")
        await device.async_set_wall_cycle(True)
        await settle(device)
        check("cycle on", bool(device.state and device.state.wall_rgb_on))
        await device.async_set_wall_cycle(False)
        await settle(device)
        check("cycle off", bool(device.state and not device.state.wall_rgb_on))

        print("\nScenes")
        await device.async_set_scene("Halloween", brightness=255)
        await settle(device)
        check("scene playing", bool(device.state and device.state.user_pattern_on))
        check("scene name tracked", device.scene == "Halloween", f"{device.scene}")
        await device.async_set_scene("Rainbow", brightness=255)
        await settle(device)
        check("switched scene", device.scene == "Rainbow" and bool(device.state and device.state.user_pattern_on))
        await device.async_stop_scene()
        await settle(device)
        check("scene stopped", bool(device.state and not device.state.user_pattern_on))
        check("scene name cleared", device.scene is None)

        print("\nConnection release (the whole point of v1.2)")
        await device.async_set_fan(True)
        check("connected during an operation", device.connected)
        released = False
        for _ in range(40):  # DISCONNECT_DELAY is 5s; allow 20s
            await asyncio.sleep(0.5)
            if not device.connected:
                released = True
                break
        check("connection released after idle", released)
        check("state retained while disconnected", device.state is not None)
        check("still available while disconnected", device.available)
        check("fan state still correct", bool(device.state and device.state.fan_on))
        await device.async_set_fan(False)
        check("reconnects for the next command", bool(device.state and not device.state.fan_on))

        print("\nMutual exclusivity")
        await device.async_set_white_light(True, brightness=255)
        await settle(device)
        await device.async_set_color_light(True, brightness=255)
        await settle(device)
        check(
            "color light replaces white light",
            bool(device.state and device.state.favorite_1_on and not device.state.light_on),
        )
        await device.async_set_color_light(False)
        await settle(device)
    finally:
        await device.stop()

    failed = [r for r in results if r[0] == FAIL]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    for _, name, detail in failed:
        print(f"  FAILED: {name} {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1])))
