"""ChromaComfort integration for Home Assistant.

Controls ChromaComfort Multi-Color LED Ventilation Fans via Bluetooth Low Energy.
"""
from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, DEFAULT_PIN_CODE
from .coordinator import ChromaComfortCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ChromaComfort from a config entry."""
    address = entry.data["address"]
    name = entry.data.get("name", "ChromaComfort Fan")

    _LOGGER.info(
        "╔═══════════════════════════════════════════════════════════════╗"
    )
    _LOGGER.info(
        "║          ChromaComfort Integration - Setup Starting           ║"
    )
    _LOGGER.info(
        "╚═══════════════════════════════════════════════════════════════╝"
    )
    _LOGGER.info("  Device: %s", name)
    _LOGGER.info("  Address: %s", address)
    _LOGGER.info("  Pairing PIN: %s", DEFAULT_PIN_CODE)
    _LOGGER.info(
        "───────────────────────────────────────────────────────────────"
    )

    # Check if device is discoverable
    _LOGGER.info("  [SETUP] Step 1: Checking if device is visible...")
    ble_device = bluetooth.async_ble_device_from_address(hass, address)

    if ble_device:
        _LOGGER.info("  [SETUP] ✓ Device found in Bluetooth scan")
        _LOGGER.info("  [SETUP]   BLE Name: %s", ble_device.name or "Unknown")
    else:
        _LOGGER.warning("  [SETUP] ⚠ Device not currently visible")
        _LOGGER.warning("  [SETUP]   This is OK - it may appear when powered on")
        _LOGGER.warning("  [SETUP]   Or it might be connected to iOS app")

    # Create coordinator
    _LOGGER.info("  [SETUP] Step 2: Creating device coordinator...")
    coordinator = ChromaComfortCoordinator(hass, address, entry)

    # Do initial data load (won't fail - just returns cached data)
    _LOGGER.info("  [SETUP] Step 3: Initial data refresh...")
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    _LOGGER.info("  [SETUP] Step 4: Registering coordinator...")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms (fan and light entities)
    _LOGGER.info("  [SETUP] Step 5: Setting up entities (fan, light)...")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info(
        "───────────────────────────────────────────────────────────────"
    )
    _LOGGER.info("  [SETUP] ✓ Setup complete!")
    _LOGGER.info("  [SETUP]   Entities created:")
    _LOGGER.info("  [SETUP]     - fan.%s_fan", name.lower().replace(" ", "_"))
    _LOGGER.info("  [SETUP]     - light.%s_light", name.lower().replace(" ", "_"))
    _LOGGER.info(
        "───────────────────────────────────────────────────────────────"
    )
    _LOGGER.info("  [SETUP] Ready! Try turning the fan or light on/off.")
    _LOGGER.info("  [SETUP] Check logs for [BLE], [FAN], [LIGHT] messages.")
    _LOGGER.info(
        "╔═══════════════════════════════════════════════════════════════╗"
    )
    _LOGGER.info(
        "║                   Setup Complete                              ║"
    )
    _LOGGER.info(
        "╚═══════════════════════════════════════════════════════════════╝"
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info(
        "───────────────────────────────────────────────────────────────"
    )
    _LOGGER.info("  [UNLOAD] Unloading ChromaComfort integration...")
    _LOGGER.info(
        "───────────────────────────────────────────────────────────────"
    )

    # Unload platforms
    _LOGGER.info("  [UNLOAD] Step 1: Unloading entities...")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _LOGGER.info("  [UNLOAD] ✓ Entities unloaded")

        # Disconnect and clean up coordinator
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            _LOGGER.info("  [UNLOAD] Step 2: Disconnecting from device...")
            coordinator: ChromaComfortCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
            await coordinator.async_disconnect()
            _LOGGER.info("  [UNLOAD] ✓ Disconnected")

        # Clean up domain data if empty
        if DOMAIN in hass.data and not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

        _LOGGER.info("  [UNLOAD] ✓ Unload complete")
    else:
        _LOGGER.error("  [UNLOAD] ✗ Failed to unload entities")

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    _LOGGER.info(
        "───────────────────────────────────────────────────────────────"
    )
    _LOGGER.info("  [REMOVE] Removing ChromaComfort device from registry...")
    _LOGGER.info(
        "───────────────────────────────────────────────────────────────"
    )

    from homeassistant.helpers import device_registry as dr

    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)

    for device_entry in device_entries:
        _LOGGER.info("  [REMOVE] Removing device: %s", device_entry.name)
        device_registry.async_remove_device(device_entry.id)

    _LOGGER.info("  [REMOVE] ✓ Device removed")
