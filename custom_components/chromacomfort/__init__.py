"""The ChromaComfort integration for ChromaComfort Multi-Color LED Ventilation Fan."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import ChromaComfortCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.FAN, Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ChromaComfort from a config entry."""
    address = entry.data["address"]
    
    # Check if device is available
    ble_device = bluetooth.async_ble_device_from_address(hass, address)
    if not ble_device:
        raise ConfigEntryNotReady(f"Could not find ChromaComfort device with address {address}")
    
    # Pass entry data to coordinator for device name and room
    coordinator = ChromaComfortCoordinator(hass, address, entry)
    
    # Try initial refresh but don't fail setup if it doesn't work
    _LOGGER.info("[SETUP] Attempting initial connection to %s", address)
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("[SETUP] ✅ Initial connection successful")
    except Exception as err:
        _LOGGER.warning("[SETUP] ⚠️ Initial connection to %s failed: %s", address, err)
        _LOGGER.warning("[SETUP] This is normal - will retry in background")
        _LOGGER.debug("[SETUP] Error type: %s", type(err).__name__)
        # Set default data so entities can be created
        coordinator.data = {
            "fan_speed": 0,
            "light_on": False,
            "brightness": 255,
            "rgb_color": (255, 255, 255),
        }
        _LOGGER.info("[SETUP] Set default data for entities")
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Forward setup to platforms
    _LOGGER.info("[SETUP] Setting up platforms for ChromaComfort: %s", PLATFORMS)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info("[SETUP] ✅ Successfully set up platforms for ChromaComfort")
    except Exception as err:
        _LOGGER.error("[SETUP] ❌ Failed to set up platforms: %s", err, exc_info=True)
        raise
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("[CLEANUP] Starting ChromaComfort integration cleanup for %s", entry.entry_id)
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Clean up coordinator and disconnect BLE
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            coordinator: ChromaComfortCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
            try:
                await coordinator.disconnect()
                _LOGGER.info("[CLEANUP] ✅ Disconnected from device %s", coordinator.address)
            except Exception as err:
                _LOGGER.warning("[CLEANUP] ⚠️ Error disconnecting from device: %s", err)
        
        # Clean up domain data if empty
        if DOMAIN in hass.data and not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            _LOGGER.info("[CLEANUP] ✅ Removed domain data")
    
    _LOGGER.info("[CLEANUP] ChromaComfort cleanup completed. Success: %s", unload_ok)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry and clean up device registry."""
    _LOGGER.info("[REMOVE] Removing ChromaComfort integration and cleaning device registry")
    
    # Import here to avoid circular imports
    from homeassistant.helpers import device_registry as dr
    
    # Remove device from device registry
    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    
    for device_entry in device_entries:
        _LOGGER.info("[REMOVE] Removing device: %s (%s)", device_entry.name, device_entry.id)
        device_registry.async_remove_device(device_entry.id)
    
    _LOGGER.info("[REMOVE] ✅ ChromaComfort device registry cleanup completed")