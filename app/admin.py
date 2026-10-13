"""Admin: product list, page authoring, QR catalog, code generation."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from . import colors, config, db, export, pages, qrcodes
from .gs1 import DEFAULT_LINK_TYPE, GS1Error, KNOWN_LINK_TYPES, build_digital_link, normalise_gtin
from .templating import templates

router = APIRouter()

CATEGORIES = {
    "I": "Brand & corporate",
    "II": "Retail-ready packaging (existing)",
    "III": "Retail-ready packaging (missing)",
}

BLANK_ROWS = 3  # empty nutrition rows offered on each edit


def _ctx(request: Request, **extra) -> dict:
    return {
        "request": request,
        "domain": config.DOMAIN,
        "scheme": config.SCHEME,
        "provisional": config.IS_PROVISIONAL,
        "target_domain": config.TARGET_DOMAIN,
        "categories": CATEGORIES,
        **extra,
    }


# --- dashboard --------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with db.cursor() as conn:
        counts = {
            "products": conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"],
            "pages": conn.execute("SELECT COUNT(*) c FROM pages").fetchone()["c"],
            "published": conn.execute(
                "SELECT COUNT(*) c FROM pages WHERE status='published'"
            ).fetchone()["c"],
            "codes": conn.execute("SELECT COUNT(*) c FROM catalog").fetchone()["c"],
            "links": conn.execute("SELECT COUNT(*) c FROM links").fetchone()["c"],
        }
        by_cat = conn.execute(
            "SELECT category, COUNT(*) c FROM catalog GROUP BY category"
        ).fetchall()
    return templates.TemplateResponse(
        request,
        "dashboard.html", _ctx(request, counts=counts, by_cat=by_cat)
    )


# --- products ---------------------------------------------------------------

@router.get("/products", response_class=HTMLResponse)
def products(request: Request, q: str = ""):
    rows = db.list_products(q)
    return templates.TemplateResponse(
        request,
        "products.html", _ctx(request, products=rows, q=q)
    )


# --- page authoring ---------------------------------------------------------

@router.get("/page/{gtin14}", response_class=HTMLResponse)
def edit_page(request: Request, gtin14: str):
    product = db.get_product(gtin14)
    if not product:
        return HTMLResponse(f"Unknown GTIN {gtin14}", status_code=404)

    page = db.get_page(gtin14)
    if page:
        content, status = pages.ensure_shape(page["content"]), page["status"]
    else:
        content, status = pages.prefill_from_product(product), "draft"

    rows = list(content["nutrition"].get("rows") or [])
    rows += [
        {"label": "", "per_serving": "", "per_reference": "", "unit": "g",
         "indent": False, "bold": False}
        for _ in range(BLANK_ROWS)
    ]
    content["nutrition"]["rows"] = rows

    link_rows = list(content["home"].get("links") or [])
    link_rows += [{"label": "", "url": ""} for _ in range(2)]
    content["home"]["links"] = link_rows

    return templates.TemplateResponse(
        request,
        "editor.html",
        _ctx(request, product=product, content=content, status=status, gtin14=gtin14),
    )


@router.post("/page/{gtin14}")
async def save_page(request: Request, gtin14: str):
    product = db.get_product(gtin14)
    if not product:
        return HTMLResponse(f"Unknown GTIN {gtin14}", status_code=404)

    form = await request.form()
    content = pages.blank_content()

    # Any hex pair is accepted. Unparseable input falls back to the default
    # rather than losing the rest of the author's edits to a validation error.
    content["theme"] = {
        "background": colors.parse_hex_or(
            form.get("theme_background"), pages.DEFAULT_THEME["background"]
        ),
        "accent": colors.parse_hex_or(
            form.get("theme_accent"), pages.DEFAULT_THEME["accent"]
        ),
    }

    content["header"] = {
        "name": form.get("name", "").strip(),
        "brand": form.get("brand", "").strip(),
        "net_weight": form.get("net_weight", "").strip(),
        "image_url": form.get("image_url", "").strip(),
        "show_gtin": form.get("show_gtin") == "on",
    }

    nutrition_rows = []
    index = 0
    while f"row_label_{index}" in form:
        label = form.get(f"row_label_{index}", "").strip()
        per_serving = form.get(f"row_serving_{index}", "").strip()
        per_reference = form.get(f"row_reference_{index}", "").strip()
        if label and (per_serving or per_reference):
            nutrition_rows.append(
                {
                    "label": label,
                    "per_serving": per_serving,
                    "per_reference": per_reference,
                    "unit": form.get(f"row_unit_{index}", "").strip(),
                    "indent": form.get(f"row_indent_{index}") == "on",
                    "bold": form.get(f"row_bold_{index}") == "on",
                }
            )
        index += 1

    content["nutrition"] = {
        "serving_size": form.get("serving_size", "").strip(),
        "servings_per_container": form.get("servings_per_container", "").strip(),
        "per_serving_label": form.get("per_serving_label", "Per serving").strip(),
        "per_reference_label": form.get("per_reference_label", "Per 100g").strip(),
        "rows": nutrition_rows,
        "footnote": form.get("footnote", "").strip(),
    }

    content["ingredients"] = {
        "statement": form.get("statement", "").strip(),
        "note": form.get("ingredients_note", "").strip(),
    }

    def csv_list(field: str) -> list[str]:
        return [v.strip() for v in form.get(field, "").split(",") if v.strip()]

    content["allergens"] = {
        "contains": csv_list("contains"),
        "may_contain": csv_list("may_contain"),
        "free_from": csv_list("free_from"),
    }

    home_links = []
    index = 0
    while f"link_label_{index}" in form:
        label = form.get(f"link_label_{index}", "").strip()
        url = form.get(f"link_url_{index}", "").strip()
        if label and url:
            home_links.append({"label": label, "url": url})
        index += 1

    content["home"] = {
        "marketing": form.get("marketing", "").strip(),
        "storage": form.get("storage", "").strip(),
        "prep": form.get("prep", "").strip(),
        "origin": form.get("origin", "").strip(),
        "links": home_links,
    }

    status = "published" if form.get("action") == "publish" else "draft"
    db.save_page(gtin14, content, status)

    # A published page becomes the default resolution target for its GTIN.
    if status == "published" and not db.get_links(gtin14):
        db.add_link(
            gtin14,
            href=f"/p/{gtin14}",
            link_type=DEFAULT_LINK_TYPE,
            title=content["header"]["name"] or gtin14,
            is_default=True,
        )

    return RedirectResponse(f"/admin/page/{gtin14}?saved=1", status_code=303)


# --- catalog ----------------------------------------------------------------

@router.get("/catalog", response_class=HTMLResponse)
def catalog(request: Request, category: str = "", q: str = ""):
    entries = db.list_catalog(category, q)
    return templates.TemplateResponse(
        request,
        "catalog.html", _ctx(request, entries=entries, category=category, q=q)
    )


@router.get("/catalog/new", response_class=HTMLResponse)
def new_entry(request: Request, gtin: str = "", error: str = ""):
    return templates.TemplateResponse(
        request,
        "catalog_new.html",
        _ctx(request, gtin=gtin, error=error, link_types=KNOWN_LINK_TYPES),
    )


@router.post("/catalog/new")
def create_entry(
    request: Request,
    category: str = Form(...),
    code_kind: str = Form(...),
    label: str = Form(...),
    gtin: str = Form(""),
    target_url: str = Form(""),
    brand: str = Form(""),
    owner: str = Form(""),
    owner_contact: str = Form(""),
    world_location: str = Form(""),
    is_dynamic: str = Form(""),
    needs_pdp: str = Form(""),
    notes: str = Form(""),
    qr_dark: str = Form(qrcodes.DEFAULT_DARK),
    qr_light: str = Form(qrcodes.DEFAULT_LIGHT),
):
    gtin14 = None
    if code_kind == "digital_link":
        try:
            gtin14 = normalise_gtin(gtin)
        except GS1Error as exc:
            return templates.TemplateResponse(
                request,
                "catalog_new.html",
                _ctx(request, gtin=gtin, error=str(exc), link_types=KNOWN_LINK_TYPES),
                status_code=400,
            )
        url = build_digital_link(
            config.DOMAIN,
            gtin14,
            scheme=config.SCHEME,
            uppercase=config.UPPERCASE_URI,
        )
    else:
        url = target_url.strip()
        if not url:
            return templates.TemplateResponse(
                request,
                "catalog_new.html",
                _ctx(request, gtin=gtin, error="A target URL is required for a plain code.",
                     link_types=KNOWN_LINK_TYPES),
                status_code=400,
            )

    # Any colour pair is allowed. Poor contrast is surfaced as a warning on the
    # code's page rather than blocked here - see colors.qr_contrast_warning.
    dark = colors.parse_hex_or(qr_dark, qrcodes.DEFAULT_DARK)
    light = colors.parse_hex_or(qr_light, qrcodes.DEFAULT_LIGHT)

    png, svg = qrcodes.generate(url, f"{gtin14 or label}-{category}", dark, light)

    entry_id = db.add_catalog_entry(
        {
            "category": category,
            "code_kind": code_kind,
            "gtin14": gtin14,
            "brand": brand.strip() or None,
            "label": label.strip(),
            "target_url": url,
            "world_location": world_location.strip() or None,
            "is_dynamic": 1 if is_dynamic == "on" else 0,
            "owner": owner.strip() or None,
            "owner_contact": owner_contact.strip() or None,
            "needs_pdp": 1 if needs_pdp == "on" else 0,
            "status": "logged",
            "notes": notes.strip() or None,
            "qr_png": png,
            "qr_svg": svg,
            "qr_dark": dark,
            "qr_light": light,
        }
    )
    return RedirectResponse(f"/admin/catalog/{entry_id}", status_code=303)


@router.get("/catalog/{entry_id}", response_class=HTMLResponse)
def view_entry(request: Request, entry_id: int):
    entry = db.get_catalog_entry(entry_id)
    if not entry:
        return HTMLResponse("Not found", status_code=404)
    warning = colors.qr_contrast_warning(entry["qr_dark"], entry["qr_light"])
    ratio = colors.contrast_ratio(entry["qr_dark"], entry["qr_light"])
    return templates.TemplateResponse(
        request,
        "catalog_entry.html",
        _ctx(request, entry=entry, contrast_warning=warning, contrast_ratio=ratio),
    )


# --- export -----------------------------------------------------------------

@router.get("/export.json")
def export_json():
    return Response(
        export.to_json(),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="jbs-digital-link.json"'},
    )


@router.get("/export/{table}.csv")
def export_csv(table: str):
    try:
        body = export.to_csv(table)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=404)
    return Response(
        body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}.csv"'},
    )
