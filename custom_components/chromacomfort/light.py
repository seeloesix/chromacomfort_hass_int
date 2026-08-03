"""Light platform for ChromaComfort.

The fan has two independent lamps: a white ceiling light and an RGB accent
light. The device treats its light modes as mutually exclusive, so turning one
on switches the other off; both entities follow the fan's own status reports, so
that resolves itself without any special handling here.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChromaComfortConfigEntry
from .device import brightness_to_ha
from .entity import ChromaComfortEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChromaComfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the white and colour lights."""
    device = entry.runtime_data
    async_add_entities([ChromaComfortWhiteLight(device), ChromaComfortColorLight(device)])


class ChromaComfortWhiteLight(ChromaComfortEntity, LightEntity):
    """The white ceiling light."""

    _attr_translation_key = "white_light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, device) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.address}_white_light"

    @property
    def is_on(self) -> bool | None:
        state = self._device.state
        return None if state is None else state.light_on

    @property
    def brightness(self) -> int | None:
        state = self._device.state
        return None if state is None else brightness_to_ha(state.brightness)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.async_set_white_light(True, kwargs.get(ATTR_BRIGHTNESS))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_set_white_light(False)


class ChromaComfortColorLight(ChromaComfortEntity, LightEntity):
    """The RGB accent light."""

    _attr_translation_key = "color_light"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(self, device) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.address}_color_light"

    @property
    def is_on(self) -> bool | None:
        state = self._device.state
        return None if state is None else state.favorite_1_on

    @property
    def brightness(self) -> int | None:
        state = self._device.state
        return None if state is None else brightness_to_ha(state.brightness)

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """The fan never reports its colour back, so this is what we last set."""
        return self._device.rgb

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.async_set_color_light(
            True, kwargs.get(ATTR_BRIGHTNESS), kwargs.get(ATTR_RGB_COLOR)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_set_color_light(False)
