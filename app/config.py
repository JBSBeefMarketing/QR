"""Runtime configuration.

The resolver domain is the one setting that genuinely matters. It is baked
into every QR code that gets printed and can never change afterwards, so it is
configurable here rather than hardcoded anywhere.

JBS owns jbs-qr.com, purchased specifically for this. Codes are printed
against the bare domain rather than a subdomain because a shorter URL packs
into a smaller QR symbol - at a fixed printed size that means larger modules
and a more forgiving scan:

    https://jbs-qr.com/01/{GTIN}      -> version 3, 29x29
    https://id.jbs-qr.com/01/{GTIN}   -> version 3, 29x29  (no gain, longer)

To run against the real domain:

    set JBS_DL_DOMAIN=jbs-qr.com
    set JBS_DL_SCHEME=https

Without those it falls back to this machine's LAN address, so codes generated
by the prototype are scannable from a phone on the same Wi-Fi.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Where the database and generated code images live.
#
# Locally this is ./data. On a host, it must point at a persistent disk -
# anything written to a normal container filesystem is erased on every deploy
# and every restart, which would silently throw away the catalog.
DATA_DIR = Path(os.environ.get("JBS_DL_DATA_DIR") or (PROJECT_ROOT / "data"))

# Admin login. There is exactly one shared account; this is a small internal
# tool, not a multi-user system, and inventing user management here would be
# scope the project does not need.
ADMIN_USER = os.environ.get("JBS_DL_ADMIN_USER", "jbs")
ADMIN_PASSWORD = os.environ.get("JBS_DL_ADMIN_PASSWORD", "")


def lan_address(port: int = 8000) -> str:
    """Best-effort LAN IP for this machine.

    Opens a UDP socket to an external address - no packets are sent, it just
    makes the OS pick the interface it would route through.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        host = sock.getsockname()[0]
    except OSError:
        host = "127.0.0.1"
    finally:
        sock.close()
    return f"{host}:{port}"


PORT = int(os.environ.get("JBS_DL_PORT", "8000"))
DOMAIN = os.environ.get("JBS_DL_DOMAIN") or lan_address(PORT)
SCHEME = os.environ.get("JBS_DL_SCHEME") or ("https" if os.environ.get("JBS_DL_DOMAIN") else "http")

# True once a real domain is configured. The UI uses this to keep reminding
# people that the printed URL is not final yet.
IS_PROVISIONAL = not bool(os.environ.get("JBS_DL_DOMAIN"))

TARGET_DOMAIN = "jbs-qr.com"  # owned by JBS; what production resolves on

# Print the scheme and host in capitals - HTTPS://JBS-QR.COM/01/{GTIN} - so
# the QR encoder can use alphanumeric mode and produce a smaller, more robust
# symbol. Confirmed acceptable with GS1 (Oct 2026). Only the scheme and host
# are capitalised; see gs1._uppercase_prefix.
UPPERCASE_URI = os.environ.get("JBS_DL_UPPERCASE", "1") not in ("0", "false", "False")
