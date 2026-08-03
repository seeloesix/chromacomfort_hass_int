"""The ChromaComfort integration."""

from __future__ import annotations

import asyncio
import logging

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .device import ChromaComfortDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.LIGHT, Platform.SWITCH]

type ChromaComfortConfigEntry = ConfigEntry[ChromaComfortDevice]


async def async_setup_entry(hass: HomeAssistant, entry: ChromaComfortConfigEntry) -> bool:
    """Set up ChromaComfort from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(f"Could not find ChromaComfort fan at {address}")

    device = ChromaComfortDevice(ble_device)
    try:
        await device.connect()
    except (BleakError, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady(f"Could not connect to ChromaComfort fan at {address}") from err

    entry.runtime_data = device

    @callback
    def _async_update_ble_device(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Keep the BLEDevice fresh so reconnects use current routing."""
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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ChromaComfortConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
