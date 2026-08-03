#!/usr/bin/env python3
"""Live probe for ChromaComfort fans. Development tool, not shipped with the integration.

    python tools/probe.py scan                     list nearby fans by signal strength
    python tools/probe.py dump   <address>         full GATT enumeration
    python tools/probe.py watch  <address>         subscribe and print decoded status
    python tools/probe.py send   <address> <cmd>   send a command, show the state change

Commands: fan_on fan_off light_on light_off rgb_on rgb_off fav_on fav_off
          bright:<0-100> color:<r,g,b>
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from bleak import BleakClient, BleakScanner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "chromacomfort"))

import protocol as p  # noqa: E402

SERVICE_UUID = "a08f7710-c37c-11e3-99cc-0228ac012a70"
WRITE_UUID = "bb8a27e0-c37c-11e3-b953-0228ac012a70"
NOTIFY_UUID = "b34ae89e-c37c-11e3-940e-0228ac012a70"

DEVICE_NAME = "Chroma-Comfort"
WRITE_REPEATS = 3
WRITE_GAP = 0.037


def describe(state: p.ChromaComfortState) -> str:
    modes = []
    if state.fan_on:
        modes.append("FAN")
    if state.light_on:
        modes.append("WHITE")
    if state.wall_rgb_on:
        modes.append("WALL-RGB")
    if state.rgb_sweep_on:
        modes.append("SWEEP")
    if state.favorite_1_on:
        modes.append("FAV1")
    if state.favorite_2_on:
        modes.append("FAV2")
    if state.user_pattern_on:
        modes.append("PATTERN")
    return f"mask=0x{state.mask:02x} bright={state.brightness:3d}  {' '.join(modes) or 'all off'}"


async def scan() -> None:
    print(f"Scanning 8s for {DEVICE_NAME!r}...\n")
    found = await BleakScanner.discover(timeout=8.0, return_adv=True)
    hits = [
        (dev, adv)
        for dev, adv in found.values()
        if (dev.name and DEVICE_NAME.lower() in dev.name.lower())
        or SERVICE_UUID in [u.lower() for u in adv.service_uuids]
    ]
    if not hits:
        print("No ChromaComfort fans found. Is the fan powered?")
        return
    for dev, adv in sorted(hits, key=lambda x: x[1].rssi, reverse=True):
        print(f"  {dev.address}  rssi={adv.rssi:4d} dBm  name={dev.name!r}")
    print("\nStrongest signal is the nearest fan. Pass its address to watch/send.")


async def dump(address: str) -> None:
    async with BleakClient(address, timeout=20.0) as client:
        print(f"Connected to {address}\n")
        for service in client.services:
            print(f"service {service.uuid}  ({service.description})")
            for char in service.characteristics:
                props = ",".join(char.properties)
                value = ""
                if "read" in char.properties:
                    try:
                        value = f"  = {bytes(await client.read_gatt_char(char)).hex()}"
                    except Exception as err:  # noqa: BLE001
                        value = f"  = <read failed: {type(err).__name__}>"
                print(f"    char {char.uuid}  handle=0x{char.handle:04x}  [{props}]{value}")
            print()


async def _subscribe(client: BleakClient, on_state) -> None:
    def handler(_sender, data: bytearray) -> None:
        frame = bytes(data)
        if p.is_ack_frame(frame) and not p.is_status_frame(frame):
            print(f"  ACK  {frame.hex()}")
            return
        try:
            on_state(p.parse_status(frame))
        except p.ChromaComfortProtocolError as err:
            print(f"  ?    {frame.hex()}  ({err})")

    await client.start_notify(NOTIFY_UUID, handler)


async def watch(address: str, seconds: float = 60.0) -> None:
    last = None

    def on_state(state: p.ChromaComfortState) -> None:
        nonlocal last
        key = (state.mask, state.brightness)
        if key != last:
            last = key
            print(f"  {describe(state)}")

    async with BleakClient(address, timeout=20.0) as client:
        print(f"Connected. Watching {seconds:.0f}s -- use the wall switch to see updates.\n")
        await _subscribe(client, on_state)
        await asyncio.sleep(seconds)


def parse_command(spec: str) -> tuple[str, bytes]:
    simple = {
        "fan_on": (p.CMD_FAN_ON, {}),
        "fan_off": (p.CMD_FAN_OFF, {}),
        "light_on": (p.CMD_LIGHT_ON, {}),
        "light_off": (p.CMD_LIGHT_OFF, {}),
        "rgb_on": (p.CMD_WALL_RGB_ON, {}),
        "rgb_off": (p.CMD_WALL_RGB_OFF, {}),
        "fav_on": (p.CMD_FAVORITE_ON, {}),
        "fav_off": (p.CMD_FAVORITE_OFF, {}),
    }
    if spec in simple:
        opcode, kwargs = simple[spec]
        return spec, p.build_command(opcode, **kwargs)
    if spec.startswith("bright:"):
        level = int(spec.split(":", 1)[1])
        return spec, p.build_command(p.CMD_LIGHT_ON, dimmer=level)
    if spec.startswith("color:"):
        r, g, b = (int(v) for v in spec.split(":", 1)[1].split(","))
        return spec, p.save_favorite_color(r, g, b)
    raise SystemExit(f"unknown command {spec!r}")


async def send(address: str, specs: list[str]) -> None:
    states: list[p.ChromaComfortState] = []

    async with BleakClient(address, timeout=20.0) as client:
        print(f"Connected to {address}")
        # Subscribing is what makes the fan start processing commands at all.
        await _subscribe(client, states.append)
        await asyncio.sleep(1.5)
        if states:
            print(f"  before: {describe(states[-1])}\n")

        for spec in specs:
            name, frame = parse_command(spec)
            print(f"-> {name}: {frame.hex()}")
            states.clear()
            # Write-without-response has no BLE-layer ack and the fan drops lone
            # writes, so the official app sends every frame three times.
            for _ in range(WRITE_REPEATS):
                await client.write_gatt_char(WRITE_UUID, frame, response=False)
                await asyncio.sleep(WRITE_GAP)
            await asyncio.sleep(3.5)
            print(f"   after: {describe(states[-1]) if states else 'no status received'}\n")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    action, rest = args[0], args[1:]
    if action == "scan":
        asyncio.run(scan())
    elif action == "dump":
        asyncio.run(dump(rest[0]))
    elif action == "watch":
        asyncio.run(watch(rest[0], float(rest[1]) if len(rest) > 1 else 60.0))
    elif action == "send":
        asyncio.run(send(rest[0], rest[1:]))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
