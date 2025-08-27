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
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Initial connection to %s failed: %s. Will retry in background.", address, err)
        # Set default data so entities can be created
        coordinator.data = {
            "fan_speed": 0,
            "light_on": False,
            "brightness": 255,
            "rgb_color": (255, 255, 255),
        }
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Forward setup to platforms
    _LOGGER.info("Setting up platforms for ChromaComfort: %s", PLATFORMS)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info("Successfully set up platforms for ChromaComfort")
    except Exception as err:
        _LOGGER.error("Failed to set up platforms: %s", err, exc_info=True)
        raise
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: ChromaComfortCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.disconnect()
    
    return unload_ok