"""Light entity for ChromaFi integration."""
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
from .coordinator import ChromaFiCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ChromaFi light entity."""
    coordinator: ChromaFiCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([ChromaFiLight(coordinator, entry)])


class ChromaFiLight(CoordinatorEntity, LightEntity):
    """Representation of a ChromaFi light."""

    _attr_has_entity_name = True
    _attr_name = "Light"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(
        self,
        coordinator: ChromaFiCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_light"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self.coordinator.data.get("light_on", False)

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if not self.is_on:
            return None
        return self.coordinator.data.get("brightness", 255)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color value."""
        if not self.is_on:
            return None
        return self.coordinator.data.get("rgb_color", (255, 255, 255))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        rgb_color = kwargs.get(ATTR_RGB_COLOR)
        
        if rgb_color:
            await self.coordinator.set_light_color(rgb_color)
        
        if brightness is not None:
            await self.coordinator.set_light_brightness(brightness)
        
        await self.coordinator.set_light_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.set_light_state(False)