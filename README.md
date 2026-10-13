# JBS Beef — Digital Link prototype

Internal QR catalog, GS1 Digital Link resolver, and product page authoring and
hosting.

Built to demonstrate that JBS can host this capability itself, so that a code
printed on packaging depends only on a JBS domain and a JBS-served page rather
than on any subscription. See [MEMO.md](MEMO.md) for the stakeholder case.

**This is a prototype.** No authentication, no production hosting, no high
availability. Do not print anything it generates until the real domain exists.

## Running it

```
pip install -r requirements.txt
python -m app.ingest        # load the GDSN exports from your Desktop
run.bat                     # or: python -m uvicorn app.main:app --port 8000
```

Then open <http://localhost:8000/admin/>.

`--host 0.0.0.0` in `run.bat` is deliberate: it lets a phone on the same Wi-Fi
scan a generated code and load the real page.

## The domain

This is the only thing here that matters permanently. The domain in a printed
QR code can never be changed.

JBS owns **`jbs-qr.com`**, bought for this purpose. Codes print against the
bare domain, not a subdomain — a shorter URL fits a smaller QR symbol, which
means larger modules at the same printed size and a more forgiving scan.

Until the domain actually serves this app, codes are generated against this
machine's LAN address and the admin UI warns on every page. Once it is live,
uncomment the two lines in `run.bat`:

```
set JBS_DL_DOMAIN=jbs-qr.com
set JBS_DL_SCHEME=https
```

Do not set these early. Codes generated against a domain that isn't serving
yet look finished and resolve to nothing.

### Capitals

Codes are generated as `HTTPS://JBS-QR.COM/01/{GTIN}`. Capitals let the QR
encoder use alphanumeric mode, which drops the symbol from 29×29 to 25×25 —
larger modules at the same printed size, so it reads better off film and in
poor light. Scheme and host are case-insensitive, so it resolves identically.
Confirmed acceptable with GS1, October 2026.

Only the scheme and host are capitalised. Path segments — batch, lot, serial —
are case-*sensitive*, and uppercasing them would change the identifier. A link
carrying a lowercase lot keeps it exactly as given and simply forgoes the size
saving.

Set `JBS_DL_UPPERCASE=0` to turn this off.

See [DEPLOYMENT.md](DEPLOYMENT.md) for getting from here to live.

## Layout

```
app/gs1.py         GTIN validation, Digital Link URI construction
app/resolver.py    GS1-conformant resolution (the printed URL lands here)
app/pages.py       Product page content model, prefill, nutrient rounding
app/admin.py       Catalog, code generation, page authoring
app/ingest.py      GDSN/Syndigo spreadsheet ingest + data gap report
app/export.py      Everything out to JSON/CSV
app/config.py      The resolver domain
tests/conformance.py   Resolver standard checks
```

## URLs

| Path | What |
|---|---|
| `/01/{GTIN}` | The printed Digital Link URL. Redirects to the product page. |
| `/01/{GTIN}?linkType=gs1:all` | Linkset (RFC 9264) |
| `/.well-known/gs1resolver` | Resolver description document |
| `/p/{GTIN}` | The consumer product page |
| `/admin/` | Everything operational |
| `/admin/export.json` | Full data export |

## Verification

```
python -m tests.conformance http://127.0.0.1:8000
```

Checks the behaviours required by the GS1 Resolver standard v1.2.1 — 400 vs 404
distinction, no default fallback on an unavailable linkType, linkset format,
CORS, HEAD/OPTIONS, GTIN-12/14 equivalence.

These are locally implemented checks, **not** the official GS1 test suite at
<https://ref.gs1.org/test-suites/resolver/>, which needs a publicly reachable
host. Run that one too once the domain is live.

To confirm a generated code carries what you think it does:

```
pip install zxing-cpp pillow
python -c "import zxingcpp;from PIL import Image;print([r.text for r in zxingcpp.read_barcodes(Image.open('data/codes/<file>.png'))])"
```

## Colour

Both the product page and the QR codes take any hex colour.

- **Page** — background and accent, set per product in the editor. Text, rules
  and muted tones are derived from the background so a dark theme stays
  readable without extra fiddling.
- **QR code** — module and background colour, set when the code is created.

Any pair is accepted. Contrast is measured and shown on the code's page, with a
warning banner when the pair is likely to scan badly — low contrast, or an
inverted code (light modules on dark). Both are advisory; nothing is blocked.
The inverted case matters more than its contrast ratio suggests: phone cameras
usually cope, but many retail POS imagers do not, which defeats the purpose of
carrying the GTIN in the URL.

## Admin password

`/admin/*` is protected by a single shared username and password. The public
side — `/01/{GTIN}` and `/p/{GTIN}` — is never protected; it exists to be
scanned.

| Situation | Behaviour |
|---|---|
| Local, no password set | Admin open, no prompt. Convenient on a laptop. |
| Real domain, no password set | **Admin locked (503).** Fails closed so a live site can never be unprotected. |
| Password set | Browser prompts. Username `jbs`, password from `JBS_DL_ADMIN_PASSWORD`. |

```
set JBS_DL_ADMIN_USER=jbs
set JBS_DL_ADMIN_PASSWORD=<something long>
```

## Known limitations

- Product data comes from spreadsheet exports, not live Syndigo or Qlik.
- The current exports have **no nutrition, allergen or serving data** and
  contain only CASE-level foodservice items. Nutrition pages must be authored
  by hand. See MEMO.md.
- GDSN gives an image *filename*, not a URL. Where those assets are served from
  is unresolved, so image URLs are entered manually.
- Single shared admin login, no per-user accounts or audit trail.
- SQLite on a single instance. Correct for this traffic, but the app cannot be
  scaled to more than one copy without changing the database.
- Backups are manual: download `/admin/export.json`.
- On the JBS network the iboss proxy intercepts loopback traffic; use
  `curl --noproxy '*'` when testing from a shell.

## Standards

- GS1 Digital Link URI Syntax — <https://ref.gs1.org/standards/digital-link/uri-syntax/>
- GS1-Conformant Resolver — <https://ref.gs1.org/standards/resolver/>
- GS1 US Sunrise 2027 — <https://www.gs1us.org/industries-and-insights/by-topic/sunrise-2027>
