"""Fan platform for ChromaComfort."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChromaComfortConfigEntry
from .entity import ChromaComfortEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChromaComfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the exhaust fan."""
    async_add_entities([ChromaComfortFan(entry.runtime_data)])


class ChromaComfortFan(ChromaComfortEntity, FanEntity):
    """The exhaust fan. Single speed, so on/off only."""

    _attr_translation_key = "fan"
    _attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

    def __init__(self, device) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.address}_fan"

    @property
    def is_on(self) -> bool | None:
        state = self._device.state
        return None if state is None else state.fan_on

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        await self._run_command(self._device.async_set_fan(True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._run_command(self._device.async_set_fan(False))
