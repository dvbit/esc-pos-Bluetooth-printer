"""
ESC/POS raw command implementation — zero external dependencies.
Implements the minimal ESC/POS command set needed for text printing,
QR codes, barcodes, and paper cut via direct RFCOMM socket.
"""
from __future__ import annotations

import socket
import struct
from typing import Generator

# ---------------------------------------------------------------------------
# ESC/POS command constants
# ---------------------------------------------------------------------------

ESC = b"\x1b"
GS  = b"\x1d"
FS  = b"\x1c"
DLE = b"\x10"

# Initialization
INIT            = ESC + b"@"

# Line feed
LF              = b"\n"

# Cut paper (full cut)
CUT_FULL        = GS + b"V" + b"\x00"
# Cut paper (partial cut)
CUT_PARTIAL     = GS + b"V" + b"\x01"

# Text align
ALIGN_LEFT      = ESC + b"a\x00"
ALIGN_CENTER    = ESC + b"a\x01"
ALIGN_RIGHT     = ESC + b"a\x02"

# Bold
BOLD_ON         = ESC + b"E\x01"
BOLD_OFF        = ESC + b"E\x00"

# Underline
UNDERLINE_OFF   = ESC + b"-\x00"

# Double height+width (2x)
SIZE_NORMAL     = GS  + b"!\x00"
SIZE_LARGE      = GS  + b"!\x11"   # 2x width + 2x height
SIZE_SMALL      = GS  + b"!\x00"   # same as normal for most printers

# Feed N lines
def feed(n: int = 1) -> bytes:
    return ESC + b"d" + bytes([n])

# Select character code page
def codepage(page: int) -> bytes:
    return ESC + b"t" + bytes([page])

# Known code pages
CODEPAGE_MAP = {
    "cp437":  0,
    "cp850":  2,
    "cp860":  3,
    "cp863":  4,
    "cp865":  5,
    "cp1252": 16,
    "cp866":  17,
    "cp852":  18,
    "latin-1": 16,
    "utf-8":  0,   # fallback to cp437 for raw printing
}

# ---------------------------------------------------------------------------
# QR Code (GS ( k)
# ---------------------------------------------------------------------------

def qr_code(data: str, size: int = 6) -> bytes:
    """Generate ESC/POS QR code command sequence."""
    encoded = data.encode("utf-8")
    length = len(encoded) + 3
    lo = length & 0xFF
    hi = (length >> 8) & 0xFF

    cmds = bytearray()
    # Set model (model 2)
    cmds += GS + b"(k" + b"\x04\x00\x31\x41\x32\x00"
    # Set size
    cmds += GS + b"(k" + b"\x03\x00\x31\x43" + bytes([size])
    # Set error correction (M = 1)
    cmds += GS + b"(k" + b"\x03\x00\x31\x45\x31"
    # Store data
    cmds += GS + b"(k" + bytes([lo, hi]) + b"\x31\x50\x30" + encoded
    # Print
    cmds += GS + b"(k" + b"\x03\x00\x31\x51\x30"
    return bytes(cmds)


# ---------------------------------------------------------------------------
# Barcode (CODE128)
# ---------------------------------------------------------------------------

def barcode_code128(data: str, height: int = 60) -> bytes:
    """Generate ESC/POS CODE128 barcode."""
    encoded = data.encode("ascii")
    cmds = bytearray()
    # Set barcode height
    cmds += GS + b"h" + bytes([height])
    # Set HRI (human readable) below barcode
    cmds += GS + b"H\x02"
    # Print CODE128
    cmds += GS + b"k\x49" + bytes([len(encoded)]) + encoded
    return bytes(cmds)


# ---------------------------------------------------------------------------
# Text encoding helper
# ---------------------------------------------------------------------------

def encode_text(text: str, encoding: str) -> bytes:
    """Encode text to bytes, replacing unencodable chars with '?'."""
    if encoding.lower() == "utf-8":
        encoding = "cp437"  # Most thermal printers don't do real UTF-8
    try:
        return text.encode(encoding, errors="replace")
    except LookupError:
        return text.encode("cp437", errors="replace")


# ---------------------------------------------------------------------------
# Main printer class — pure socket, no external deps
# ---------------------------------------------------------------------------

class RawEscposPrinter:
    """
    Minimal ESC/POS printer over RFCOMM socket.
    No external dependencies — uses only stdlib socket.
    """

    def __init__(self, mac: str, channel: int, timeout: int = 15) -> None:
        self._mac = mac
        self._channel = channel
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._buffer = bytearray()

    def connect(self) -> None:
        """Open RFCOMM socket connection."""
        self._sock = socket.socket(
            socket.AF_BLUETOOTH,
            socket.SOCK_STREAM,
            socket.BTPROTO_RFCOMM,
        )
        self._sock.settimeout(self._timeout)
        self._sock.connect((self._mac, self._channel))

    def close(self) -> None:
        """Close socket."""
        if self._sock:
            try:
                self._sock.close()
            except Exception:  # noqa: BLE001
                pass
            self._sock = None

    def _write(self, data: bytes) -> None:
        """Send raw bytes to printer."""
        if not self._sock:
            raise RuntimeError("Printer not connected")
        self._sock.sendall(data)

    def __enter__(self) -> "RawEscposPrinter":
        self.connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # --- High level print job ---

    def print_job(
        self,
        message: str,
        title: str = "",
        align: str = "left",
        bold: bool = False,
        size: str = "normal",
        cut: bool = True,
        qrcode: str | None = None,
        barcode: str | None = None,
        raw_bytes: bytes | None = None,
        encoding: str = "cp437",
        char_width: int = 48,
    ) -> None:
        """Execute a complete print job."""
        cp = CODEPAGE_MAP.get(encoding.lower(), 0)

        # Init printer
        self._write(INIT)
        self._write(codepage(cp))

        # --- Title ---
        if title:
            self._write(ALIGN_CENTER)
            self._write(BOLD_ON)
            self._write(SIZE_LARGE)
            self._write(encode_text(title + "\n", encoding))
            self._write(SIZE_NORMAL)
            self._write(BOLD_OFF)
            separator = "-" * (char_width // 2) + "\n"  # half width because 2x size
            self._write(ALIGN_CENTER)
            self._write(SIZE_NORMAL)
            self._write(encode_text(separator, encoding))

        # --- Align ---
        align_cmd = {
            "left": ALIGN_LEFT,
            "center": ALIGN_CENTER,
            "right": ALIGN_RIGHT,
        }.get(align, ALIGN_LEFT)
        self._write(align_cmd)

        # --- Size ---
        size_cmd = {
            "normal": SIZE_NORMAL,
            "large": SIZE_LARGE,
            "small": SIZE_SMALL,
        }.get(size, SIZE_NORMAL)
        self._write(size_cmd)

        # --- Bold ---
        if bold:
            self._write(BOLD_ON)

        # --- Message ---
        if message:
            if not message.endswith("\n"):
                message += "\n"
            self._write(encode_text(message, encoding))

        # Reset formatting
        self._write(BOLD_OFF)
        self._write(SIZE_NORMAL)
        self._write(ALIGN_LEFT)

        # --- QR Code ---
        if qrcode:
            self._write(ALIGN_CENTER)
            self._write(feed(1))
            self._write(qr_code(qrcode, size=6))
            self._write(feed(1))
            self._write(ALIGN_LEFT)

        # --- Barcode ---
        if barcode:
            self._write(ALIGN_CENTER)
            self._write(feed(1))
            self._write(barcode_code128(barcode))
            self._write(feed(1))
            self._write(ALIGN_LEFT)

        # --- Raw bytes ---
        if raw_bytes:
            self._write(raw_bytes)

        # --- Feed and cut ---
        self._write(feed(3))
        if cut:
            self._write(CUT_FULL)
