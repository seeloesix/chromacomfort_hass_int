"""Fan entity for ChromaComfort integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
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
    """Set up ChromaComfort fan entity."""
    coordinator: ChromaComfortCoordinator = hass.data[DOMAIN][entry.entry_id]

    _LOGGER.info("[FAN] Setting up fan entity for %s", coordinator.custom_name)

    async_add_entities([ChromaComfortFan(coordinator, entry)])


class ChromaComfortFan(CoordinatorEntity, FanEntity):
    """ChromaComfort fan entity (single speed on/off)."""

    _attr_has_entity_name = True
    _attr_name = "Fan"
    _attr_icon = "mdi:fan"

    def __init__(
        self,
        coordinator: ChromaComfortCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_fan"
        self._attr_device_info = coordinator.device_info
        self._coordinator = coordinator

    @property
    def available(self) -> bool:
        """Return True - entity is always available for commands."""
        return True

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return self._coordinator.data.get("fan_on", False)

    @property
    def supported_features(self) -> FanEntityFeature:
        """Return supported features (on/off only)."""
        features = FanEntityFeature(0)

        if hasattr(FanEntityFeature, 'TURN_ON'):
            features |= FanEntityFeature.TURN_ON
        if hasattr(FanEntityFeature, 'TURN_OFF'):
            features |= FanEntityFeature.TURN_OFF

        return features

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.info("[FAN] Turn ON requested")
        success = await self._coordinator.set_fan_state(True)
        if success:
            self.async_write_ha_state()
        else:
            _LOGGER.error("[FAN] Failed to turn on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        _LOGGER.info("[FAN] Turn OFF requested")
        success = await self._coordinator.set_fan_state(False)
        if success:
            self.async_write_ha_state()
        else:
            _LOGGER.error("[FAN] Failed to turn off")
