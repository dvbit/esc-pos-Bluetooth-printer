"""Coordinator for ESC/POS Bluetooth Printer — manages connection state and print jobs."""
from __future__ import annotations

import asyncio
import logging
import socket
import time
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_RFCOMM_CHANNEL,
    CONF_TIMEOUT,
    CONF_ENCODING,
    CONF_PAPER_WIDTH,
    DEFAULT_TIMEOUT,
    DEFAULT_ENCODING,
    HEALTH_CHECK_INTERVAL,
    MAX_PRINT_RETRIES,
    RETRY_DELAY,
    PAPER_WIDTHS,
    STATE_ONLINE,
    STATE_OFFLINE,
)
from .escpos_raw import RawEscposPrinter

_LOGGER = logging.getLogger(__name__)


class PrinterCoordinatorData:
    """Holds current printer state."""

    def __init__(self) -> None:
        self.status: str = STATE_OFFLINE
        self.last_seen: float | None = None
        self.last_error: str | None = None
        self.last_print_time: float | None = None
        self.print_count: int = 0
        self.error_count: int = 0


def _health_check_blocking(mac: str, channel: int, timeout: int) -> bool:
    """Open and immediately close RFCOMM socket to check reachability."""
    try:
        sock = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM,
        )
        sock.settimeout(timeout)
        sock.connect((mac, channel))
        sock.close()
        return True
    except OSError as err:
        _LOGGER.debug("Health check failed for %s: %s", mac, err)
        return False


def _print_job_blocking(
    mac: str,
    channel: int,
    timeout: int,
    encoding: str,
    char_width: int,
    job: dict[str, Any],
) -> None:
    """
    Execute a print job via raw RFCOMM socket.
    Uses RawEscposPrinter — zero external dependencies.
    Blocking — must run in executor.
    """
    import base64

    raw_bytes = None
    if job.get("raw_bytes"):
        try:
            raw_bytes = base64.b64decode(job["raw_bytes"])
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Invalid base64 raw_bytes: %s", err)

    with RawEscposPrinter(mac=mac, channel=channel, timeout=timeout) as printer:
        printer.print_job(
            message=job.get("message", ""),
            title=job.get("title", ""),
            align=job.get("align", "left"),
            bold=job.get("bold", False),
            size=job.get("size", "normal"),
            cut=job.get("cut", True),
            qrcode=job.get("qrcode"),
            barcode=job.get("barcode"),
            raw_bytes=raw_bytes,
            encoding=encoding,
            char_width=char_width,
        )


class EscposPrinterCoordinator(DataUpdateCoordinator[PrinterCoordinatorData]):
    """Coordinator for ESC/POS printer."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config: dict[str, Any],
    ) -> None:
        self._mac: str = config[CONF_MAC_ADDRESS]
        self._channel: int = config[CONF_RFCOMM_CHANNEL]
        self._timeout: int = config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        self._encoding: str = config.get(CONF_ENCODING, DEFAULT_ENCODING)
        paper_width_key = config.get(CONF_PAPER_WIDTH, list(PAPER_WIDTHS.keys())[1])
        self._char_width: int = PAPER_WIDTHS.get(paper_width_key, 48)
        self._entry_id = entry_id
        self._data = PrinterCoordinatorData()

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self._mac}",
            update_interval=timedelta(seconds=HEALTH_CHECK_INTERVAL),
        )

    @property
    def mac_address(self) -> str:
        return self._mac

    @property
    def rfcomm_channel(self) -> int:
        return self._channel

    async def _async_update_data(self) -> PrinterCoordinatorData:
        """Health check — called on schedule."""
        reachable = await self.hass.async_add_executor_job(
            _health_check_blocking,
            self._mac,
            self._channel,
            min(self._timeout, 8),
        )

        if reachable:
            self._data.status = STATE_ONLINE
            self._data.last_seen = time.time()
            self._data.last_error = None
        else:
            self._data.status = STATE_OFFLINE

        return self._data

    async def async_print(self, job: dict[str, Any]) -> bool:
        """Send a print job. Returns True on success."""
        last_error: Exception | None = None

        for attempt in range(1, MAX_PRINT_RETRIES + 1):
            _LOGGER.debug(
                "Print attempt %d/%d to %s ch%d",
                attempt, MAX_PRINT_RETRIES, self._mac, self._channel,
            )
            try:
                await self.hass.async_add_executor_job(
                    _print_job_blocking,
                    self._mac,
                    self._channel,
                    self._timeout,
                    self._encoding,
                    self._char_width,
                    job,
                )
                self._data.status = STATE_ONLINE
                self._data.last_seen = time.time()
                self._data.last_print_time = time.time()
                self._data.print_count += 1
                self._data.last_error = None
                self.async_update_listeners()
                _LOGGER.info("Print job sent successfully to %s", self._mac)
                return True

            except Exception as err:  # noqa: BLE001
                last_error = err
                _LOGGER.warning(
                    "Print attempt %d failed for %s: %s",
                    attempt, self._mac, err,
                )
                if attempt < MAX_PRINT_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)

        self._data.status = STATE_OFFLINE
        self._data.error_count += 1
        self._data.last_error = str(last_error)
        self.async_update_listeners()
        _LOGGER.error(
            "All %d print attempts failed for %s: %s",
            MAX_PRINT_RETRIES, self._mac, last_error,
        )
        return False

    @property
    def printer_data(self) -> PrinterCoordinatorData:
        return self._data
