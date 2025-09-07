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

from .const import DOMAIN
from .coordinator import ChromaComfortCoordinator

_LOGGER = logging.getLogger(__name__)


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
    """Representation of a ChromaComfort fan (single speed on/off only)."""

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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Always return True to keep entity responsive even if BLE disconnected
        return True

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return self.coordinator.data.get("fan_state", False)

    @property
    def supported_features(self) -> FanEntityFeature:
        """Flag supported features."""
        # Only support basic on/off for single speed fan
        features = FanEntityFeature(0)

        # Check which features are available in this HA version
        if hasattr(FanEntityFeature, 'TURN_ON'):
            features |= FanEntityFeature.TURN_ON
        if hasattr(FanEntityFeature, 'TURN_OFF'):
            features |= FanEntityFeature.TURN_OFF

        # If no explicit turn on/off features, return 0 (no special features)
        return features

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan (single speed only)."""
        try:
            await self.coordinator.set_fan_state(True)
            _LOGGER.info("Fan turned on")
        except Exception as err:
            _LOGGER.error("Failed to turn on fan %s: %s", self.entity_id, err)
            # Don't re-raise to keep the entity responsive

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        try:
            await self.coordinator.set_fan_state(False)
            _LOGGER.info("Fan turned off")
        except Exception as err:
            _LOGGER.error("Failed to turn off fan %s: %s", self.entity_id, err)
            # Don't re-raise to keep the entity responsive

    # Note: No async_set_percentage method needed since it's single speed
    # The fan entity will automatically handle percentage=0 as turn_off