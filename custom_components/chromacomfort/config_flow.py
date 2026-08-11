"""Config flow for ChromaComfort."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_SCAN_INTERVAL,
    CONTROL_SERVICE_UUID,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_NAME_PREFIX,
    DOMAIN,
    SCAN_INTERVAL_OPTIONS,
)


def _is_chromacomfort(info: BluetoothServiceInfoBleak) -> bool:
    """Match on the control service UUID, falling back to the advertised name."""
    if CONTROL_SERVICE_UUID in [uuid.lower() for uuid in info.service_uuids]:
        return True
    return bool(info.name and info.name.startswith(DEVICE_NAME_PREFIX))


def _display_name(name: str | None) -> str:
    """Sanitise an advertised name before it reaches the frontend.

    The name is attacker-controlled radio data and ends up in markdown-rendered
    dialog text ("Set up {name}?"), so strip markdown-active characters and
    control codes, and bound the length.
    """
    if not name:
        return "ChromaComfort"
    cleaned = "".join(c for c in name if c.isprintable() and c not in "[]()<>`#*_")
    cleaned = cleaned.strip()
    return cleaned[:40] or "ChromaComfort"


class ChromaComfortConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle discovery and manual setup of ChromaComfort fans."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ChromaComfortOptionsFlow:
        return ChromaComfortOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a fan discovered over Bluetooth."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovered = discovery_info
        self.context["title_placeholders"] = {"name": _display_name(discovery_info.name)}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a discovered fan."""
        assert self._discovered is not None
        if user_input is not None:
            return self.async_create_entry(
                title=_display_name(self._discovered.name),
                data={CONF_ADDRESS: self._discovered.address},
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": _display_name(self._discovered.name)},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick from the fans Home Assistant can currently see."""
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            # The schema's vol.In guards the normal UI path, but a flow started
            # programmatically can arrive here with an address we never
            # discovered -- show the picker again rather than blow up.
            if address in self._discovered_devices:
                await self.async_set_unique_id(address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self._discovered_devices[address],
                    data={CONF_ADDRESS: address},
                )
            errors["base"] = "device_not_found"

        current = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address in current or info.address in self._discovered_devices:
                continue
            if _is_chromacomfort(info):
                self._discovered_devices[info.address] = _display_name(info.name)

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            address: f"{name} ({address})"
                            for address, name in self._discovered_devices.items()
                        }
                    )
                }
            ),
            errors=errors,
        )


class ChromaComfortOptionsFlow(OptionsFlow):
    """Lets the user choose how often Home Assistant re-reads the fan's state.

    Every refresh briefly takes the fan's single Bluetooth connection, so this is
    a trade between how current the state is and how freely the vendor app works.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.In(
                        SCAN_INTERVAL_OPTIONS
                    )
                }
            ),
        )
