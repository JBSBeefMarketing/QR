"""Hex colour parsing and contrast checking.

Colour is not purely cosmetic here. A QR code is read by a camera resolving
light and dark modules, so a low-contrast pair produces a code that looks fine
on screen and fails at the shelf. ISO/IEC 15415 grades print contrast for this
reason. We let anyone pick any colour, but we tell them when the pair is going
to cause trouble - a warning now is cheaper than a reprint.
"""

from __future__ import annotations

import re

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Contrast ratio thresholds (WCAG-style 1..21 scale).
# QR readers are more tolerant than human readers, but not by much once you
# add print variation, film, and a phone camera in poor store lighting.
QR_CONTRAST_GOOD = 7.0
QR_CONTRAST_MARGINAL = 4.0
TEXT_CONTRAST_MIN = 4.5


class ColorError(ValueError):
    pass


def parse_hex(value: str, default: str | None = None) -> str:
    """Normalise to #rrggbb. Falls back to default when given nothing."""
    if value is None or not str(value).strip():
        if default is None:
            raise ColorError("no colour given")
        return default

    text = str(value).strip()
    match = HEX_RE.match(text)
    if not match:
        raise ColorError(f"{text!r} is not a hex colour (expected #RGB or #RRGGBB)")

    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits.lower()


def parse_hex_or(value: str, default: str) -> str:
    """Lenient parse: bad input falls back instead of raising.

    Used on form submissions, where rejecting the whole save because someone
    typed '#12345' would throw away every other edit on the page.
    """
    try:
        return parse_hex(value, default)
    except ColorError:
        return default


def to_rgb(value: str) -> tuple[int, int, int]:
    h = parse_hex(value).lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def relative_luminance(value: str) -> float:
    """WCAG relative luminance, 0 (black) to 1 (white)."""
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in to_rgb(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def readable_text_color(background: str) -> str:
    """Pick black or white text for a background, whichever reads better."""
    return "#111111" if relative_luminance(background) > 0.45 else "#f5f5f5"


def qr_contrast_warning(dark: str, light: str) -> str | None:
    """Return a warning if this colour pair will scan badly, else None."""
    ratio = contrast_ratio(dark, light)

    if relative_luminance(dark) > relative_luminance(light):
        # Modern phone cameras and many software decoders handle inverted
        # codes, but hardware POS imagers frequently do not - and a POS scan is
        # the whole point of putting the GTIN in the URL. Flag it, don't block.
        return (
            f"This code is inverted - the module colour ({dark}) is lighter "
            f"than its background ({light}). Phone cameras usually cope, but "
            f"many retail POS scanners do not read inverted codes, which "
            f"defeats the point of a scannable GTIN. Test on real hardware."
        )
    if ratio < QR_CONTRAST_MARGINAL:
        return (
            f"Contrast ratio is {ratio:.1f}:1. This code will likely fail to "
            f"scan, especially in print. Aim for {QR_CONTRAST_GOOD:.0f}:1 or better."
        )
    if ratio < QR_CONTRAST_GOOD:
        return (
            f"Contrast ratio is {ratio:.1f}:1. Readable on screen but risky in "
            f"print. Test a physical proof before committing to packaging."
        )
    return None
