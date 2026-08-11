"""BLE transport for ChromaComfort fans.

The fan accepts only one Bluetooth connection at a time, and the vendor phone app
needs it too. So this connects only when there is something to do and releases a
few seconds later, rather than holding the link. Between operations Home
Assistant keeps the last state it saw and tracks the fan by advertisement.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Callable

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    close_stale_connections_by_address,
    establish_connection,
)

from . import protocol as p
from .const import (
    COMMAND_GAP,
    DISCONNECT_DELAY,
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
STATUS_TIMEOUT = 5.0

# Ceiling on any single GATT operation. Without it a peripheral that accepts the
# connection but stops servicing requests wedges the operation lock forever,
# taking every entity with it until Home Assistant restarts.
BLE_OP_TIMEOUT = 10.0

# How long to wait for a command to show up in the fan's status, and how many
# times to resend before giving up.
CONFIRM_TIMEOUT = 1.5
CONFIRM_ATTEMPTS = 3

# Floor between entity update fan-outs. The fan itself reports about once a
# second; anything faster is a misbehaving or hostile peripheral, which must not
# be able to flood the Home Assistant event bus through us.
NOTIFY_MIN_INTERVAL = 0.25


def brightness_to_device(value: int) -> int:
    """Convert Home Assistant's 0-255 brightness to the fan's 10-100 percent."""
    percent = round(value / 255 * MAX_BRIGHTNESS)
    return max(MIN_BRIGHTNESS, min(MAX_BRIGHTNESS, percent))


def brightness_to_ha(value: int) -> int:
    """Convert the fan's 0-100 percent to Home Assistant's 0-255 brightness."""
    return max(0, min(255, round(value / MAX_BRIGHTNESS * 255)))


class ChromaComfortDevice:
    """Talks to one fan, holding the connection only while it is needed."""

    def __init__(
        self,
        ble_device: BLEDevice,
        presence_check: Callable[[], bool] | None = None,
    ) -> None:
        self._ble_device = ble_device
        # Answers "is the fan advertising?" without connecting. Entities use it
        # for availability, since we are disconnected most of the time.
        self._presence_check = presence_check
        self._client: BleakClientWithServiceCache | None = None
        self._connect_lock = asyncio.Lock()
        # Serialises whole command sequences, not individual writes: a scene
        # upload is several writes with pauses between and must not interleave.
        self._operation_lock = asyncio.Lock()
        self._callbacks: list[Callable[[], None]] = []
        self._state: p.ChromaComfortState | None = None
        self._release_timer: asyncio.TimerHandle | None = None
        # Strong references, because asyncio itself only keeps weak ones. The
        # generation counter lets a new operation void a release that is already
        # past its timer but still waiting on the operation lock.
        self._release_tasks: set[asyncio.Task] = set()
        self._release_generation = 0
        self._notify_flush_timer: asyncio.TimerHandle | None = None
        self._last_notify = 0.0
        self._closing = False
        # Set when a status frame arrives on the current connection. Cleared on
        # every connect, because retained state must not be mistaken for the fan
        # having started streaming again.
        self._ready = asyncio.Event()
        # The fan reports neither its RGB value nor which scene is loaded, so
        # track both locally. Like _state, these survive a disconnect.
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
        """The last status the fan reported, which may predate the last command."""
        return self._state

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self._rgb

    @property
    def scene(self) -> str | None:
        """The scene we last started, or None. The fan does not report this."""
        return self._scene

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def busy(self) -> bool:
        """True while a command sequence or refresh holds the operation lock."""
        return self._operation_lock.locked()

    @property
    def available(self) -> bool:
        """Available when the fan is in range and we have seen its state.

        Deliberately not tied to holding a connection -- we release it after
        every operation, so that would leave entities unavailable almost always.
        """
        if self._state is None:
            return False
        if self._presence_check is None:
            return True
        return self._presence_check()

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
        # Iterate a copy with per-callback isolation: one raising entity must not
        # silence the others, and a callback that unregisters during the fan-out
        # must not shift the list under the loop.
        for callback in list(self._callbacks):
            try:
                callback()
            except Exception:  # noqa: BLE001 - isolate misbehaving subscribers
                _LOGGER.exception("State callback for %s failed", self.address)

    def _dispatch_state_change(self) -> None:
        """Fan out a state change, rate-limited to NOTIFY_MIN_INTERVAL.

        Trailing-edge: a burst inside the window schedules exactly one flush at
        its end, so the final state always lands but a peripheral streaming
        alternating frames cannot drive unbounded event-bus churn.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No loop means no bleak and no event bus to protect (direct calls
            # from synchronous tests); deliver immediately.
            self._notify_callbacks()
            return
        now = loop.time()
        if now - self._last_notify >= NOTIFY_MIN_INTERVAL:
            self._last_notify = now
            self._notify_callbacks()
        elif self._notify_flush_timer is None:
            delay = NOTIFY_MIN_INTERVAL - (now - self._last_notify)
            self._notify_flush_timer = loop.call_later(delay, self._flush_notify)

    def _flush_notify(self) -> None:
        self._notify_flush_timer = None
        self._last_notify = asyncio.get_running_loop().time()
        self._notify_callbacks()

    def _handle_notification(self, _sender, data: bytearray) -> None:
        frame = bytes(data)
        if not p.is_status_frame(frame):
            return
        try:
            state = p.parse_status(frame)
        except p.ChromaComfortProtocolError as err:
            _LOGGER.debug("Discarding malformed status frame %s: %s", frame.hex(), err)
            return
        # Signal readiness on every frame, not just changed ones: the first frame
        # of a session often matches the state we retained, and that still means
        # the fan has started streaming and will now accept commands.
        self._ready.set()
        if state != self._state:
            self._state = state
            self._dispatch_state_change()

    def _handle_disconnect(self, _client) -> None:
        """Note the link is gone. Deliberately does not reconnect.

        Reconnecting here is what previously made the fan unusable from the
        vendor app: the fan allows a single connection, so an automatic retry
        loop permanently contests it.
        """
        _LOGGER.debug("%s disconnected", self.address)
        self._client = None
        self._ready.clear()
        # _state is kept on purpose so entities keep their last known values.
        self._notify_callbacks()

    async def connect(self) -> None:
        """Connect, subscribe, and wait until the fan is actually streaming."""
        async with self._connect_lock:
            if self.connected:
                return
            self._ready.clear()
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
            try:
                async with asyncio.timeout(BLE_OP_TIMEOUT):
                    await client.start_notify(NOTIFY_CHAR_UUID, self._handle_notification)
            except asyncio.TimeoutError as err:
                await self._disconnect_client(client)
                raise BleakError(f"Subscribing to {self.address} timed out") from err
            if not client.is_connected:
                # The fan dropped the link mid-handshake; _handle_disconnect has
                # already run, so installing this handle would resurrect a dead
                # connection.
                raise BleakError(f"{self.address} disconnected during setup")
            self._client = client
            try:
                async with asyncio.timeout(STATUS_TIMEOUT):
                    await self._ready.wait()
            except asyncio.TimeoutError as err:
                # Commands sent now would be silently ignored, so fail loudly
                # rather than let the caller burn its retries against a fan that
                # is not listening.
                await self._disconnect_client(client)
                raise BleakError(
                    f"Connected to {self.address} but it never started reporting status"
                ) from err
            _LOGGER.debug("Connected to %s", self.address)

    async def _disconnect_client(self, client: BleakClientWithServiceCache) -> None:
        """Unsubscribe and drop the link, tolerating a already-dead connection."""
        with contextlib.suppress(BleakError, EOFError, asyncio.TimeoutError):
            async with asyncio.timeout(BLE_OP_TIMEOUT):
                await client.stop_notify(NOTIFY_CHAR_UUID)
        with contextlib.suppress(BleakError, EOFError, asyncio.TimeoutError):
            async with asyncio.timeout(BLE_OP_TIMEOUT):
                await client.disconnect()
        if self._client is client:
            self._client = None
            self._ready.clear()

    def _cancel_release(self) -> None:
        if self._release_timer is not None:
            self._release_timer.cancel()
            self._release_timer = None
        # Void any release already past its timer but still queued on the
        # operation lock; when it finally runs it will see a newer generation
        # and leave the connection alone.
        self._release_generation += 1

    def _schedule_release(self) -> None:
        """Drop the connection shortly, so the phone app can have the fan."""
        self._cancel_release()
        if self._closing or not self.connected:
            return
        loop = asyncio.get_running_loop()
        self._release_timer = loop.call_later(DISCONNECT_DELAY, self._start_release)

    def _start_release(self) -> None:
        self._release_timer = None
        task = asyncio.create_task(self._release(self._release_generation))
        self._release_tasks.add(task)
        task.add_done_callback(self._release_tasks.discard)

    async def _release(self, generation: int) -> None:
        # Take the operation lock so we never cut a command sequence short; if a
        # new operation got in first, the generation has moved on and this
        # release no longer speaks for the current connection.
        async with self._operation_lock:
            if generation != self._release_generation:
                return
            client = self._client
            if client is None:
                return
            _LOGGER.debug("Releasing connection to %s", self.address)
            await self._disconnect_client(client)
            self._notify_callbacks()

    @contextlib.asynccontextmanager
    async def _operation(self) -> AsyncIterator[None]:
        """Hold a connection for one logical operation, then arm its release."""
        self._cancel_release()
        async with self._operation_lock:
            self._cancel_release()
            await self.connect()
            try:
                yield
            finally:
                self._schedule_release()

    async def stop(self) -> None:
        """Disconnect and stay disconnected. Used when the entry unloads."""
        self._closing = True
        self._cancel_release()
        if self._notify_flush_timer is not None:
            self._notify_flush_timer.cancel()
            self._notify_flush_timer = None
        for task in list(self._release_tasks):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._release_tasks.clear()
        # Take the operation lock so unload cannot cut a scene upload or other
        # command sequence mid-write. Operations are individually timed out, so
        # this cannot block indefinitely.
        async with self._operation_lock:
            if self._client is not None:
                await self._disconnect_client(self._client)

    async def async_refresh_state(self) -> None:
        """Connect briefly just to read the fan's current state.

        Used by the scheduled poll. Callers treat failure as routine -- the most
        likely cause is the phone app holding the connection.
        """
        async with self._operation():
            pass

    async def _write(self, frame: bytes) -> None:
        """Write one frame, repeated to survive the unreliable transport."""
        client = self._client
        if client is None:
            raise BleakError(f"Not connected to {self.address}")
        for index in range(WRITE_REPEATS):
            async with asyncio.timeout(BLE_OP_TIMEOUT):
                await client.write_gatt_char(WRITE_CHAR_UUID, frame, response=False)
            if index < WRITE_REPEATS - 1:
                await asyncio.sleep(WRITE_GAP)

    async def _confirmed(
        self, frame: bytes, expected: Callable[[p.ChromaComfortState], bool]
    ) -> None:
        """Send a command and resend until the fan's own status agrees.

        Write-without-response has no delivery guarantee and the fan does
        occasionally miss a command even with the triple write. It reports status
        unprompted, so we can just watch for the change and retry.

        The measured cadence is about one frame per second, so the 1.5 s
        CONFIRM_TIMEOUT below spans only a single frame in the worst phase
        alignment: one dropped notification then costs a whole resend cycle, and
        three of those report failure on a command the fan may well have applied.
        Widening it trades that against holding the fan's single connection
        longer, which is time the vendor app cannot have it.
        """
        for attempt in range(CONFIRM_ATTEMPTS):
            await self._write(frame)
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
        # INFO, not WARNING: this fires on routine contention (the phone app
        # holding the fan), and warnings end up pasted into bug reports.
        _LOGGER.info("Fan %s did not apply command %s", self.address, frame.hex())

    async def async_set_fan(self, on: bool) -> None:
        async with self._operation():
            await self._confirmed(
                p.build_command(p.CMD_FAN_ON if on else p.CMD_FAN_OFF),
                lambda state: state.fan_on is on,
            )

    async def async_set_white_light(self, on: bool, brightness: int | None = None) -> None:
        async with self._operation():
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
        async with self._operation():
            if not on:
                await self._confirmed(
                    p.build_command(p.CMD_FAVORITE_OFF), lambda state: not state.favorite_1_on
                )
                return
            if rgb is not None:
                self._rgb = rgb
                # Saving a colour produces no status change, so it cannot be
                # confirmed; send it and give the fan time before activating.
                await self._write(p.save_favorite_color(*rgb))
                await asyncio.sleep(COMMAND_GAP)
            dimmer = brightness_to_device(brightness) if brightness is not None else 0
            await self._confirmed(
                p.build_command(p.CMD_FAVORITE_ON, dimmer=dimmer),
                lambda state: state.favorite_1_on and (dimmer == 0 or state.brightness == dimmer),
            )

    async def async_set_wall_cycle(self, on: bool) -> None:
        async with self._operation():
            await self._confirmed(
                p.build_command(p.CMD_WALL_RGB_ON if on else p.CMD_WALL_RGB_OFF),
                lambda state: state.wall_rgb_on is on,
            )

    async def async_stop_scene(self) -> None:
        """Stop scene playback."""
        async with self._operation():
            await self._confirmed(
                p.build_command(p.CMD_PATTERN_OFF), lambda state: not state.user_pattern_on
            )
        self._scene = None

    async def async_turn_color_off(self) -> None:
        """Turn the colour lamp off, whichever mode it is currently in.

        Decided inside the operation so the choice is made against status read on
        this connection, not against whatever was cached before it.
        """
        async with self._operation():
            if self._state is not None and self._state.user_pattern_on:
                await self._confirmed(
                    p.build_command(p.CMD_PATTERN_OFF),
                    lambda state: not state.user_pattern_on,
                )
                self._scene = None
                return
            await self._confirmed(
                p.build_command(p.CMD_FAVORITE_OFF), lambda state: not state.favorite_1_on
            )

    async def async_set_scene(self, name: str, brightness: int | None = None) -> None:
        """Upload a scene's palette to the fan and start playing it.

        Three steps, matching the vendor app: stop any running scene, write the
        colour pair, then activate. The fan stores one scene at a time, so
        switching scenes means re-uploading.
        """
        first, second = p.scene_frames(name)
        dimmer = brightness_to_device(brightness) if brightness is not None else MAX_BRIGHTNESS

        async with self._operation():
            await self._write(p.build_command(p.CMD_PATTERN_OFF, dimmer=MIN_BRIGHTNESS))
            await asyncio.sleep(SCENE_STEP_GAP)

            # The two frames are a unit -- the second carries colour data where
            # the opcode would be, so it only means anything directly after the
            # first. The app writes the pair three times rather than each frame
            # three times, and waits for no acknowledgement.
            client = self._client
            if client is None:
                raise BleakError(f"Not connected to {self.address}")
            for _ in range(WRITE_REPEATS):
                async with asyncio.timeout(BLE_OP_TIMEOUT):
                    await client.write_gatt_char(WRITE_CHAR_UUID, first, response=False)
                await asyncio.sleep(WRITE_GAP)
                async with asyncio.timeout(BLE_OP_TIMEOUT):
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
