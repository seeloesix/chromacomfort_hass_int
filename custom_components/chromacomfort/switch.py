"""Switch platform for ChromaComfort."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChromaComfortConfigEntry
from .entity import ChromaComfortEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChromaComfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the colour cycle switch."""
    async_add_entities([ChromaComfortColorCycle(entry.runtime_data)])


class ChromaComfortColorCycle(ChromaComfortEntity, SwitchEntity):
    """The fan's built-in colour cycling effect.

    This is a separate mode from the RGB light rather than an effect on it: the
    fan runs its own factory colour sweep and ignores the saved colour while it
    is active.
    """

    _attr_translation_key = "color_cycle"
    _attr_icon = "mdi:looks"

    def __init__(self, device) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.address}_color_cycle"

    @property
    def is_on(self) -> bool | None:
        state = self._device.state
        return None if state is None else state.wall_rgb_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.async_set_wall_cycle(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.async_set_wall_cycle(False)
