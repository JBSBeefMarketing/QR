"""Application entry point.

Route layout matters here. The GS1 AI paths (/01/...) sit at the root because
that is what gets printed on packaging and it must stay short and stable.
Everything operational lives under /admin, which is never part of a public URL.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import admin, auth, config, db, pages, resolver
from .templating import templates

DATA_DIR = config.DATA_DIR
STATIC_DIR = config.PROJECT_ROOT / "static"

# Docs are off: they would sit outside the /admin auth and describe every
# endpoint to anyone who asked.
app = FastAPI(title="JBS Beef Digital Link", docs_url=None, redoc_url=None)

# Directories must exist before StaticFiles is mounted below, not at startup.
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "codes").mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
def startup() -> None:
    db.init_db()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Only the generated code images are served, NOT the whole data directory -
# that also holds catalog.sqlite3, which must never be downloadable.
app.mount(
    "/media/codes",
    StaticFiles(directory=str(DATA_DIR / "codes")),
    name="media",
)

# Everything under /admin requires the shared password. The resolver and the
# product pages below are intentionally public - they exist to be scanned.
app.include_router(
    admin.router, prefix="/admin", dependencies=[Depends(auth.require_admin)]
)
app.include_router(resolver.router)


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Liveness probe for the host, and the thing uptime monitoring should hit.

    Touches the database so a healthy response means more than "the process is
    running" - it means the disk is mounted and readable.
    """
    try:
        with db.cursor() as conn:
            conn.execute("SELECT 1 FROM products LIMIT 1").fetchone()
    except Exception as exc:  # surface the fault rather than reporting healthy
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "domain": config.DOMAIN, "provisional": config.IS_PROVISIONAL}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/admin/")


@app.get("/p/{gtin14}", response_class=HTMLResponse)
def product_page(request: Request, gtin14: str, tab: str = ""):
    """The consumer-facing page. This is the URL a QR ultimately lands on."""
    product = db.get_product(gtin14)
    page = db.get_page(gtin14)
    if not product or not page:
        return templates.TemplateResponse(
            request,
            "passport_missing.html",
            {"request": request, "gtin14": gtin14},
            status_code=404,
        )

    content = pages.ensure_shape(page["content"])
    tabs = pages.visible_tabs(content)
    active = tab if tab in tabs else (tabs[0] if tabs else "home")

    return templates.TemplateResponse(
        request,
        "passport.html",
        {
            "request": request,
            "gtin14": gtin14,
            "product": product,
            "content": content,
            "tabs": tabs,
            "active": active,
            "theme": pages.theme_vars(content),
            "is_draft": page["status"] != "published",
        },
    )
