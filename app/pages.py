"""Consumer product page: content model, prefill, and formatting.

Pages are authored here and served from here. Nothing external hosts them,
which is the whole point: a printed QR outlives any vendor relationship, so the
page behind it has to live somewhere JBS controls.

Content is a JSON document rather than a wide table because the section list
will change as the format settles, and a schema migration per tweak would slow
that down. The shape is documented in blank_content().
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

# Rounding precision per unit. The reference platform renders raw floats
# ("1198.21428571429kj", "9.82142857142857g") straight onto a consumer page;
# these are the precisions a nutrition panel actually uses.
UNIT_PRECISION = {
    "kj": 0,
    "kcal": 0,
    "cal": 0,
    "mg": 0,
    "iu": 0,
    "g": 1,
    "mcg": 1,
    "µg": 1,
    "ml": 1,
    "%": 0,
}

TABS = ["nutrition", "ingredients", "allergens", "home"]


DEFAULT_THEME = {
    "background": "#ffffff",
    "accent": "#9c2a2a",
}


def blank_content() -> dict:
    return {
        "theme": dict(DEFAULT_THEME),
        "header": {
            "name": "",
            "brand": "",
            "net_weight": "",
            "image_url": "",
            "show_gtin": True,
        },
        "nutrition": {
            "serving_size": "",
            "servings_per_container": "",
            "per_serving_label": "Per serving",
            "per_reference_label": "Per 100g",
            "rows": [],           # {label, per_serving, per_reference, unit, indent, bold}
            "footnote": "",
        },
        "ingredients": {
            "statement": "",
            "note": "",
        },
        "allergens": {
            "contains": [],
            "may_contain": [],
            "free_from": [],
        },
        "home": {
            "marketing": "",
            "storage": "",
            "prep": "",
            "origin": "",
            "links": [],          # {label, url}
        },
    }


def default_nutrition_rows() -> list[dict]:
    """The standard panel skeleton, so an author fills values not structure."""
    spec = [
        ("Energy", "kcal", False, True),
        ("Total Fat", "g", False, True),
        ("Saturated Fat", "g", True, False),
        ("Trans Fat", "g", True, False),
        ("Cholesterol", "mg", False, True),
        ("Sodium", "mg", False, True),
        ("Total Carbohydrate", "g", False, True),
        ("Dietary Fiber", "g", True, False),
        ("Total Sugars", "g", True, False),
        ("Protein", "g", False, True),
    ]
    return [
        {
            "label": label,
            "per_serving": "",
            "per_reference": "",
            "unit": unit,
            "indent": indent,
            "bold": bold,
        }
        for label, unit, indent, bold in spec
    ]


def prefill_from_product(product) -> dict:
    """Seed a page from ingested GDSN data.

    Only fields the export actually carries are filled. Nutrition, allergens
    and prep are empty in the current exports (0/162), so those arrive blank
    and must be authored - which is why the editor exists.
    """
    content = blank_content()
    get = product.__getitem__ if hasattr(product, "keys") else product.get

    def field(name):
        try:
            return get(name) or ""
        except (KeyError, IndexError):
            return ""

    name = field("short_description") or field("trade_item_desc") or field("functional_name")
    content["header"].update(
        {
            "name": name,
            "brand": field("brand"),
            "net_weight": _join_measure(field("net_weight"), field("net_weight_uom")),
            "image_url": _image_url(field("image_ref")),
        }
    )
    content["ingredients"]["statement"] = field("ingredients")
    content["nutrition"]["rows"] = default_nutrition_rows()
    content["home"].update(
        {
            "marketing": field("marketing_message"),
            "storage": field("storage"),
            "prep": field("prep_serving"),
            "origin": field("country_of_origin"),
        }
    )
    return content


def _join_measure(value: str, uom: str) -> str:
    value, uom = (value or "").strip(), (uom or "").strip()
    if not value:
        return ""
    return f"{format_number(value)} {uom}".strip()


def _image_url(image_ref: str) -> str:
    """GDSN carries a filename, not a URL.

    Where these assets are served from (Bynder, the I: drive, somewhere else)
    is an open question, so record the filename and let the author paste a real
    URL. Guessing a base URL here would bake in a wrong assumption.
    """
    return ""


def format_number(value) -> str:
    """Trim float noise without lying about precision."""
    if value is None or value == "":
        return ""
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return str(value)
    d = d.normalize()
    if d == d.to_integral_value():
        return str(d.quantize(Decimal(1)))
    return format(d, "f").rstrip("0").rstrip(".")


def format_nutrient(value, unit: str) -> str:
    """Round a nutrient to the precision its unit is actually reported in."""
    if value is None or str(value).strip() == "":
        return ""
    unit_key = (unit or "").strip().lower()
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return str(value)
    places = UNIT_PRECISION.get(unit_key, 1)
    quantum = Decimal(1) if places == 0 else Decimal(1).scaleb(-places)
    rounded = d.quantize(quantum)
    text = format(rounded, "f")
    if places:
        text = text.rstrip("0").rstrip(".")
    return f"{text}{unit}" if unit else text


def has_content(section: dict | list) -> bool:
    """Whether a tab has anything worth showing."""
    if isinstance(section, list):
        return bool(section)
    for value in (section or {}).values():
        if isinstance(value, list):
            if any(has_content(v) if isinstance(v, dict) else bool(v) for v in value):
                return True
        elif isinstance(value, str) and value.strip():
            return True
    return False


def ensure_shape(content: dict) -> dict:
    """Fill in sections a stored page predates.

    Content is stored as JSON, so adding a section to the model does not
    migrate existing rows. Merging against blank_content() on read means an
    older page keeps working instead of failing on a missing key.
    """
    base = blank_content()
    merged = dict(base)
    for key, default in base.items():
        value = (content or {}).get(key)
        if isinstance(default, dict) and isinstance(value, dict):
            merged[key] = {**default, **value}
        elif value is not None:
            merged[key] = value
    return merged


def theme_vars(content: dict) -> dict:
    """Resolve the page theme into CSS values.

    Text and rule colours are derived rather than authored: someone picking a
    dark background should not also have to remember to change the text, and a
    page that ends up grey-on-grey is worse than one with fewer knobs.
    """
    from .colors import parse_hex, readable_text_color, relative_luminance

    theme = {**DEFAULT_THEME, **(content.get("theme") or {})}
    background = parse_hex(theme.get("background"), DEFAULT_THEME["background"])
    accent = parse_hex(theme.get("accent"), DEFAULT_THEME["accent"])
    text = readable_text_color(background)
    is_dark = relative_luminance(background) <= 0.45

    return {
        "background": background,
        "accent": accent,
        "text": text,
        # Hairlines and secondary text are the same hue as the text, just
        # faded, so they stay legible on any background.
        "line": "rgba(255,255,255,.18)" if is_dark else "rgba(0,0,0,.10)",
        "muted": "rgba(245,245,245,.70)" if is_dark else "rgba(0,0,0,.55)",
        "panel": "rgba(255,255,255,.06)" if is_dark else "rgba(0,0,0,.03)",
    }


def visible_tabs(content: dict) -> list[str]:
    """Hide empty tabs rather than showing a consumer a blank panel."""
    tabs = []
    for tab in TABS:
        section = content.get(tab, {})
        if tab == "nutrition":
            rows = section.get("rows") or []
            if any(r.get("per_serving") or r.get("per_reference") for r in rows):
                tabs.append(tab)
        elif has_content(section):
            tabs.append(tab)
    return tabs
