"""Base entity for ChromaComfort devices."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL
from .device import ChromaComfortDevice


class ChromaComfortEntity(Entity):
    """Common wiring for entities backed by one fan."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: ChromaComfortDevice) -> None:
        self._device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.address)},
            connections={(CONNECTION_BLUETOOTH, device.address)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=device.name,
        )

    @property
    def available(self) -> bool:
        """Entities are unavailable whenever the fan is not reporting status."""
        return self._device.available

    async def async_added_to_hass(self) -> None:
        """Subscribe to pushed state updates."""
        self.async_on_remove(self._device.register_callback(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Called from the event loop when the fan reports new status."""
        self.async_write_ha_state()
