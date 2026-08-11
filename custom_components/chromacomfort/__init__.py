"""The ChromaComfort integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .device import ChromaComfortDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.LIGHT, Platform.SELECT, Platform.SWITCH]

# Hard ceiling on a whole background refresh, comfortably above the worst-case
# bounded connect (retry attempts x CONNECT_TIMEOUT in the device layer).
REFRESH_TIMEOUT = 120.0

type ChromaComfortConfigEntry = ConfigEntry[ChromaComfortDevice]


async def async_setup_entry(hass: HomeAssistant, entry: ChromaComfortConfigEntry) -> bool:
    """Set up ChromaComfort from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(f"Could not find ChromaComfort fan at {address}")

    @callback
    def _is_present() -> bool:
        return bluetooth.async_address_present(hass, address.upper(), connectable=True)

    device = ChromaComfortDevice(ble_device, presence_check=_is_present)
    entry.runtime_data = device

    @callback
    def _async_update_ble_device(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Keep the BLEDevice fresh so the next connect uses current routing."""
        device.set_ble_device(service_info.device)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_ble_device,
            {"address": address.upper(), "connectable": True},
            bluetooth.BluetoothScanningMode.PASSIVE,
        )
    )
    entry.async_on_unload(device.stop)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Read the fan's state in the background. Doing it inline would make setup
    # fail whenever the phone app happens to hold the connection, and there is
    # nothing here worth blocking startup for.
    entry.async_create_background_task(
        hass, _async_initial_refresh(device), f"chromacomfort {address} initial refresh"
    )
    _async_schedule_refresh(hass, entry, device)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_initial_refresh(device: ChromaComfortDevice) -> None:
    try:
        async with asyncio.timeout(REFRESH_TIMEOUT):
            await device.async_refresh_state()
    except (BleakError, asyncio.TimeoutError) as err:
        _LOGGER.debug("Initial state read for %s failed: %s", device.address, err)


@callback
def _async_schedule_refresh(
    hass: HomeAssistant, entry: ChromaComfortConfigEntry, device: ChromaComfortDevice
) -> None:
    """Arm the periodic state refresh, if the user has not turned it off."""
    seconds = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    if not seconds:
        return

    async def _refresh(_now) -> None:
        # The interval tracker never awaits the previous run, so guard against
        # refreshes stacking up behind a slow or stuck operation.
        if device.busy:
            _LOGGER.debug("Skipping scheduled state read for %s: busy", device.address)
            return
        try:
            async with asyncio.timeout(REFRESH_TIMEOUT):
                await device.async_refresh_state()
        except (BleakError, asyncio.TimeoutError) as err:
            # Routine: most likely the phone app has the fan. Keep the last
            # known state and try again next interval.
            _LOGGER.debug("Scheduled state read for %s failed: %s", device.address, err)

    entry.async_on_unload(
        async_track_time_interval(hass, _refresh, timedelta(seconds=seconds))
    )


async def _async_options_updated(
    hass: HomeAssistant, entry: ChromaComfortConfigEntry
) -> None:
    """Reload so a changed refresh interval takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ChromaComfortConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
