"""Sensor platform for ESC/POS Bluetooth Printer — status and diagnostics."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_MAC_ADDRESS,
    CONF_RFCOMM_CHANNEL,
    STATE_ONLINE,
    STATE_OFFLINE,
    STATE_ERROR,
    STATE_UNKNOWN,
)
from .coordinator import EscposPrinterCoordinator, PrinterCoordinatorData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for this printer."""
    coordinator: EscposPrinterCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        PrinterStatusSensor(coordinator, entry),
        PrinterPrintCountSensor(coordinator, entry),
        PrinterLastPrintSensor(coordinator, entry),
        PrinterLastErrorSensor(coordinator, entry),
    ]

    async_add_entities(entities)


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    """Build DeviceInfo for this printer."""
    mac = entry.data[CONF_MAC_ADDRESS]
    channel = entry.data[CONF_RFCOMM_CHANNEL]
    name = entry.data.get("printer_name") or f"ESC/POS {mac}"

    return DeviceInfo(
        identifiers={(DOMAIN, f"{mac}_{channel}")},
        name=name,
        manufacturer="ESC/POS Thermal Printer",
        model=f"Bluetooth RFCOMM Ch{channel}",
        sw_version="1.0.0",
        configuration_url=None,
    )


class PrinterStatusSensor(CoordinatorEntity[EscposPrinterCoordinator], SensorEntity):
    """Sensor showing online/offline status of the printer."""

    _attr_has_entity_name = True
    _attr_name = "Status"
    _attr_icon = "mdi:printer"

    def __init__(
        self,
        coordinator: EscposPrinterCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC_ADDRESS]
        channel = entry.data[CONF_RFCOMM_CHANNEL]
        self._attr_unique_id = f"{DOMAIN}_{mac}_{channel}_status"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str:
        """Return current printer status."""
        if self.coordinator.data is None:
            return STATE_UNKNOWN
        return self.coordinator.data.status

    @property
    def icon(self) -> str:
        status = self.native_value
        if status == STATE_ONLINE:
            return "mdi:printer-check"
        if status == STATE_OFFLINE:
            return "mdi:printer-off"
        return "mdi:printer-alert"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.printer_data
        attrs: dict[str, Any] = {
            "mac_address": self.coordinator.mac_address,
            "rfcomm_channel": self.coordinator.rfcomm_channel,
        }
        if data.last_seen:
            attrs["last_seen"] = datetime.fromtimestamp(data.last_seen).isoformat()
        return attrs


class PrinterPrintCountSensor(CoordinatorEntity[EscposPrinterCoordinator], SensorEntity):
    """Sensor showing total number of successful print jobs this session."""

    _attr_has_entity_name = True
    _attr_name = "Print Count"
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "jobs"

    def __init__(
        self,
        coordinator: EscposPrinterCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC_ADDRESS]
        channel = entry.data[CONF_RFCOMM_CHANNEL]
        self._attr_unique_id = f"{DOMAIN}_{mac}_{channel}_print_count"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int:
        if self.coordinator.data is None:
            return 0
        return self.coordinator.data.print_count


class PrinterLastPrintSensor(CoordinatorEntity[EscposPrinterCoordinator], SensorEntity):
    """Sensor showing timestamp of last successful print."""

    _attr_has_entity_name = True
    _attr_name = "Last Print"
    _attr_icon = "mdi:clock-check-outline"

    def __init__(
        self,
        coordinator: EscposPrinterCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC_ADDRESS]
        channel = entry.data[CONF_RFCOMM_CHANNEL]
        self._attr_unique_id = f"{DOMAIN}_{mac}_{channel}_last_print"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.printer_data
        if data.last_print_time is None:
            return None
        return datetime.fromtimestamp(data.last_print_time).isoformat()


class PrinterLastErrorSensor(CoordinatorEntity[EscposPrinterCoordinator], SensorEntity):
    """Sensor showing last error message (if any)."""

    _attr_has_entity_name = True
    _attr_name = "Last Error"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(
        self,
        coordinator: EscposPrinterCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC_ADDRESS]
        channel = entry.data[CONF_RFCOMM_CHANNEL]
        self._attr_unique_id = f"{DOMAIN}_{mac}_{channel}_last_error"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.printer_data
        return data.last_error

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.printer_data
        return {
            "error_count": data.error_count,
        }
