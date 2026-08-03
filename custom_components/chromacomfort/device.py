"""BLE transport for ChromaComfort fans.

The fan streams status notifications continuously while connected, so this holds
a persistent connection and pushes state to entities rather than polling.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
    close_stale_connections_by_address,
)

from . import protocol as p
from .const import (
    COMMAND_GAP,
    MAX_BRIGHTNESS,
    MIN_BRIGHTNESS,
    NOTIFY_CHAR_UUID,
    SCENE_STEP_GAP,
    WRITE_CHAR_UUID,
    WRITE_GAP,
    WRITE_REPEATS,
)

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 20.0
RECONNECT_DELAY = 10.0
STATUS_TIMEOUT = 5.0

# How long to wait for a command to show up in the fan's status, and how many
# times to resend before giving up.
CONFIRM_TIMEOUT = 1.5
CONFIRM_ATTEMPTS = 3


def brightness_to_device(value: int) -> int:
    """Convert Home Assistant's 0-255 brightness to the fan's 10-100 percent."""
    percent = round(value / 255 * MAX_BRIGHTNESS)
    return max(MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, percent))


def brightness_to_ha(value: int) -> int:
    """Convert the fan's 0-100 percent to Home Assistant's 0-255 brightness."""
    return max(0, min(255, round(value / MAX_BRIGHTNESS * 255)))


class ChromaComfortDevice:
    """Owns the BLE connection to one fan and fans state out to entities."""

    def __init__(self, ble_device: BLEDevice) -> None:
        self._ble_device = ble_device
        self._client: BleakClientWithServiceCache | None = None
        self._connect_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._callbacks: list[Callable[[], None]] = []
        self._state: p.ChromaComfortState | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._closing = False
        # The fan reports neither its RGB value nor which scene is loaded, so
        # track both locally.
        self._rgb: tuple[int, int, int] = (255, 255, 255)
        self._scene: str | None = None

    @property
    def address(self) -> str:
        return self._ble_device.address

    @property
    def name(self) -> str:
        return self._ble_device.name or "ChromaComfort"

    @property
    def state(self) -> p.ChromaComfortState | None:
        return self._state

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self._rgb

    @property
    def available(self) -> bool:
        return self._client is not None and self._client.is_connected and self._state is not None

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        """Refresh the BLEDevice from a new advertisement."""
        self._ble_device = ble_device

    def register_callback(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register an entity to be notified of state changes."""
        self._callbacks.append(callback)

        def unregister() -> None:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

        return unregister

    def _notify_callbacks(self) -> None:
        for callback in self._callbacks:
            callback()

    def _handle_notification(self, _sender, data: bytearray) -> None:
        frame = bytes(data)
        if not p.is_status_frame(frame):
            return
        try:
            state = p.parse_status(frame)
        except p.ChromaComfortProtocolError as err:
            _LOGGER.debug("Discarding malformed status frame %s: %s", frame.hex(), err)
            return
        if state != self._state:
            self._state = state
            self._notify_callbacks()

    def _handle_disconnect(self, _client) -> None:
        _LOGGER.debug("%s disconnected", self.address)
        self._client = None
        self._state = None
        self._notify_callbacks()
        if not self._closing:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        while not self._closing and self._client is None:
            await asyncio.sleep(RECONNECT_DELAY)
            if self._closing:
                return
            try:
                await self.connect()
            except (BleakError, asyncio.TimeoutError) as err:
                _LOGGER.debug("Reconnect to %s failed: %s", self.address, err)

    async def connect(self) -> None:
        """Establish the connection and subscribe to status notifications."""
        async with self._connect_lock:
            if self._client is not None and self._client.is_connected:
                return
            await close_stale_connections_by_address(self.address)
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self.name,
                self._handle_disconnect,
                use_services_cache=True,
                ble_device_callback=lambda: self._ble_device,
                timeout=CONNECT_TIMEOUT,
            )
            # Subscribing is not just how we read state -- the fan does not
            # process any commands until a client writes the status CCCD.
            await client.start_notify(NOTIFY_CHAR_UUID, self._handle_notification)
            self._client = client
            # The fan ignores commands sent in the window between the CCCD write
            # and it starting to stream. It reports several times a second, so
            # the first frame arriving is a reliable ready signal.
            try:
                async with asyncio.timeout(STATUS_TIMEOUT):
                    while self._state is None:
                        await asyncio.sleep(0.05)
            except asyncio.TimeoutError:
                _LOGGER.warning(
                    "Connected to %s but no status received in %.0fs",
                    self.address,
                    STATUS_TIMEOUT,
                )
            _LOGGER.debug("Connected to %s", self.address)

    async def stop(self) -> None:
        """Disconnect and stop reconnecting."""
        self._closing = True
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        if self._client is not None:
            try:
                await self._client.disconnect()
            except BleakError as err:
                _LOGGER.debug("Error disconnecting %s: %s", self.address, err)
            self._client = None

    async def _send(self, frame: bytes) -> None:
        """Write a command frame, repeated to survive the unreliable transport."""
        async with self._write_lock:
            if self._client is None or not self._client.is_connected:
                await self.connect()
            client = self._client
            if client is None:
                raise BleakError(f"Not connected to {self.address}")
            for index in range(WRITE_REPEATS):
                await client.write_gatt_char(WRITE_CHAR_UUID, frame, response=False)
                if index < WRITE_REPEATS - 1:
                    await asyncio.sleep(WRITE_GAP)

    async def _confirmed(
        self, frame: bytes, expected: Callable[[p.ChromaComfortState], bool]
    ) -> None:
        """Send a command and resend until the fan's own status agrees.

        Write-without-response has no delivery guarantee and the fan does
        occasionally miss a command even with the triple write. It reports status
        several times a second, so we can just watch for the change and retry.
        """
        for attempt in range(CONFIRM_ATTEMPTS):
            await self._send(frame)
            deadline = asyncio.get_running_loop().time() + CONFIRM_TIMEOUT
            while asyncio.get_running_loop().time() < deadline:
                if self._state is not None and expected(self._state):
                    return
                await asyncio.sleep(0.05)
            _LOGGER.debug(
                "Command %s not reflected in status, attempt %d of %d",
                frame.hex(),
                attempt + 1,
                CONFIRM_ATTEMPTS,
            )
        _LOGGER.warning("Fan %s did not apply command %s", self.address, frame.hex())

    async def async_set_fan(self, on: bool) -> None:
        await self._confirmed(
            p.build_command(p.CMD_FAN_ON if on else p.CMD_FAN_OFF),
            lambda state: state.fan_on is on,
        )

    async def async_set_white_light(self, on: bool, brightness: int | None = None) -> None:
        if not on:
            await self._confirmed(
                p.build_command(p.CMD_LIGHT_OFF), lambda state: not state.light_on
            )
            return
        dimmer = brightness_to_device(brightness) if brightness is not None else 0
        await self._confirmed(
            p.build_command(p.CMD_LIGHT_ON, dimmer=dimmer),
            lambda state: state.light_on and (dimmer == 0 or state.brightness == dimmer),
        )

    async def async_set_color_light(
        self,
        on: bool,
        brightness: int | None = None,
        rgb: tuple[int, int, int] | None = None,
    ) -> None:
        if not on:
            await self._confirmed(
                p.build_command(p.CMD_FAVORITE_OFF), lambda state: not state.favorite_1_on
            )
            return
        if rgb is not None:
            self._rgb = rgb
            # Saving a colour produces no status change, so it cannot be
            # confirmed; send it and give the fan time before activating.
            await self._send(p.save_favorite_color(*rgb))
            await asyncio.sleep(COMMAND_GAP)
        dimmer = brightness_to_device(brightness) if brightness is not None else 0
        await self._confirmed(
            p.build_command(p.CMD_FAVORITE_ON, dimmer=dimmer),
            lambda state: state.favorite_1_on and (dimmer == 0 or state.brightness == dimmer),
        )

    async def async_set_wall_cycle(self, on: bool) -> None:
        await self._confirmed(
            p.build_command(p.CMD_WALL_RGB_ON if on else p.CMD_WALL_RGB_OFF),
            lambda state: state.wall_rgb_on is on,
        )

    async def async_stop_scene(self) -> None:
        """Stop scene playback."""
        await self._confirmed(
            p.build_command(p.CMD_PATTERN_OFF), lambda state: not state.user_pattern_on
        )
        self._scene = None

    async def async_set_scene(self, name: str, brightness: int | None = None) -> None:
        """Upload a scene's palette to the fan and start playing it.

        Three steps, matching the vendor app: stop any running scene, write the
        colour pair, then activate. The fan stores one scene at a time, so
        switching scenes means re-uploading.
        """
        first, second = p.scene_frames(name)
        dimmer = brightness_to_device(brightness) if brightness is not None else MAX_BRIGHTNESS

        await self._send(p.build_command(p.CMD_PATTERN_OFF, dimmer=MIN_BRIGHTNESS))
        await asyncio.sleep(SCENE_STEP_GAP)

        # The two frames are a unit -- the second carries colour data where the
        # opcode would be, so it only means anything directly after the first.
        # The app writes the pair three times rather than each frame three
        # times, and waits for no acknowledgement.
        async with self._write_lock:
            if self._client is None or not self._client.is_connected:
                await self.connect()
            client = self._client
            if client is None:
                raise BleakError(f"Not connected to {self.address}")
            for _ in range(WRITE_REPEATS):
                await client.write_gatt_char(WRITE_CHAR_UUID, first, response=False)
                await asyncio.sleep(WRITE_GAP)
                await client.write_gatt_char(WRITE_CHAR_UUID, second, response=False)
                await asyncio.sleep(WRITE_GAP)
        await asyncio.sleep(SCENE_STEP_GAP)

        await self._confirmed(
            p.build_command(
                p.CMD_PATTERN_ON, dimmer=dimmer, speed=p.scene_cycle_seconds(name)
            ),
            lambda state: state.user_pattern_on,
        )
        self._scene = name

    @property
    def scene(self) -> str | None:
        """The scene we last started, or None. The fan does not report this."""
        return self._scene
