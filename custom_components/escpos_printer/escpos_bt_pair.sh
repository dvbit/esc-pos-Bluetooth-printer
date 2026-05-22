#!/usr/bin/env bash
# =============================================================================
# escpos_bt_pair.sh — Pairing automatico stampante ESC/POS Bluetooth Classic
# 
# Uso:
#   bash escpos_bt_pair.sh AA:BB:CC:DD:EE:FF [PIN]
#   bash escpos_bt_pair.sh AA:BB:CC:DD:EE:FF 0000
#
# Il PIN è opzionale — default 0000 (standard Netum e la maggior parte
# delle stampanti termiche economiche).
#
# Pensato per girare su Home Assistant OS via shell_command o Terminal.
# =============================================================================

set -euo pipefail

# --- Parametri ---
MAC="${1:-}"
PIN="${2:-0000}"
SCAN_TIMEOUT=20      # secondi di scansione per trovare il device
PAIR_TIMEOUT=15      # secondi max per completare il pairing

# --- Colori output ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

# --- Validazione MAC ---
if [[ -z "$MAC" ]]; then
    log_error "MAC address mancante."
    echo "Uso: $0 AA:BB:CC:DD:EE:FF [PIN]"
    exit 1
fi

if ! echo "$MAC" | grep -qE '^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'; then
    log_error "MAC address non valido: $MAC"
    echo "Formato atteso: AA:BB:CC:DD:EE:FF"
    exit 1
fi

MAC="${MAC^^}"  # Uppercase

echo ""
echo "=============================================="
echo "  ESC/POS Bluetooth Pairing Tool"
echo "=============================================="
echo "  MAC:  $MAC"
echo "  PIN:  $PIN"
echo "=============================================="
echo ""

# --- Verifica bluetoothctl disponibile ---
if ! command -v bluetoothctl &>/dev/null; then
    log_error "bluetoothctl non trovato. Assicurati che BlueZ sia installato."
    exit 1
fi

# --- Verifica controller BT attivo ---
log_info "Verifica controller Bluetooth..."
if ! bluetoothctl show | grep -q "Powered: yes"; then
    log_warn "Controller BT spento — tento di accenderlo..."
    bluetoothctl power on
    sleep 2
    if ! bluetoothctl show | grep -q "Powered: yes"; then
        log_error "Impossibile accendere il controller Bluetooth."
        log_error "Verifica che il dongle/adattatore BT sia collegato."
        exit 1
    fi
fi
log_ok "Controller Bluetooth attivo."

# --- Rimuovi eventuale pairing precedente ---
if bluetoothctl devices Paired | grep -qi "$MAC"; then
    log_warn "Device già accoppiato — rimuovo il pairing precedente..."
    bluetoothctl remove "$MAC" || true
    sleep 1
fi

# --- Scansione per verificare che il device sia visibile ---
log_info "Scansione BT in corso (${SCAN_TIMEOUT}s) — assicurati che la stampante sia accesa e discoverable..."

# Avvia scan in background tramite expect-like approach con bluetoothctl
bluetoothctl scan on &
SCAN_PID=$!
sleep "$SCAN_TIMEOUT"
kill "$SCAN_PID" 2>/dev/null || true
bluetoothctl scan off 2>/dev/null || true
sleep 1

# Verifica se il device è ora noto a bluetoothctl
if ! bluetoothctl info "$MAC" 2>/dev/null | grep -q "Device"; then
    log_warn "Device $MAC non trovato durante la scansione."
    log_warn "Possibili cause:"
    log_warn "  1. La stampante non è in modalità discoverable (LED deve lampeggiare)"
    log_warn "  2. Il MAC non è corretto"
    log_warn "  3. La stampante è già connessa ad un altro device (es. telefono)"
    log_warn ""
    log_warn "Tentativo di pairing diretto comunque..."
fi

# --- Pairing tramite expect (se disponibile) o bluetoothctl diretto ---
log_info "Avvio pairing con $MAC (PIN: $PIN)..."

# Funzione pairing con expect (gestisce il PIN automaticamente)
do_pair_with_expect() {
    expect <<EOF
set timeout $PAIR_TIMEOUT
spawn bluetoothctl
expect "Agent registered"
send "agent on\r"
expect "#"
send "default-agent\r"
expect "#"
send "pair $MAC\r"
expect {
    "Enter PIN code:" {
        send "$PIN\r"
        expect {
            "Pairing successful" { exit 0 }
            "Failed to pair"     { exit 1 }
            timeout              { exit 2 }
        }
    }
    "Pairing successful" { exit 0 }
    "Failed to pair"     { exit 1 }
    timeout              { exit 2 }
}
EOF
}

# Funzione pairing senza expect (fallback)
do_pair_without_expect() {
    # Usa bluetoothctl in modalità comandi
    {
        echo "agent on"
        echo "default-agent"
        echo "pair $MAC"
        sleep "$PAIR_TIMEOUT"
        echo "quit"
    } | bluetoothctl
}

PAIR_OK=false

if command -v expect &>/dev/null; then
    log_info "Uso 'expect' per gestione PIN automatica..."
    if do_pair_with_expect; then
        PAIR_OK=true
    fi
else
    log_warn "'expect' non disponibile — pairing senza gestione PIN automatica."
    log_warn "Se la stampante chiede un PIN, potrebbe essere necessario inserirlo manualmente."
    do_pair_without_expect
    # Verifica risultato
    if bluetoothctl info "$MAC" 2>/dev/null | grep -q "Paired: yes"; then
        PAIR_OK=true
    fi
fi

# --- Verifica pairing ---
if bluetoothctl info "$MAC" 2>/dev/null | grep -q "Paired: yes"; then
    PAIR_OK=true
fi

if ! $PAIR_OK; then
    log_error "Pairing fallito per $MAC"
    log_error "Prova manualmente:"
    log_error "  bluetoothctl"
    log_error "  pair $MAC"
    exit 1
fi

log_ok "Pairing completato con successo!"

# --- Trust (fondamentale per riconnessione automatica) ---
log_info "Imposto 'trust' per riconnessione automatica..."
bluetoothctl trust "$MAC"
log_ok "Device trusted."

# --- Verifica finale ---
echo ""
echo "=============================================="
echo "  Stato finale device $MAC"
echo "=============================================="
bluetoothctl info "$MAC" 2>/dev/null | grep -E "Name|Paired|Trusted|Connected|Class" || true
echo "=============================================="
echo ""
log_ok "Stampante pronta. Torna nel config flow di Home Assistant e riprova."
echo ""
