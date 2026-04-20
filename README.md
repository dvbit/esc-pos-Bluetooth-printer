# ESC/POS Bluetooth Printer — Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)
![Platform](https://img.shields.io/badge/platform-Linux%20only-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

A Home Assistant custom integration for **Bluetooth Classic (RFCOMM/SPP) ESC/POS thermal printers**. Print receipts, notifications, reports, QR codes, and barcodes directly from Home Assistant automations — no cloud, no external dependencies, fully local.

---

## ✨ Features

- **Zero external dependencies** — uses only Python stdlib (`socket`), no `python-escpos` or `PyBluez` required
- **Full UI configuration flow** — MAC address entry, automatic connection test, built-in Bluetooth pairing guide
- **One-click pairing** — dedicated "Pair Bluetooth" button that runs the pairing process automatically
- **Rich print jobs** — text, titles, bold, alignment, font sizes, QR codes, CODE128 barcodes, raw ESC/POS bytes
- **Multiple printers** — supports multiple config entries simultaneously
- **Health monitoring** — periodic connectivity check with online/offline sensor
- **Diagnostic sensors** — print count, last print timestamp, last error
- **Automatic retry** — 3 attempts with backoff on print failure
- **Multi-language** — English, Italian, French, German, Spanish

---

## ⚠️ System Requirements

| Requirement | Details |
|-------------|---------|
| **Home Assistant** | 2024.1 or newer |
| **OS** | **Linux only** — HassOS, Container (Docker on Linux), Core on Linux |
| **Bluetooth** | Bluetooth **Classic** (RFCOMM/SPP) — **not BLE** |
| **Adapter** | USB dongle or built-in Bluetooth on the HA host |
| **Python** | 3.11+ (included with HA) |

> ⚠️ **macOS and Windows are not supported.** Bluetooth Classic RFCOMM sockets require the Linux kernel. If you run HA on a Raspberry Pi, NUC, Beelink, or any Linux machine, you're good.

> ℹ️ This integration uses **Bluetooth Classic (SPP/RFCOMM)**, not BLE. Most inexpensive thermal printers (Netum, Xprinter, GOOJPRT, Rongta) use Bluetooth Classic.

---

## 🖨️ Compatible Printers

Any ESC/POS thermal printer with Bluetooth Classic (SPP) should work. Tested models:

| Printer | Width | RFCOMM Channel | Encoding | Status |
|---------|-------|----------------|----------|--------|
| Netum NT-5890 | 58mm | 1 | cp437 | ✅ Tested |
| Netum NT-1809 | 58mm | 1 | cp1252 | ✅ Tested |
| Xprinter XP-58 | 58mm | 1 | cp1252 | ✅ Tested |
| GOOJPRT PT-210 | 58mm | 1 | cp1252 | ✅ Tested |
| Rongta RPP02N | 58mm | 1 | cp437 | ✅ Tested |
| Epson TM-P20 | 80mm | 1 | cp1252 | ✅ Tested |

---

## 📦 Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**
3. Add this repository URL and select category **Integration**
4. Search for **"ESC/POS Bluetooth Printer"** and install
5. Restart Home Assistant

### Manual

1. Download the latest release ZIP
2. Extract the `custom_components/escpos_printer/` folder
3. Copy it to your HA config directory: `<config>/custom_components/escpos_printer/`
4. Restart Home Assistant

Your config directory structure should look like:

```
config/
└── custom_components/
    └── escpos_printer/
        ├── __init__.py
        ├── button.py
        ├── config_flow.py
        ├── const.py
        ├── coordinator.py
        ├── escpos_bt_pair.sh
        ├── escpos_raw.py
        ├── manifest.json
        ├── sensor.py
        ├── services.yaml
        ├── strings.json
        └── translations/
            ├── en.json
            ├── it.json
            ├── fr.json
            ├── de.json
            └── es.json
```

---

## 🔧 Pre-Configuration: Bluetooth Pairing

Before adding the integration, the printer must be **paired** with the HA host system. The integration provides two ways to do this.

### Method A — Automatic (recommended after first setup)

Once the integration is installed, a **"Pair Bluetooth"** button appears in the device card. Press it and HA will run the pairing script automatically, showing a notification with the result.

### Method B — Manual via Terminal

If you're setting up for the first time and the printer isn't paired yet, the config flow will guide you through this. You can also do it manually:

1. Install the **Terminal & SSH** add-on (Settings → Add-ons → Add-on Store)
2. Open the terminal and run:

```bash
bluetoothctl
power on
agent on
default-agent
scan on
```

3. Power cycle your printer. Wait for its MAC address to appear in the scan list.
4. Once you see it:

```bash
scan off
pair AA:BB:CC:DD:EE:FF
# Enter PIN when prompted (usually 0000 or 1234)
trust AA:BB:CC:DD:EE:FF
quit
```

### Finding Your Printer's MAC Address

The most reliable method is to **print a self-test page**:

- **Power off** the printer
- Hold the **Feed button** while powering on
- Release after the beep and test page prints
- The MAC address is printed on the test page

Alternatively, use a phone app to scan for Bluetooth devices near the printer.

### Common PIN Codes

| Brand | PIN |
|-------|-----|
| Netum | `0000` |
| Xprinter | `0000` |
| GOOJPRT | `0000` or `1234` |
| Rongta | `0000` |
| Generic | `0000` or `1234` |

---

## ⚙️ Configuration

1. Go to **Settings → Integrations → Add Integration**
2. Search for **"ESC/POS Bluetooth Printer"**
3. **Step 1 — Device**: Enter the MAC address and RFCOMM channel
4. **Step 2 — Connection test**: The integration tests the Bluetooth connection
   - If the printer is not paired, you'll see an inline pairing guide with your MAC pre-filled
5. **Step 3 — Printer settings**: Configure name, paper width, encoding, timeout
6. Click **Finish**

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| MAC Address | — | Bluetooth MAC of the printer (required) |
| RFCOMM Channel | `1` | Serial port channel, usually 1 or 2 |
| Printer Name | Auto | Friendly name shown in HA |
| Paper Width | `80mm (48 char)` | `58mm (32 char)` or `80mm (48 char)` |
| Character Encoding | `cp437` | Code page for text rendering |
| Connection Timeout | `15s` | Socket timeout per attempt |

You can change all options except MAC address via **Settings → Integrations → ESC/POS → Configure**.

---

## 🏠 Entities

After setup, the following entities are created per printer:

### Sensors

| Entity | Description | Example State |
|--------|-------------|---------------|
| `sensor.<name>_status` | Connectivity status | `online` / `offline` |
| `sensor.<name>_print_count` | Successful prints this session | `42` |
| `sensor.<name>_last_print` | Timestamp of last successful print | `2024-03-15T14:32:00` |
| `sensor.<name>_last_error` | Last error message, if any | `[Errno 111] Connection refused` |

### Buttons

| Entity | Description |
|--------|-------------|
| `button.<name>_pair_bluetooth` | Run Bluetooth pairing script automatically |
| `button.<name>_print_test_page` | Print a test page with timestamp |

---

## 🖨️ Printing — Services

### `escpos_printer.print`

Send a print job to a specific printer entry.

```yaml
service: escpos_printer.print
data:
  entry_id: "abc123def456"   # from Settings → Integrations → ESC/POS → entry URL
  message: "Hello, World!"
  title: "NOTIFICATION"      # optional — printed centered, bold, 2x size
  align: left                # left | center | right
  bold: false
  size: normal               # normal | large | small
  cut: true                  # auto-cut after printing
  qrcode: "https://example.com"   # optional QR code
  barcode: "1234567890"           # optional CODE128 barcode
  raw_bytes: "G1ZA"               # optional base64-encoded raw ESC/POS bytes
```

### `escpos_printer.send_<printer_name>`

A notify-style service registered per printer:

```yaml
service: escpos_printer.send_my_printer
data:
  message: "Order is ready!"
  data:
    title: "KITCHEN"
    cut: true
    align: center
```

---

## 🤖 Automation Examples

### Print a notification when the doorbell rings

```yaml
automation:
  - alias: "Print doorbell alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.doorbell
        to: "on"
    action:
      - service: escpos_printer.print
        data:
          entry_id: "abc123"
          title: "DOORBELL"
          message: >
            Someone at the door
            {{ now().strftime('%H:%M:%S') }}
          align: center
          cut: true
```

### Daily morning report

```yaml
automation:
  - alias: "Morning report"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: escpos_printer.print
        data:
          entry_id: "abc123"
          title: "MORNING REPORT"
          message: >
            {{ now().strftime('%A, %B %d %Y') }}

            Indoor: {{ states('sensor.living_room_temperature') }}°C
            Outdoor: {{ states('sensor.outdoor_temperature') }}°C
            Humidity: {{ states('sensor.living_room_humidity') }}%

            Alarm: {{ states('alarm_control_panel.home') }}
          cut: true
```

### Print a QR code for a shopping list URL

```yaml
service: escpos_printer.print
data:
  entry_id: "abc123"
  title: "SHOPPING LIST"
  message: "Scan to open the list"
  align: center
  qrcode: "https://ha.local/shopping-list"
  cut: true
```

### Print from a Node-RED flow or script

```yaml
service: escpos_printer.print
data:
  entry_id: "abc123"
  message: "Custom ESC/POS command follows"
  raw_bytes: "G1ZA"   # base64 of GS V 0x00 (full cut)
```

---

## 🔍 Troubleshooting

### "Invalid handler specified" on setup

The integration failed to load. Check the logs:

```bash
# In Terminal & SSH add-on:
ha core logs | grep -i escpos
```

Most common cause: syntax error in a file — make sure you copied the complete folder without corruption.

### "bluetooth_not_supported"

Your system does not support Bluetooth Classic RFCOMM sockets. This happens on:
- macOS (not supported)
- Windows (not supported)
- Linux without the `rfcomm` kernel module

On HassOS, verify the module is loaded:

```bash
lsmod | grep rfcomm
```

If not loaded:

```bash
modprobe rfcomm
```

### "device_not_found" after pairing

The printer was paired but the connection fails:

1. Verify the printer is powered on and not connected to another device (phone, tablet)
2. Remove the printer from any other paired device first
3. Check the pairing is still active: `bluetoothctl devices Paired`
4. Try pressing the **"Pair Bluetooth"** button in the device card to re-pair

### "connection_refused" — wrong channel

Try RFCOMM channel 2 or 3 in the integration options. Use `sdptool` to discover the correct channel:

```bash
sdptool browse AA:BB:CC:DD:EE:FF
```

Look for "Serial Port" or "RFCOMM" in the output.

### Characters print as garbage / wrong symbols

Change the **Character Encoding** in the integration options:

| Encoding | Use case |
|----------|----------|
| `cp437` | Default, most budget printers |
| `cp1252` | Western European characters (è, ü, ñ) |
| `cp850` | Alternative for Western European |
| `cp866` | Cyrillic |
| `latin-1` | ISO-8859-1 alternative |

### Printer offline after inactivity

This is normal — Bluetooth Classic connections are not persistent. The integration reconnects automatically on every print job. The health check sensor will show `offline` when the printer is sleeping or powered off, and return to `online` when it wakes up.

### Docker / Container users — Bluetooth not working

Make sure your `docker-compose.yml` has the D-Bus socket mounted:

```yaml
services:
  homeassistant:
    network_mode: host
    privileged: true
    volumes:
      - /var/run/dbus:/var/run/dbus   # required for Bluetooth
      - /config:/config
```

Without `/var/run/dbus`, the container cannot access the host Bluetooth stack even after pairing.

---

## 🏗️ Architecture

The integration is built with zero external dependencies — all ESC/POS commands are implemented in `escpos_raw.py` using raw bytes over a stdlib `socket.AF_BLUETOOTH` / `BTPROTO_RFCOMM` connection.

```
Home Assistant
│
├── config_flow.py       Config UI (3 steps + pairing guide)
├── coordinator.py       Health check (60s) + print job management
├── __init__.py          Entry setup, service registration
├── sensor.py            Status, print count, last print, last error
├── button.py            Pair Bluetooth, Print Test Page
├── escpos_raw.py        Zero-dep ESC/POS implementation
└── escpos_bt_pair.sh    Bash pairing helper (copied to /config/)
```

**Connection model**: the integration uses **lazy connect** — the RFCOMM socket is opened only when a print job is sent, then immediately closed. This avoids maintaining a persistent connection that would drop unpredictably. The health check also opens and closes a socket briefly every 60 seconds to update the status sensor.

**Thread safety**: all Bluetooth socket operations are blocking and run in `hass.async_add_executor_job()` to avoid blocking the HA event loop.

---

## 📄 ESC/POS Command Reference

The following ESC/POS commands are implemented in `escpos_raw.py`:

| Command | Bytes | Description |
|---------|-------|-------------|
| Initialize | `ESC @` | Reset printer to defaults |
| Align left | `ESC a 0` | Left-align text |
| Align center | `ESC a 1` | Center-align text |
| Align right | `ESC a 2` | Right-align text |
| Bold on/off | `ESC E 1/0` | Toggle bold |
| Size normal | `GS ! 0x00` | 1x width, 1x height |
| Size large | `GS ! 0x11` | 2x width, 2x height |
| Feed N lines | `ESC d N` | Advance paper |
| Code page | `ESC t N` | Select character table |
| Cut full | `GS V 0x00` | Full paper cut |
| QR code | `GS ( k` | Print QR code (model 2) |
| Barcode | `GS k 0x49` | Print CODE128 barcode |

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Pull requests are welcome. When adding features, please:

1. Keep the zero-dependency philosophy — stdlib only in `escpos_raw.py`
2. Test on actual hardware before submitting
3. Update translations for all 5 languages (en, it, fr, de, es)
4. Verify Python syntax: `python3 -c "import ast; ast.parse(open('file.py').read())"`

---

## 📋 Changelog

### v1.1.0
- Replaced `python-escpos` with zero-dependency `escpos_raw.py`
- Removed all external requirements — no more install failures
- Added automatic Bluetooth pairing guide in config flow
- Added "Pair Bluetooth" button entity
- Added "Print Test Page" button entity
- Added French, German, Spanish translations
- Fixed syntax error in `__init__.py`

### v1.0.0
- Initial release
- Config flow UI
- REST polling coordinator
- Print service
- Status/count/error sensors
