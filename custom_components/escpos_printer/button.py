"""Button platform for ESC/POS Printer — Bluetooth pairing trigger."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_MAC_ADDRESS, CONF_RFCOMM_CHANNEL
from .coordinator import EscposPrinterCoordinator

_LOGGER = logging.getLogger(__name__)

# Path dove copiamo lo script di pairing nella config dir di HA
PAIRING_SCRIPT_NAME = "escpos_bt_pair.sh"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities."""
    coordinator: EscposPrinterCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Copia lo script di pairing nella config dir se non già presente
    await hass.async_add_executor_job(_ensure_pairing_script, hass.config.config_dir)

    async_add_entities([
        PairingButton(coordinator, entry, hass.config.config_dir),
        TestPrintButton(coordinator, entry),
    ])


def _ensure_pairing_script(config_dir: str) -> str:
    """
    Copia lo script di pairing nella config dir di HA se non esiste.
    Restituisce il path completo dello script.
    """
    dest = os.path.join(config_dir, PAIRING_SCRIPT_NAME)
    if not os.path.exists(dest):
        # Cerca lo script nella stessa directory del modulo
        src = os.path.join(os.path.dirname(__file__), PAIRING_SCRIPT_NAME)
        if os.path.exists(src):
            shutil.copy2(src, dest)
            os.chmod(dest, 0o755)
            _LOGGER.info("Script pairing copiato in %s", dest)
        else:
            _LOGGER.warning(
                "Script pairing non trovato in %s — pairing automatico non disponibile", src
            )
    return dest


def _run_pairing_script(script_path: str, mac: str, pin: str = "0000") -> tuple[bool, str]:
    """
    Esegue lo script di pairing. Blocking — chiamare in executor.
    Restituisce (successo, output).
    """
    if not os.path.exists(script_path):
        return False, f"Script non trovato: {script_path}"

    try:
        result = subprocess.run(
            ["bash", script_path, mac, pin],
            capture_output=True,
            text=True,
            timeout=60,  # max 60 secondi per l'intero processo
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Timeout durante il pairing (60s)"
    except Exception as err:  # noqa: BLE001
        return False, f"Errore: {err}"


def _device_info_from_entry(entry: ConfigEntry) -> DeviceInfo:
    mac = entry.data[CONF_MAC_ADDRESS]
    channel = entry.data[CONF_RFCOMM_CHANNEL]
    name = entry.data.get("printer_name") or f"ESC/POS {mac}"
    return DeviceInfo(
        identifiers={(DOMAIN, f"{mac}_{channel}")},
        name=name,
        manufacturer="ESC/POS Thermal Printer",
        model=f"Bluetooth RFCOMM Ch{channel}",
    )


class PairingButton(ButtonEntity):
    """Pulsante per avviare il pairing Bluetooth della stampante."""

    _attr_has_entity_name = True
    _attr_name = "Accoppia Bluetooth"
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(
        self,
        coordinator: EscposPrinterCoordinator,
        entry: ConfigEntry,
        config_dir: str,
    ) -> None:
        mac = entry.data[CONF_MAC_ADDRESS]
        channel = entry.data[CONF_RFCOMM_CHANNEL]
        self._attr_unique_id = f"{DOMAIN}_{mac}_{channel}_pair_button"
        self._attr_device_info = _device_info_from_entry(entry)
        self._mac = mac
        self._config_dir = config_dir
        self._script_path = os.path.join(config_dir, PAIRING_SCRIPT_NAME)

    async def async_press(self) -> None:
        """Avvia il pairing quando il pulsante viene premuto."""
        _LOGGER.info("Avvio pairing Bluetooth per %s", self._mac)

        success, output = await self.hass.async_add_executor_job(
            _run_pairing_script,
            self._script_path,
            self._mac,
            "0000",
        )

        if success:
            _LOGGER.info("Pairing completato per %s:\n%s", self._mac, output)
            self.hass.components.persistent_notification.async_create(
                f"✅ **Pairing completato** per `{self._mac}`\n\n"
                "La stampante è ora accoppiata con Home Assistant. "
                "Puoi riprovare la connessione dall'integrazione.",
                title="ESC/POS Printer — Pairing OK",
                notification_id=f"escpos_pair_{self._mac}",
            )
        else:
            _LOGGER.error("Pairing fallito per %s:\n%s", self._mac, output)
            self.hass.components.persistent_notification.async_create(
                f"❌ **Pairing fallito** per `{self._mac}`\n\n"
                f"```\n{output[-800:]}\n```\n\n"
                "Verifica che la stampante sia accesa e in modalità discoverable "
                "(LED deve lampeggiare). Se è connessa al telefono, prima rimuovila "
                "dalle impostazioni BT del telefono.",
                title="ESC/POS Printer — Pairing Fallito",
                notification_id=f"escpos_pair_fail_{self._mac}",
            )


class TestPrintButton(ButtonEntity):
    """Pulsante per stampare una pagina di test."""

    _attr_has_entity_name = True
    _attr_name = "Stampa Test"
    _attr_icon = "mdi:printer-check"

    def __init__(
        self,
        coordinator: EscposPrinterCoordinator,
        entry: ConfigEntry,
    ) -> None:
        mac = entry.data[CONF_MAC_ADDRESS]
        channel = entry.data[CONF_RFCOMM_CHANNEL]
        self._attr_unique_id = f"{DOMAIN}_{mac}_{channel}_test_print_button"
        self._attr_device_info = _device_info_from_entry(entry)
        self._coordinator = coordinator
        self._mac = mac

    async def async_press(self) -> None:
        """Stampa una pagina di test."""
        from datetime import datetime

        job = {
            "title": "TEST STAMPA",
            "message": (
                f"Home Assistant\n"
                f"ESC/POS Integration\n"
                f"\n"
                f"MAC: {self._mac}\n"
                f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
                f"\n"
                f"Se leggi questo messaggio\n"
                f"la stampante funziona!"
            ),
            "align": "center",
            "cut": True,
            "bold": False,
        }

        success = await self._coordinator.async_print(job)

        if success:
            _LOGGER.info("Stampa test completata per %s", self._mac)
        else:
            _LOGGER.error("Stampa test fallita per %s", self._mac)
            self.hass.components.persistent_notification.async_create(
                f"❌ **Stampa test fallita** per `{self._mac}`\n\n"
                "Verifica che la stampante sia accesa e accoppiata.",
                title="ESC/POS Printer — Test Fallito",
                notification_id=f"escpos_test_fail_{self._mac}",
            )
