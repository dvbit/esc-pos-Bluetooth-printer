"""Constants for the ESC/POS Bluetooth Printer integration."""

DOMAIN = "escpos_printer"

# Config entry keys
CONF_MAC_ADDRESS = "mac_address"
CONF_RFCOMM_CHANNEL = "rfcomm_channel"
CONF_PRINTER_NAME = "printer_name"
CONF_PAPER_WIDTH = "paper_width"
CONF_ENCODING = "encoding"
CONF_TIMEOUT = "timeout"

# Defaults
DEFAULT_RFCOMM_CHANNEL = 1
DEFAULT_PAPER_WIDTH = 80
DEFAULT_ENCODING = "cp1252"
DEFAULT_TIMEOUT = 15  # seconds

# Paper widths (characters)
PAPER_WIDTH_58MM = 58
PAPER_WIDTH_80MM = 80

PAPER_WIDTHS = {
    "58mm (32 char)": 32,
    "80mm (48 char)": 48,
}

# Encodings supported by most thermal printers
ENCODINGS = [
    "cp1252",
    "cp437",
    "utf-8",
    "cp850",
    "latin-1",
]

# Platforms
PLATFORMS = ["notify", "sensor"]

# Health check interval (seconds)
HEALTH_CHECK_INTERVAL = 60

# Max retry attempts for printing
MAX_PRINT_RETRIES = 3
RETRY_DELAY = 1.5  # seconds

# Sensor states
STATE_ONLINE = "online"
STATE_OFFLINE = "offline"
STATE_ERROR = "error"
STATE_UNKNOWN = "unknown"

# Service data keys
SERVICE_DATA_TITLE = "title"
SERVICE_DATA_CUT = "cut"
SERVICE_DATA_BOLD = "bold"
SERVICE_DATA_ALIGN = "align"
SERVICE_DATA_SIZE = "size"
SERVICE_DATA_QRCODE = "qrcode"
SERVICE_DATA_BARCODE = "barcode"
SERVICE_DATA_RAW_BYTES = "raw_bytes"

# Align options
ALIGN_LEFT = "left"
ALIGN_CENTER = "center"
ALIGN_RIGHT = "right"

# Size options
SIZE_NORMAL = "normal"
SIZE_LARGE = "large"
SIZE_SMALL = "small"
