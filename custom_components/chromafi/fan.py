"""Fan entity for ChromaFi integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN, FAN_SPEED_HIGH, FAN_SPEED_LOW, FAN_SPEED_MEDIUM, FAN_SPEED_OFF
from .coordinator import ChromaFiCoordinator

_LOGGER = logging.getLogger(__name__)

ORDERED_NAMED_FAN_SPEEDS = [FAN_SPEED_LOW, FAN_SPEED_MEDIUM, FAN_SPEED_HIGH]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ChromaFi fan entity."""
    coordinator: ChromaFiCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([ChromaFiFan(coordinator, entry)])


class ChromaFiFan(CoordinatorEntity, FanEntity):
    """Representation of a ChromaFi fan."""

    _attr_has_entity_name = True
    _attr_name = "Fan"

    def __init__(
        self,
        coordinator: ChromaFiCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_fan"
        self._attr_device_info = coordinator.device_info
        self._attr_supported_features = FanEntityFeature.SET_SPEED

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return self.coordinator.data.get("fan_speed", FAN_SPEED_OFF) != FAN_SPEED_OFF

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        speed = self.coordinator.data.get("fan_speed", FAN_SPEED_OFF)
        if speed == FAN_SPEED_OFF:
            return 0
        return ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            # Default to medium speed
            await self.coordinator.set_fan_speed(FAN_SPEED_MEDIUM)
        else:
            speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
            await self.coordinator.set_fan_speed(speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.set_fan_speed(FAN_SPEED_OFF)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
        else:
            speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
            await self.coordinator.set_fan_speed(speed)