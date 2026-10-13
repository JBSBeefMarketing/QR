# Hosting JBS Beef QR codes internally

**To:** Stephanie Hamilton
**From:** Preston Evans, Marketing Project Manager, JBS Beef
**Re:** Recommendation to build and host our QR / product page platform in-house
**Date:** September 2026

---

## The recommendation

Build and host it internally. A working prototype exists and is described at the
end of this memo.

The case is **not** cost savings. Infrastructure for an internal build costs
roughly what a subscription costs. The case is that a QR code printed on
packaging is a multi-year commitment, and everything behind it has to last at
least as long.

---

## Why internal

**A printed code lasts as long as the packaging, not as long as a contract.**

When we put a QR on a package, we are committing to keep that code working for
the entire life of that artwork — through reruns, through inventory in the
channel, through product sitting in a customer's freezer. If the destination
behind that code depends on a subscription, then the code's real lifespan is the
subscription's lifespan. When the subscription ends, the code is dead and the
only remedy is a reprint.

We just paid that bill with the Swift codes and Element. The lesson was not
"pick a better vendor." It was that anything printed onto packaging must depend
only on assets we own outright.

**Internal hosting reduces the permanent dependencies to two, and we own both:**

1. A JBS-registered domain — **`jbs-qr.com`**, now purchased by IT
2. A page served from JBS infrastructure

Everything else becomes replaceable without touching a single printed package.

**A second, quieter reason: the data.** The content on these pages is product
data we already own and already maintain for Syndigo. Authoring it somewhere
external creates a second copy that drifts out of sync with the first. Keeping
it inside means one place to correct a net weight, not two.

**A third: the codes are GS1 Digital Link, which means the URL carries the
GTIN** in a standard path (`/01/{GTIN}`). That format is defined by public
standard, not by any tool we happen to use, so the printed code stays valid no
matter what we build behind it. It also means the same code a shopper scans can
be read by a retail POS scanner — the direction GS1 US is pushing with
Sunrise 2027.

*One caution so we are not overselling this internally:* Sunrise 2027 is an
industry milestone, not a mandate. There is no law behind it, no penalty, and
the UPC is not going away. It is a good reason to move, not a deadline we are
forced to meet.

---

## What it will take

**Already built (prototype, on my machine):** GTIN validation, GS1-conformant
resolution, the QR catalog, code generation, the page authoring tool, and the
consumer page. It passes 14 of 14 locally implemented conformance checks against
the published GS1 Resolver standard.

**What separates the prototype from something we can print against:**

| Work | Notes |
|---|---|
| ~~Secure a domain~~ | **Done.** IT purchased `jbs-qr.com`. Still to confirm: JBS is the WHOIS registrant and controls the DNS zone. |
| Production hosting | Azure App Service or equivalent, managed database, TLS, backups. |
| Authentication | SSO for the authoring tool. Not needed for public pages. |
| IT architecture review | This is internet-facing and writes to a JBS-hosted database. Expect a real review, not a checkbox. |
| Product data integration | Prototype reads spreadsheet exports. Live Syndigo or Qlik connection is a later phase. |
| Content authoring | See the data gap below — this is the real workload. |
| A named long-term owner | The part that usually goes unfunded, and the part that determines whether this still works in 2031. |

**Honest estimate:** weeks of engineering, not days. The resolver itself is
small — it is a redirect table. The effort is in the authoring tool, the data
integration, and running a consumer-facing service to a standard where it is
still up years from now.

### The data gap we should know about now

Ingesting our current GDSN export (162 items) found:

- **Nutrition data: 0 of 162 items.**
- **Allergen data: 0 of 162 items.**
- **Preparation/serving info: 0 of 162 items.**
- Every item is **CASE-level foodservice** (1855, Swift Black Angus, Elite
  Prime). No retail-ready consumer units at all.

Available today: brand, description, net weight, ingredient statement, storage,
marketing copy, country of origin, and an image *filename* (not a URL — we still
need to establish where those assets are served from).

Two implications, and neither is a reason not to proceed:

1. **The consumer nutrition page cannot be auto-generated.** Someone has to
   author that content. The tool is built around that fact rather than pretending
   otherwise.
2. **Retail-ready consumer GTINs need a different data source than this export.**
   Worth confirming with Brogan whether a GTIN↔SAP mapping exists, since that
   also determines whether the catalog can be bootstrapped or has to be built by
   hand.

*Also worth flagging as a data quality issue:* all 162 items are marked "Item is
Sold to the Consumer = Y" while also being CASE-level. Those two things cannot
both be right. That is the kind of thing my Syndigo verification step is
supposed to catch, and it suggests the field is not being maintained.

---

## Expected cost

**Infrastructure — estimated $100–200/month.** Azure App Service, a managed
database, domain and certificate. This range needs IT to confirm it; JBS's
Azure agreement and internal chargeback rates decide the real number, not list
pricing.

**People — the larger and less visible cost.** Initial build, then ongoing
ownership. The recurring cost that matters is not the server; it is having
someone responsible for this in three years.

**Content — the largest cost, and it is unavoidable either way.** Given the gaps
above, most of the effort in year one is authoring product content that does not
currently exist anywhere. We would pay this cost with any platform, internal or
external.

### Being straight about the comparison

Subscription platforms in this space run roughly $80/month at our volume, and
around $3,000/year at enterprise scale. **Internal infrastructure alone is
comparable.** We should not present this as a savings initiative — that argument
will not survive a finance review, and it would be the wrong argument anyway.

The right framing is risk. The relevant number is not the monthly fee; it is the
cost of reprinting packaging across our SKU range if the thing behind our codes
goes away. We have a recent number for that, and it is not small.

---

## What I'm asking for

1. ~~A domain.~~ **Done** — IT purchased `jbs-qr.com`. What remains is
   confirming JBS is the registrant of record and controls the DNS zone, since
   that is the part that makes the printed codes permanent.
2. **A short IT architecture conversation** to scope production hosting.
3. **Direction on who owns product content authoring** — this is the real
   workload and it sits outside my team.

I can demo the working prototype whenever it's useful.

---

## Appendix: what the prototype does today

- Ingests our GDSN/Syndigo exports and reports exactly which fields are missing
- Validates GTINs, including the check digit
- Generates GS1 Digital Link QR codes as SVG (print) and PNG (proofing)
- Maintains the QR catalog described in the intern project brief — code, target,
  where the image lives, where the code exists in the world, static vs dynamic,
  owner, and whether the item needs its own product page
- Lets a non-technical user author a tabbed product page (Nutrition,
  Ingredients, Allergens, Home) without writing any code
- Serves that page and resolves the printed code to it
- Exports everything to JSON and CSV — this tool must not become its own trap

Verified: generated codes were decoded back and confirmed to carry the correct
canonical `/01/{GTIN}` URL.
