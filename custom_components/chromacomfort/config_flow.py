"""Config flow for ChromaComfort integration.

This handles device discovery and setup, mirroring the iOS app flow:
1. Scan for ChromaComfort devices
2. User selects device
3. User names device and assigns room
4. Device is added (pairing happens on first connection)
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import area_registry as ar

from .const import DOMAIN, DEFAULT_PIN_CODE

_LOGGER = logging.getLogger(__name__)

# GooWi Technology manufacturer ID
MANUFACTURER_ID = 10
SERVICE_UUID = "a08f7710-c37c-11e3-99cc-0228ac012a70"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ChromaComfort."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )
        _LOGGER.info("  [DISCOVERY] Bluetooth device detected!")
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )
        _LOGGER.info("  Name: %s", discovery_info.name)
        _LOGGER.info("  Address: %s", discovery_info.address)
        _LOGGER.info("  RSSI: %s dBm", discovery_info.rssi)

        if discovery_info.manufacturer_data:
            for mid, data in discovery_info.manufacturer_data.items():
                _LOGGER.info("  Manufacturer ID: %d (0x%04X)", mid, mid)
                _LOGGER.debug("  Manufacturer Data: %s", data.hex() if data else "None")

        if discovery_info.service_uuids:
            _LOGGER.info("  Service UUIDs: %s", discovery_info.service_uuids)

        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovered_device = discovery_info

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovered device and configure."""
        if user_input is not None:
            address = self._discovered_device.address
            device_name = user_input.get(CONF_NAME) or self._discovered_device.name or "ChromaComfort Fan"
            room = user_input.get("room", "none")

            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            entry_data = {
                CONF_ADDRESS: address,
                CONF_NAME: device_name,
            }

            if room and room != "none":
                entry_data["room"] = room

            _LOGGER.info(
                "═══════════════════════════════════════════════════════════════"
            )
            _LOGGER.info("  [SETUP] Creating device entry")
            _LOGGER.info(
                "═══════════════════════════════════════════════════════════════"
            )
            _LOGGER.info("  Device Name: %s", device_name)
            _LOGGER.info("  BLE Address: %s", address)
            _LOGGER.info("  Room: %s", room if room != "none" else "Not assigned")
            _LOGGER.info("  Pairing PIN: %s (will be used on first connection)", DEFAULT_PIN_CODE)
            _LOGGER.info(
                "═══════════════════════════════════════════════════════════════"
            )

            return self.async_create_entry(
                title=device_name,
                data=entry_data,
            )

        # Build room selection
        areas = await self._get_areas()

        default_name = self._discovered_device.name or "ChromaComfort Fan"
        device_address = self._discovered_device.address

        _LOGGER.info("  [CONFIG] Showing configuration form for %s", device_address)

        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=vol.Schema({
                vol.Optional(CONF_NAME, default=default_name): str,
                vol.Optional("room", default="none"): vol.In(areas),
            }),
            description_placeholders={
                "name": default_name,
                "address": device_address,
                "manufacturer": "GooWi Technology",
                "model": "Multi-Color LED Ventilation Fan",
                "pin_code": DEFAULT_PIN_CODE,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual setup (user initiated)."""
        errors = {}

        if user_input is not None:
            if CONF_ADDRESS in user_input:
                address = user_input[CONF_ADDRESS]
                _LOGGER.info("  [USER] Selected device: %s", address)

                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()

                self._discovered_device = self._discovered_devices[address]
                return await self.async_step_bluetooth_confirm()

        # Scan for ChromaComfort devices
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )
        _LOGGER.info("  [SCAN] Scanning for ChromaComfort devices...")
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )
        _LOGGER.info("  Looking for:")
        _LOGGER.info("    - Manufacturer ID: %d (GooWi Technology)", MANUFACTURER_ID)
        _LOGGER.info("    - Service UUID: %s", SERVICE_UUID)
        _LOGGER.info(
            "───────────────────────────────────────────────────────────────"
        )

        current_addresses = self._async_current_ids()
        all_discovered = list(async_discovered_service_info(self.hass, False))

        _LOGGER.info("  [SCAN] Found %d total Bluetooth devices nearby", len(all_discovered))

        self._discovered_devices = {}

        for discovery_info in all_discovered:
            # Skip already configured devices
            if discovery_info.address in current_addresses:
                _LOGGER.debug("  [SCAN] Skipping %s (already configured)", discovery_info.address)
                continue

            # Log all devices for debugging
            _LOGGER.debug(
                "  [SCAN] Checking: %s (%s) - Mfr IDs: %s",
                discovery_info.name or "Unknown",
                discovery_info.address,
                list(discovery_info.manufacturer_data.keys()) if discovery_info.manufacturer_data else "None"
            )

            # Check for ChromaComfort device
            is_chromacomfort = self._is_chromacomfort_device(discovery_info)

            if is_chromacomfort:
                self._discovered_devices[discovery_info.address] = discovery_info
                _LOGGER.info(
                    "  [SCAN] ✓ FOUND ChromaComfort: %s (%s)",
                    discovery_info.name or "Unknown",
                    discovery_info.address
                )

        _LOGGER.info(
            "───────────────────────────────────────────────────────────────"
        )

        if not self._discovered_devices:
            _LOGGER.warning("  [SCAN] ✗ No ChromaComfort devices found!")
            _LOGGER.warning("  [SCAN]   Tips:")
            _LOGGER.warning("  [SCAN]   → Make sure the fan is powered on")
            _LOGGER.warning("  [SCAN]   → Close the iOS ChromaComfort app")
            _LOGGER.warning("  [SCAN]   → Move closer to the fan (~30 feet range)")
            _LOGGER.info(
                "═══════════════════════════════════════════════════════════════"
            )
            return self.async_show_form(
                step_id="user",
                errors={"base": "no_devices_found"},
            )

        _LOGGER.info("  [SCAN] ✓ Found %d ChromaComfort device(s)", len(self._discovered_devices))
        _LOGGER.info(
            "═══════════════════════════════════════════════════════════════"
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): vol.In({
                    addr: f"{device.name or 'ChromaComfort'} ({addr})"
                    for addr, device in self._discovered_devices.items()
                }),
            }),
            errors=errors,
        )

    def _is_chromacomfort_device(self, discovery_info: BluetoothServiceInfoBleak) -> bool:
        """Check if a discovered device is a ChromaComfort fan."""
        # Primary check: manufacturer ID 10 (GooWi Technology)
        if discovery_info.manufacturer_data:
            if MANUFACTURER_ID in discovery_info.manufacturer_data:
                _LOGGER.debug(
                    "  [SCAN]   → Matched by Manufacturer ID %d",
                    MANUFACTURER_ID
                )
                return True

        # Secondary check: service UUID
        if discovery_info.service_uuids:
            for uuid in discovery_info.service_uuids:
                if SERVICE_UUID in uuid.lower():
                    _LOGGER.debug(
                        "  [SCAN]   → Matched by Service UUID %s",
                        SERVICE_UUID
                    )
                    return True

        return False

    async def _get_areas(self) -> dict[str, str]:
        """Get available areas/rooms."""
        areas = {}

        try:
            area_registry = ar.async_get(self.hass)
            areas = {area.id: area.name for area in area_registry.areas.values()}
            _LOGGER.debug("  [CONFIG] Found %d areas in registry", len(areas))
        except Exception as e:
            _LOGGER.debug("  [CONFIG] Could not get area registry: %s", e)

        # Add default rooms if registry is empty
        if not areas:
            areas = {
                "living_room": "Living Room",
                "bedroom": "Bedroom",
                "bathroom": "Bathroom",
                "kitchen": "Kitchen",
                "office": "Office",
            }
            _LOGGER.debug("  [CONFIG] Using default room list")

        # Always add "No Room" option
        areas["none"] = "No Room"

        return areas
