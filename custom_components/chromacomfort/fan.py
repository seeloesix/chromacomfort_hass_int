"""Fan entity for ChromaComfort integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN, FAN_SPEED_HIGH, FAN_SPEED_LOW, FAN_SPEED_MEDIUM, FAN_SPEED_OFF
from .coordinator import ChromaComfortCoordinator

_LOGGER = logging.getLogger(__name__)

ORDERED_NAMED_FAN_SPEEDS = [FAN_SPEED_LOW, FAN_SPEED_MEDIUM, FAN_SPEED_HIGH]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ChromaComfort fan entity."""
    try:
        coordinator: ChromaComfortCoordinator = hass.data[DOMAIN][entry.entry_id]
        _LOGGER.info("Setting up ChromaComfort fan entity for %s", entry.data.get(CONF_NAME, "Unknown"))
        
        fan = ChromaComfortFan(coordinator, entry)
        async_add_entities([fan])
        
        _LOGGER.info("Successfully created fan entity: %s", fan.entity_id if hasattr(fan, 'entity_id') else "Unknown ID")
    except Exception as err:
        _LOGGER.error("Failed to set up ChromaComfort fan entity: %s", err, exc_info=True)


class ChromaComfortFan(CoordinatorEntity, FanEntity):
    """Representation of a ChromaComfort fan."""

    _attr_has_entity_name = True
    _attr_name = "Fan"
    _attr_should_poll = False  # We use coordinator for updates
    _attr_icon = "mdi:fan"  # Fan icon
    

    def __init__(
        self,
        coordinator: ChromaComfortCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_fan"
        self._attr_device_info = coordinator.device_info
        # Explicitly set that we support turning on/off and percentage control
        # Don't set _attr_supported_features to avoid compatibility issues

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Always return True to keep entity responsive even if BLE disconnected
        return True
    
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
    
    @property
    def supported_features(self) -> FanEntityFeature:
        """Flag supported features."""
        # Return FanEntityFeature object with SET_SPEED for percentage control
        return FanEntityFeature.SET_SPEED
    

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        try:
            if percentage is None:
                # Default to medium speed
                await self.coordinator.set_fan_speed(FAN_SPEED_MEDIUM)
            else:
                speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
                await self.coordinator.set_fan_speed(speed)
        except Exception as err:
            _LOGGER.error("Failed to turn on fan %s: %s", self.entity_id, err)
            # Don't re-raise to keep the entity responsive

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        try:
            await self.coordinator.set_fan_speed(FAN_SPEED_OFF)
        except Exception as err:
            _LOGGER.error("Failed to turn off fan %s: %s", self.entity_id, err)
            # Don't re-raise to keep the entity responsive

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
        else:
            speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
            await self.coordinator.set_fan_speed(speed)
    
    def turn_on(self, **kwargs) -> None:
        """Turn on the fan (sync wrapper)."""
        # Home Assistant should call async_turn_on, but some versions may look for this
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.async_turn_on(**kwargs))
            else:
                asyncio.run(self.async_turn_on(**kwargs))
        except Exception:
            pass  # Fail silently as this is just a compatibility shim
    
    def turn_off(self, **kwargs) -> None:
        """Turn off the fan (sync wrapper)."""
        # Home Assistant should call async_turn_off, but some versions may look for this
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.async_turn_off(**kwargs))
            else:
                asyncio.run(self.async_turn_off(**kwargs))
        except Exception:
            pass  # Fail silently as this is just a compatibility shim