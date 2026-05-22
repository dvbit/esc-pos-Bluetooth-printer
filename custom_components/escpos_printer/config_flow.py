"""Config flow for ESC/POS Bluetooth Printer integration."""
from __future__ import annotations

import logging
import re
import socket
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_RFCOMM_CHANNEL,
    CONF_PRINTER_NAME,
    CONF_PAPER_WIDTH,
    CONF_ENCODING,
    CONF_TIMEOUT,
    DEFAULT_RFCOMM_CHANNEL,
    DEFAULT_PAPER_WIDTH,
    DEFAULT_ENCODING,
    DEFAULT_TIMEOUT,
    PAPER_WIDTHS,
    ENCODINGS,
)

_LOGGER = logging.getLogger(__name__)

MAC_ADDRESS_RE = re.compile(
    r"^([0-9A-Fa-f]{2}[:\-]){5}([0-9A-Fa-f]{2})$"
)


def _normalize_mac(mac: str) -> str:
    return mac.upper().replace("-", ":")


def _validate_mac(mac: str) -> bool:
    return bool(MAC_ADDRESS_RE.match(mac))


def _test_bluetooth_connection(mac: str, channel: int, timeout: int) -> str | None:
    """
    Attempt RFCOMM connection to printer.
    Returns None on success, error key on failure.
    Runs in executor (blocking).
    """
    try:
        sock = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM,
        )
        sock.settimeout(timeout)
        sock.connect((mac, channel))
        sock.close()
        return None
    except OSError as err:
        err_str = str(err).lower()
        if "no such device" in err_str or "host is down" in err_str:
            return "device_not_found"
        if "connection refused" in err_str:
            return "connection_refused"
        if "timed out" in err_str or "timeout" in err_str:
            return "connection_timeout"
        if "network is unreachable" in err_str:
            return "bluetooth_unavailable"
        if "protocol not supported" in err_str or "address family" in err_str:
            return "bluetooth_not_supported"
        _LOGGER.debug("Bluetooth connection error: %s", err)
        return "cannot_connect"
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Unexpected error testing Bluetooth: %s", err)
        return "unknown_error"


class EscposPrinterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ESC/POS Bluetooth Printer."""

    VERSION = 1

    def __init__(self) -> None:
        self._mac_address: str = ""
        self._rfcomm_channel: int = DEFAULT_RFCOMM_CHANNEL
        self._printer_name: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1: MAC address and RFCOMM channel."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC_ADDRESS].strip()
            channel = user_input[CONF_RFCOMM_CHANNEL]

            if not _validate_mac(mac):
                errors[CONF_MAC_ADDRESS] = "invalid_mac"
            elif not 1 <= channel <= 30:
                errors[CONF_RFCOMM_CHANNEL] = "invalid_channel"
            else:
                mac = _normalize_mac(mac)
                await self.async_set_unique_id(f"escpos_{mac}_{channel}")
                self._abort_if_unique_id_configured()
                self._mac_address = mac
                self._rfcomm_channel = channel
                return await self.async_step_test_connection()

        schema = vol.Schema(
            {
                vol.Required(CONF_MAC_ADDRESS): str,
                vol.Optional(
                    CONF_RFCOMM_CHANNEL, default=DEFAULT_RFCOMM_CHANNEL
                ): vol.All(int, vol.Range(min=1, max=30)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "mac_hint": "Es: AA:BB:CC:DD:EE:FF",
                "channel_hint": "Solitamente 1 o 2",
            },
        )

    async def async_step_test_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2: Test RFCOMM connection."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="test_connection",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "mac": self._mac_address,
                    "channel": str(self._rfcomm_channel),
                },
            )

        _LOGGER.debug(
            "Testing Bluetooth connection to %s channel %s",
            self._mac_address,
            self._rfcomm_channel,
        )

        error = await self.hass.async_add_executor_job(
            _test_bluetooth_connection,
            self._mac_address,
            self._rfcomm_channel,
            10,
        )

        if error:
            # Se il device non è raggiungibile, mostra guida al pairing
            if error in ("device_not_found", "cannot_connect", "connection_timeout"):
                return await self.async_step_bluetooth_pairing_guide()

            # Altri errori (BT non supportato, ecc.) — mostra direttamente
            errors["base"] = error
            return self.async_show_form(
                step_id="test_connection",
                data_schema=vol.Schema({}),
                errors=errors,
                description_placeholders={
                    "mac": self._mac_address,
                    "channel": str(self._rfcomm_channel),
                },
            )

        return await self.async_step_printer_settings()

    async def async_step_bluetooth_pairing_guide(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        Step intermedio: guida al pairing BT con comandi precompilati.
        Quando l'utente clicca Avanti, ritenta il test di connessione.
        """
        if user_input is not None:
            # Utente dichiara di aver completato il pairing — riprova test
            return await self.async_step_test_connection()

        return self.async_show_form(
            step_id="bluetooth_pairing_guide",
            data_schema=vol.Schema({}),
            description_placeholders={
                "mac": self._mac_address,
                "pin": "0000",
                "cmd_pair": f"pair {self._mac_address}",
                "cmd_trust": f"trust {self._mac_address}",
            },
        )

    async def async_step_printer_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 3: Printer-specific settings."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_PRINTER_NAME) or f"ESC/POS {self._mac_address}",
                data={
                    CONF_MAC_ADDRESS: self._mac_address,
                    CONF_RFCOMM_CHANNEL: self._rfcomm_channel,
                    CONF_PRINTER_NAME: user_input.get(CONF_PRINTER_NAME, ""),
                    CONF_PAPER_WIDTH: user_input.get(CONF_PAPER_WIDTH, list(PAPER_WIDTHS.keys())[1]),
                    CONF_ENCODING: user_input.get(CONF_ENCODING, DEFAULT_ENCODING),
                    CONF_TIMEOUT: user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                },
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_PRINTER_NAME): str,
                vol.Optional(
                    CONF_PAPER_WIDTH, default=list(PAPER_WIDTHS.keys())[1]
                ): vol.In(list(PAPER_WIDTHS.keys())),
                vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): vol.In(ENCODINGS),
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
                    int, vol.Range(min=5, max=60)
                ),
            }
        )

        return self.async_show_form(
            step_id="printer_settings",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "EscposPrinterOptionsFlow":
        return EscposPrinterOptionsFlow(config_entry)


class EscposPrinterOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.data

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_PAPER_WIDTH,
                    default=current.get(CONF_PAPER_WIDTH, list(PAPER_WIDTHS.keys())[1]),
                ): vol.In(list(PAPER_WIDTHS.keys())),
                vol.Optional(
                    CONF_ENCODING,
                    default=current.get(CONF_ENCODING, DEFAULT_ENCODING),
                ): vol.In(ENCODINGS),
                vol.Optional(
                    CONF_TIMEOUT,
                    default=current.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                ): vol.All(int, vol.Range(min=5, max=60)),
                vol.Optional(
                    CONF_RFCOMM_CHANNEL,
                    default=current.get(CONF_RFCOMM_CHANNEL, DEFAULT_RFCOMM_CHANNEL),
                ): vol.All(int, vol.Range(min=1, max=30)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
