"""Light entity for ChromaComfort integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChromaComfortCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ChromaComfort light entity."""
    coordinator: ChromaComfortCoordinator = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.info("[LIGHT] Setting up light entity for %s", coordinator.custom_name)

    async_add_entities([ChromaComfortLight(coordinator, entry)])


class ChromaComfortLight(CoordinatorEntity, LightEntity):
    """ChromaComfort light entity with RGB support."""

    _attr_has_entity_name = True
    _attr_name = "Light"
    _attr_icon = "mdi:led-strip-variant"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(
        self,
        coordinator: ChromaComfortCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_light"
        self._attr_device_info = coordinator.device_info
        self._coordinator = coordinator

    @property
    def available(self) -> bool:
        """Return True - entity is always available for commands."""
        return True

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._coordinator.data.get("light_on", False)

    @property
    def brightness(self) -> int | None:
        """Return current brightness."""
        if not self.is_on:
            return None
        return self._coordinator.data.get("brightness", 255)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return current RGB color."""
        if not self.is_on:
            return None
        return self._coordinator.data.get("rgb_color", (255, 255, 255))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        _LOGGER.info("[LIGHT] Turn ON requested")

        # Handle color if specified
        rgb_color = kwargs.get(ATTR_RGB_COLOR)
        if rgb_color:
            await self._coordinator.set_light_color(rgb_color)

        # Handle brightness if specified
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            await self._coordinator.set_light_brightness(brightness)

        # Turn on the light
        success = await self._coordinator.set_light_state(True)
        if success:
            self.async_write_ha_state()
        else:
            _LOGGER.error("[LIGHT] Failed to turn on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        _LOGGER.info("[LIGHT] Turn OFF requested")
        success = await self._coordinator.set_light_state(False)
        if success:
            self.async_write_ha_state()
        else:
            _LOGGER.error("[LIGHT] Failed to turn off")
