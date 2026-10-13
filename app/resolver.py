"""GS1-conformant Digital Link resolution.

Implements the behaviour required by the Resolver standard v1.2.1:
https://ref.gs1.org/standards/resolver/

  - GET / HEAD / OPTIONS over the AI path form, with CORS
  - 400 for a malformed URI, 404 for valid-but-unknown (they are different
    answers and conflating them hides data problems)
  - exactly one default link per entity at every level of granularity
  - linkset responses in RFC 9264 JSON
  - 404 when a requested linkType is unavailable, rather than silently falling
    back to the default (this changed in Resolver 1.2 - the older behaviour
    would send someone asking for allergen info to a marketing page)
  - a /.well-known/gs1resolver descriptor

This module is deliberately thin. Resolution is a redirect table; the effort in
this project is in authoring and hosting the pages it points at.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from . import db
from .gs1 import (
    DEFAULT_LINK_TYPE,
    GS1Error,
    KNOWN_LINK_TYPES,
    link_type_iri,
    normalise_gtin,
    normalise_link_type,
)

router = APIRouter()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "Accept, Content-Type",
}


def _error(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        {"status": status, "title": title, "detail": detail},
        status_code=status,
        headers=CORS_HEADERS,
    )


def _linkset(gtin14: str, links, request: Request) -> JSONResponse:
    """RFC 9264 linkset. The anchor is the canonical URI for the entity."""
    anchor = str(request.url).split("?")[0]
    context: dict[str, list[dict]] = {}
    for row in links:
        iri = link_type_iri(row["link_type"])
        context.setdefault(iri, []).append(
            {
                "href": row["href"],
                "title": row["title"] or "",
                "hreflang": [row["lang"] or "en"],
            }
        )
    return JSONResponse(
        {"linkset": [{"anchor": anchor, **context}]},
        media_type="application/linkset+json",
        headers=CORS_HEADERS,
    )


def _resolve(
    request: Request,
    gtin: str,
    lot: str | None = None,
    serial: str | None = None,
) -> Response:
    try:
        gtin14 = normalise_gtin(gtin)
    except GS1Error as exc:
        return _error(400, "Malformed GS1 Digital Link URI", str(exc))

    links = db.get_links(gtin14, lot, serial)
    if not links:
        return _error(
            404,
            "Unknown identifier",
            f"No links are registered for GTIN {gtin14}.",
        )

    requested = normalise_link_type(request.query_params.get("linkType"))

    if requested in ("gs1:all", "gs1:linkset"):
        return _linkset(gtin14, links, request)

    if "application/linkset+json" in request.headers.get("accept", ""):
        return _linkset(gtin14, links, request)

    if requested:
        matches = [r for r in links if r["link_type"] == requested]
        if not matches:
            # Resolver 1.2: do not fall back to the default here.
            available = sorted({r["link_type"] for r in links})
            return _error(
                404,
                "Requested linkType unavailable",
                f"GTIN {gtin14} has no {requested} link. Available: {', '.join(available)}",
            )
        target = matches[0]
    else:
        defaults = [r for r in links if r["is_default"]]
        target = defaults[0] if defaults else links[0]

    return RedirectResponse(
        target["href"],
        status_code=307,
        headers={**CORS_HEADERS, "Link": f'<{str(request.url)}>; rel="owl:sameAs"'},
    )


@router.api_route("/01/{gtin}", methods=["GET", "HEAD"])
def resolve_gtin(request: Request, gtin: str):
    return _resolve(request, gtin)


@router.api_route("/01/{gtin}/10/{lot}", methods=["GET", "HEAD"])
def resolve_lot(request: Request, gtin: str, lot: str):
    return _resolve(request, gtin, lot=lot)


@router.api_route("/01/{gtin}/21/{serial}", methods=["GET", "HEAD"])
def resolve_serial(request: Request, gtin: str, serial: str):
    return _resolve(request, gtin, serial=serial)


@router.api_route("/01/{gtin}/10/{lot}/21/{serial}", methods=["GET", "HEAD"])
def resolve_lot_serial(request: Request, gtin: str, lot: str, serial: str):
    return _resolve(request, gtin, lot=lot, serial=serial)


@router.options("/01/{path:path}")
def resolve_options(path: str):
    return Response(status_code=204, headers=CORS_HEADERS)


@router.get("/.well-known/gs1resolver")
def resolver_description(request: Request):
    """Declares what this resolver supports, per the Resolver standard."""
    return JSONResponse(
        {
            "name": "JBS Beef Digital Link Resolver",
            "resolverRoot": f"{request.url.scheme}://{request.url.netloc}",
            "supportedPrimaryKeys": ["01"],
            "supportedLinkType": KNOWN_LINK_TYPES,
            "defaultLinkType": DEFAULT_LINK_TYPE,
            "supportedContexts": ["us"],
            "supportedMediaTypes": ["text/html", "application/linkset+json"],
            "contact": {
                "name": "JBS Beef Marketing",
                "email": "Preston.Evans@jbssa.com",
            },
            "statusCodes": {
                "malformedRequest": 400,
                "unknownIdentifier": 404,
                "unavailableLinkType": 404,
                "resolved": 307,
            },
        },
        headers=CORS_HEADERS,
    )
