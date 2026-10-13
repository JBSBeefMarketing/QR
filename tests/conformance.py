"""Resolver conformance checks.

These assert the behaviours the GS1 Resolver standard v1.2.1 requires, as read
from https://ref.gs1.org/standards/resolver/.

This is NOT the official GS1 test suite. That suite is hosted at
https://ref.gs1.org/test-suites/resolver/ and has to be pointed at a publicly
reachable resolver, which this prototype is not yet. Treat a pass here as
"nothing obviously wrong", not as certification.

    python -m tests.conformance [base_url]
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
GTIN = "90076338468464"          # must be published in the DB before running
BAD_CHECK_DIGIT = "90076338468465"
MALFORMED = "12345"
UNKNOWN = "00000000000000"

results: list[tuple[bool, str, str]] = []


def request(path: str, method: str = "GET", accept: str | None = None):
    """Return (status, headers, body) without following redirects."""
    url = BASE + path
    req = urllib.request.Request(url, method=method)
    if accept:
        req.add_header("Accept", accept)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    # proxy={} matters on the JBS network: the corporate proxy intercepts
    # loopback traffic and returns its own 403 block page.
    opener = urllib.request.build_opener(
        NoRedirect, urllib.request.ProxyHandler({})
    )
    try:
        with opener.open(req, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf8", "replace")


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((condition, name, detail))


def run() -> None:
    # 1. Resolution of a known identifier
    status, headers, _ = request(f"/01/{GTIN}")
    check(
        "Known GTIN resolves with a redirect",
        status in (301, 302, 307, 308),
        f"got {status}",
    )

    # 2. Malformed URI must be 400, not 404 - they are different answers
    status, _, _ = request(f"/01/{MALFORMED}")
    check("Malformed GTIN returns 400", status == 400, f"got {status}")

    status, _, _ = request(f"/01/{BAD_CHECK_DIGIT}")
    check("Failed check digit returns 400", status == 400, f"got {status}")

    # 3. Valid but unknown must be 404
    status, _, _ = request(f"/01/{UNKNOWN}")
    check("Unknown GTIN returns 404", status == 404, f"got {status}")

    # 4. Resolver 1.2: unavailable linkType is 404, NOT a default fallback
    status, _, _ = request(f"/01/{GTIN}?linkType=gs1:recipeInfo")
    check(
        "Unavailable linkType returns 404 (no default fallback)",
        status == 404,
        f"got {status}",
    )

    # 5. Linkset in RFC 9264 form, both by query and by Accept header
    status, headers, body = request(f"/01/{GTIN}?linkType=gs1:all")
    ok = status == 200 and "linkset" in headers.get("content-type", "").lower()
    check("linkType=gs1:all returns application/linkset+json", ok,
          f"{status} {headers.get('content-type')}")
    try:
        payload = json.loads(body)
        anchored = "linkset" in payload and "anchor" in payload["linkset"][0]
    except (ValueError, KeyError, IndexError):
        anchored = False
    check("Linkset body is RFC 9264 shaped with an anchor", anchored)

    status, headers, _ = request(f"/01/{GTIN}", accept="application/linkset+json")
    check(
        "Accept: application/linkset+json returns a linkset",
        status == 200 and "linkset" in headers.get("content-type", "").lower(),
        f"{status} {headers.get('content-type')}",
    )

    # 6. HEAD and OPTIONS
    status, _, _ = request(f"/01/{GTIN}", method="HEAD")
    check("HEAD is supported", status in (200, 301, 302, 307, 308), f"got {status}")

    status, headers, _ = request(f"/01/{GTIN}", method="OPTIONS")
    check("OPTIONS is supported", status in (200, 204), f"got {status}")

    # 7. CORS
    _, headers, _ = request(f"/01/{UNKNOWN}")
    check(
        "CORS header present",
        headers.get("access-control-allow-origin") == "*",
        str(headers.get("access-control-allow-origin")),
    )

    # 8. Resolver description document
    status, _, body = request("/.well-known/gs1resolver")
    ok = False
    if status == 200:
        try:
            doc = json.loads(body)
            ok = "01" in doc.get("supportedPrimaryKeys", []) and bool(
                doc.get("supportedLinkType")
            )
        except ValueError:
            ok = False
    check("/.well-known/gs1resolver describes the resolver", ok, f"got {status}")

    # 9. GTIN-12 and GTIN-14 must land on the same entity
    status_14, _, _ = request(f"/01/{GTIN}")
    status_short, _, _ = request(f"/01/{GTIN.lstrip('0')}")
    check(
        "Short and 14-digit GTIN forms resolve identically",
        status_14 == status_short,
        f"{status_14} vs {status_short}",
    )

    # 10. Key qualifier path falls back to the GTIN-level default
    status, _, _ = request(f"/01/{GTIN}/10/LOT123")
    check(
        "Lot-level request falls back to the GTIN default link",
        status in (301, 302, 307, 308),
        f"got {status}",
    )


def report() -> int:
    run()
    passed = sum(1 for ok, _, _ in results if ok)
    total = len(results)
    print(f"GS1 Resolver conformance checks against {BASE}")
    print("=" * 68)
    for ok, name, detail in results:
        mark = "PASS" if ok else "FAIL"
        suffix = f"   [{detail}]" if detail and not ok else ""
        print(f"  {mark}  {name}{suffix}")
    print("=" * 68)
    print(f"{passed}/{total} checks passed")
    print(
        "\nNote: these are locally implemented checks of the documented "
        "requirements,\nnot the official GS1 test suite, which requires a "
        "publicly reachable host."
    )
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(report())
