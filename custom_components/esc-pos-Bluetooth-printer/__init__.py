"""ESC/POS Bluetooth Printer — Home Assistant Integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_RFCOMM_CHANNEL,
    CONF_TIMEOUT,
    CONF_ENCODING,
    CONF_PAPER_WIDTH,
    SERVICE_DATA_TITLE,
    SERVICE_DATA_CUT,
    SERVICE_DATA_BOLD,
    SERVICE_DATA_ALIGN,
    SERVICE_DATA_SIZE,
    SERVICE_DATA_QRCODE,
    SERVICE_DATA_BARCODE,
    SERVICE_DATA_RAW_BYTES,
    ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT,
    SIZE_NORMAL, SIZE_LARGE, SIZE_SMALL,
)
from .coordinator import EscposPrinterCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

PRINT_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("message"): cv.string,
        vol.Optional(SERVICE_DATA_TITLE, default=""): cv.string,
        vol.Optional(SERVICE_DATA_CUT, default=True): cv.boolean,
        vol.Optional(SERVICE_DATA_BOLD, default=False): cv.boolean,
        vol.Optional(SERVICE_DATA_ALIGN, default=ALIGN_LEFT): vol.In(
            [ALIGN_LEFT, ALIGN_CENTER, ALIGN_RIGHT]
        ),
        vol.Optional(SERVICE_DATA_SIZE, default=SIZE_NORMAL): vol.In(
            [SIZE_NORMAL, SIZE_LARGE, SIZE_SMALL]
        ),
        vol.Optional(SERVICE_DATA_QRCODE): cv.string,
        vol.Optional(SERVICE_DATA_BARCODE): cv.string,
        vol.Optional(SERVICE_DATA_RAW_BYTES): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ESC/POS Printer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = EscposPrinterCoordinator(
        hass=hass,
        entry_id=entry.entry_id,
        config=dict(entry.data),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:  # noqa: BLE001
        _LOGGER.warning(
            "Initial health check failed for printer %s — will retry later",
            entry.data.get(CONF_MAC_ADDRESS),
        )

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    await _async_setup_notify(hass, entry, coordinator)

    _async_register_print_service(hass, coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_setup_notify(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: EscposPrinterCoordinator,
) -> None:
    """Register a notify-style service for this printer entry."""
    printer_name = entry.data.get("printer_name") or f"escpos_{entry.entry_id[:8]}"
    service_name = printer_name.lower().replace(" ", "_").replace("-", "_")
    service_name = "".join(c for c in service_name if c.isalnum() or c == "_")
    service_name = f"send_{service_name}"

    async def handle_notify(call: ServiceCall) -> None:
        data = call.data.get("data") or {}
        job = {
            "message": call.data.get("message", ""),
            "title": data.get(SERVICE_DATA_TITLE, ""),
            "cut": data.get(SERVICE_DATA_CUT, True),
            "bold": data.get(SERVICE_DATA_BOLD, False),
            "align": data.get(SERVICE_DATA_ALIGN, ALIGN_LEFT),
            "size": data.get(SERVICE_DATA_SIZE, SIZE_NORMAL),
            "qrcode": data.get(SERVICE_DATA_QRCODE),
            "barcode": data.get(SERVICE_DATA_BARCODE),
            "raw_bytes": data.get(SERVICE_DATA_RAW_BYTES),
        }
        success = await coordinator.async_print(job)
        if not success:
            _LOGGER.error("Failed to send print job to %s", coordinator.mac_address)

    hass.services.async_register(
        DOMAIN,
        service_name,
        handle_notify,
        schema=vol.Schema(
            {
                vol.Required("message"): cv.string,
                vol.Optional("data", default={}): dict,
            }
        ),
    )

    _LOGGER.info("Registered notify service: %s.%s", DOMAIN, service_name)


def _async_register_print_service(
    hass: HomeAssistant,
    coordinator: EscposPrinterCoordinator,
) -> None:
    """Register generic print service."""

    async def handle_print(call: ServiceCall) -> None:
        job = {
            "message": call.data["message"],
            "title": call.data.get(SERVICE_DATA_TITLE, ""),
            "cut": call.data.get(SERVICE_DATA_CUT, True),
            "bold": call.data.get(SERVICE_DATA_BOLD, False),
            "align": call.data.get(SERVICE_DATA_ALIGN, ALIGN_LEFT),
            "size": call.data.get(SERVICE_DATA_SIZE, SIZE_NORMAL),
            "qrcode": call.data.get(SERVICE_DATA_QRCODE),
            "barcode": call.data.get(SERVICE_DATA_BARCODE),
            "raw_bytes": call.data.get(SERVICE_DATA_RAW_BYTES),
        }
        success = await coordinator.async_print(job)
        if not success:
            _LOGGER.error(
                "Print service call failed for printer %s", coordinator.mac_address
            )

    if not hass.services.has_service(DOMAIN, "print"):
        hass.services.async_register(
            DOMAIN,
            "print",
            handle_print,
            schema=PRINT_SERVICE_SCHEMA,
        )
        _LOGGER.debug("Registered %s.print service", DOMAIN)
