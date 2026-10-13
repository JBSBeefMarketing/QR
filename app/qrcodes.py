"""QR code generation.

Emits PNG (for proofing and digital use) and SVG (for print - packaging
artwork should never be handed a raster).
"""

from __future__ import annotations

import re

import segno

from . import config
from .colors import parse_hex

OUT_DIR = config.DATA_DIR / "codes"

# Error correction level. 'm' (~15%) is the usual choice for packaging: 'l'
# is fragile on a printed surface that gets scuffed or creased, and 'h' grows
# the symbol enough to matter in a crowded label layout.
ERROR_LEVEL = "m"

DEFAULT_DARK = "#000000"
DEFAULT_LIGHT = "#ffffff"


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-")[:80] or "code"


def generate(
    url: str,
    name: str,
    dark: str = DEFAULT_DARK,
    light: str = DEFAULT_LIGHT,
) -> tuple[str, str]:
    """Write PNG and SVG for a URL. Returns paths relative to data/.

    `dark` is the module colour, `light` the background. Contrast is the
    caller's decision - see colors.qr_contrast_warning - but it is checked and
    surfaced in the UI, because a low-contrast code fails at the shelf rather
    than at design time.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = _slug(name)
    dark = parse_hex(dark, DEFAULT_DARK)
    light = parse_hex(light, DEFAULT_LIGHT)

    qr = segno.make(url, error=ERROR_LEVEL)

    png_path = OUT_DIR / f"{stem}.png"
    svg_path = OUT_DIR / f"{stem}.svg"

    # scale 10 gives a proofing image big enough to scan off a screen.
    qr.save(png_path, scale=10, border=4, dark=dark, light=light)
    qr.save(svg_path, scale=10, border=4, dark=dark, light=light)

    return f"codes/{png_path.name}", f"codes/{svg_path.name}"
