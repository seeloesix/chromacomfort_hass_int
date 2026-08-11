"""Select platform for ChromaComfort.

Exposes the animated scenes as a select on the device page, so a scene can be
started or stopped from the device's controls without going through the colour
light's more-info dialog or a service call.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChromaComfortConfigEntry, protocol
from .entity import ChromaComfortEntity

# The non-scene option. Scene names are proper nouns and stay untranslated.
OPTION_OFF = "Off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChromaComfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the scene selector."""
    async_add_entities([ChromaComfortSceneSelect(entry.runtime_data)])


class ChromaComfortSceneSelect(ChromaComfortEntity, SelectEntity):
    """Pick an animated scene, or Off to stop scene playback.

    This mirrors the colour light's effect list; both drive the same lamp. The
    select exists so the scene is one tap away on the device page.
    """

    _attr_translation_key = "scene"
    _attr_icon = "mdi:palette"
    _attr_options = [OPTION_OFF, *protocol.BUILTIN_SCENES]

    def __init__(self, device) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.address}_scene"

    @property
    def current_option(self) -> str | None:
        state = self._device.state
        if state is None:
            return None
        if not state.user_pattern_on:
            return OPTION_OFF
        # A scene is running. The fan does not report which one, so if it was
        # started by the phone app rather than us, honestly report unknown.
        return self._device.scene

    async def async_select_option(self, option: str) -> None:
        if option == OPTION_OFF:
            await self._run_command(self._device.async_stop_scene())
            return
        await self._run_command(self._device.async_set_scene(option))
