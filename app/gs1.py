"""GS1 identifier and Digital Link URI handling.

Python has no binding to GS1's C syntax engine, so the small amount of
validation we need is implemented here rather than pulling a thin dependency.

References:
  URI Syntax     https://ref.gs1.org/standards/digital-link/uri-syntax/
  Resolver       https://ref.gs1.org/standards/resolver/
"""

from __future__ import annotations

import re

# Application Identifiers we support. Primary key first, then key qualifiers
# in the order the standard requires them to appear in the path.
AI_GTIN = "01"
AI_LOT = "10"
AI_SERIAL = "21"

KEY_QUALIFIER_ORDER = [AI_LOT, AI_SERIAL]

# linkTypes we expect to serve. The gs1: prefix is the compact IRI form used
# in ?linkType= query values.
KNOWN_LINK_TYPES = [
    "gs1:pip",  # product information page - our default
    "gs1:nutritionalInfo",
    "gs1:allergenInfo",
    "gs1:ingredientsInfo",
    "gs1:recipeInfo",
    "gs1:traceability",
    "gs1:sustainabilityInfo",
    "gs1:promotion",
    "gs1:brandHomepage",
]

DEFAULT_LINK_TYPE = "gs1:pip"

_DIGITS = re.compile(r"^\d+$")


class GS1Error(ValueError):
    """Raised when an identifier is syntactically invalid (-> HTTP 400)."""


def check_digit(payload: str) -> int:
    """Standard GS1 mod-10 check digit for the payload *without* its check digit.

    Weights alternate 3 and 1, applied right to left.
    """
    if not _DIGITS.match(payload):
        raise GS1Error("check digit input must be digits only")
    total = 0
    for i, ch in enumerate(reversed(payload)):
        weight = 3 if i % 2 == 0 else 1
        total += int(ch) * weight
    return (10 - (total % 10)) % 10


def is_valid_gtin(gtin: str) -> bool:
    if not gtin or not _DIGITS.match(gtin) or len(gtin) not in (8, 12, 13, 14):
        return False
    return check_digit(gtin[:-1]) == int(gtin[-1])


def normalise_gtin(gtin: str) -> str:
    """Return the canonical 14-digit form.

    Zero-padding to 14 digits became mandatory in URI Syntax 1.4.0, so a GTIN-12
    (UPC) and its GTIN-14 equivalent resolve to the same entry rather than
    silently becoming two different products.
    """
    if gtin is None:
        raise GS1Error("missing GTIN")
    gtin = str(gtin).strip()
    if not _DIGITS.match(gtin or ""):
        raise GS1Error(f"GTIN must be numeric: {gtin!r}")
    if len(gtin) not in (8, 12, 13, 14):
        raise GS1Error(f"GTIN must be 8, 12, 13 or 14 digits, got {len(gtin)}")
    if not is_valid_gtin(gtin):
        expected = check_digit(gtin[:-1])
        raise GS1Error(
            f"GTIN {gtin} fails the mod-10 check digit (expected {expected}, got {gtin[-1]})"
        )
    return gtin.rjust(14, "0")


def build_digital_link(
    domain: str,
    gtin: str,
    lot: str | None = None,
    serial: str | None = None,
    scheme: str = "https",
    uppercase: bool = False,
) -> str:
    """Build a canonical GS1 Digital Link URI.

    Canonical form requires HTTPS, a 14-digit GTIN, and key qualifiers in the
    order defined by the standard. We keep the scheme overridable only so the
    prototype can emit http:// for a LAN demo before a real domain exists.

    `uppercase` capitalises the scheme and host so the QR encoder can use
    alphanumeric mode, which produces a smaller symbol - see _uppercase_prefix
    for why only those two parts are touched.
    """
    gtin14 = normalise_gtin(gtin)
    path = f"/{AI_GTIN}/{gtin14}"
    if lot:
        path += f"/{AI_LOT}/{_escape_segment(lot)}"
        if serial:
            path += f"/{AI_SERIAL}/{_escape_segment(serial)}"
    elif serial:
        # Serial without lot is legal; the qualifier order still holds.
        path += f"/{AI_SERIAL}/{_escape_segment(serial)}"

    prefix = f"{scheme}://{domain.rstrip('/')}"
    if uppercase:
        prefix = _uppercase_prefix(prefix)
    return f"{prefix}{path}"


def _uppercase_prefix(prefix: str) -> str:
    """Capitalise the scheme and host only.

    QR codes have an alphanumeric encoding mode covering digits, capitals and
    a handful of symbols, which packs roughly 35% tighter than the byte mode
    lowercase forces. A GTIN-only link encoded this way drops from a 29x29
    symbol to 25x25 - larger modules at the same printed size, so it survives
    print variation and a phone camera in poor light far better.

    Only the scheme and host are touched, and that distinction matters. Scheme
    and host are case-insensitive per RFC 3986, so changing them cannot change
    where the URI points. The path is case-SENSITIVE: a batch code of 'abc123'
    is not the same identifier as 'ABC123', and uppercasing it would silently
    corrupt the data. So a link carrying a lowercase lot or serial simply
    forgoes the size saving, which is the right trade.
    """
    return prefix.upper()


def _escape_segment(value: str) -> str:
    from urllib.parse import quote

    return quote(str(value), safe="")


def normalise_link_type(value: str | None) -> str | None:
    """Accept the compact form (gs1:nutritionalInfo) or a bare name."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if value.startswith("https://gs1.org/voc/"):
        value = "gs1:" + value.rsplit("/", 1)[-1]
    elif ":" not in value:
        value = "gs1:" + value
    return value


def link_type_iri(compact: str) -> str:
    """Expand gs1:nutritionalInfo to its full IRI for linkset output."""
    if compact.startswith("gs1:"):
        return "https://gs1.org/voc/" + compact.split(":", 1)[1]
    return compact
