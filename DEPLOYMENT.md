# Putting this on jbs-qr.com, by yourself

Written for: Preston, working solo, with no IT support beyond the domain
purchase. No prior deployment experience assumed.

Realistic time: **one afternoon** for steps 1–6. Then a pause while you test,
before anything gets printed.

Cost: **$7/month** plus about **$0.25/month** for storage.

---

## The one rule

**Nothing gets printed until you can scan a code with your phone, on cellular
data, away from the office, and watch a real page load.**

Everything below serves that. The QR code is the only part of this project
that can't be revised later.

---

## What "deploying" actually means

Right now the app runs on your laptop. When you close the terminal, it stops.
Nobody else can reach it.

Deploying means putting the same code on a computer that is always on and
always connected, then pointing `jbs-qr.com` at that computer. That's it.
There's no difference in the code — it's the same files, running somewhere
else.

Three pieces have to come together:

| Piece | What it is | Who provides it |
|---|---|---|
| **The code** | The files in this folder | You, via GitHub |
| **The computer** | An always-on machine running them | Render, $7/month |
| **The address** | `jbs-qr.com` pointing at that machine | Already bought; you set one record |

---

## Why Render, and why not Azure

The earlier plan assumed Azure App Service. That assumed IT. Without them you
can't get into JBS's Azure tenant, so it's off the table.

**Render** is a hosting service you can sign up for yourself with a card. You
connect it to GitHub, and every time you update the code it redeploys on its
own. Custom domains and HTTPS certificates are included and automatic.

**This does not undermine the whole premise of the project.** The argument for
building internally was never "never use an outside service" — it was "never
let a printed code depend on one." You own `jbs-qr.com`. If Render disappears
tomorrow, you move the code elsewhere, change one DNS record, and every
printed package keeps working. That is precisely the protection the original
platform couldn't offer, and it still holds here.

### One simplification worth knowing

The earlier plan said you'd have to replace the database before going live.
That was true for Azure, which can move your app between machines without
warning and would have lost the file.

Render lets you attach a **persistent disk** — storage that survives restarts
and redeploys. So the existing database works as-is. That removes several days
of work and a whole category of things that could go wrong.

The trade-off, honestly: you can only run **one** copy of the app. That's
completely fine for this traffic, and you'd notice the limit long before it
mattered. If it ever becomes a problem, it's a good problem.

---

## Before you start

Have these ready:

- A **GitHub account under `beefmktg@jbssa.com`** — not your personal one
- A card you can expense
- Access to wherever `jbs-qr.com`'s DNS is managed (ask IT who holds this)

**On the shared account:** your instinct is right, and it's the same principle
as the domain. If this lives under your personal GitHub, then the day you
change roles, JBS loses the ability to update its own product pages. Put it
somewhere the company owns. Use the same shared address for the Render account
too.

---

## Step 1 — Create the GitHub account

GitHub stores the code and is what Render reads from.

1. Go to <https://github.com/signup>
2. Sign up with `beefmktg@jbssa.com`
3. Save the password in whatever JBS uses for shared credentials
4. Turn on two-factor authentication when prompted

---

## Step 2 — Put the code on GitHub

On github.com, click **+** (top right) → **New repository**.

- Name: `jbs-digital-link`
- **Private** — not public
- Don't add a README or .gitignore; this folder already has both
- Click **Create repository**

GitHub then shows a page of commands. Ignore it and run these instead, in a
terminal in this folder (`C:\Users\pevans3\dev\jbs-digital-link`).

`git init` and `git add` have already been done for you, so start here:

```
git commit -m "JBS Digital Link resolver and QR catalog"
git branch -M main
git remote add origin https://github.com/YOUR-ACCOUNT/jbs-digital-link.git
git push -u origin main
```

Replace `YOUR-ACCOUNT` with the account name you just made. It'll ask you to
sign in.

**What that did:** uploaded the code. The `.gitignore` file deliberately keeps
`data/` out of it, so your local test catalog doesn't get uploaded and later
overwrite the live one.

---

## Step 3 — Create the Render service

1. Go to <https://render.com> and sign up **with GitHub**, using the shared
   account. That links the two automatically.
2. **New** → **Web Service**
3. Pick the `jbs-digital-link` repository
4. Render reads [render.yaml](render.yaml) and fills in nearly everything —
   the Python version, the start command, the disk. Confirm it shows:
   - Plan: **Starter ($7/month)** — not Free. The free tier sleeps after
     inactivity, so the first scan after a quiet spell takes ~50 seconds. On
     packaging that reads as broken.
   - Disk: **1 GB at `/var/data`**
5. Click **Create Web Service**

First build takes a few minutes. When it finishes you get a URL like
`jbs-digital-link.onrender.com`.

---

## Step 4 — Set the admin password

**Do this immediately.** Until you do, the admin area is locked — deliberately,
so an unprotected site can never be live. The public pages work fine meanwhile.

In Render: your service → **Environment** → **Add Environment Variable**

| Key | Value |
|---|---|
| `JBS_DL_ADMIN_PASSWORD` | a long random password |

Save it in shared credentials. The username is `jbs`.

Render restarts the service. Visit `https://your-app.onrender.com/admin/` and
your browser will prompt for the username and password.

**What's protected and what isn't:**

- `/admin/*` — password required. Everything that edits anything.
- `/p/{GTIN}` and `/01/{GTIN}` — public, always. They exist to be scanned.

---

## Step 5 — Load the products

Your laptop has the 162 ingested products; the new server starts empty.

Easiest route: on your laptop, go to `/admin/export.json` and save the file.
Then from the folder, with the server running locally:

```
python -m app.ingest
```

...and re-run it against the live site later, or simply re-author the handful
of pages you actually need. Given only a few products will have real pages at
first, re-doing them in the live admin is often faster than migrating.

---

## Step 6 — Hand the DNS records to IT

IT has confirmed the process: they have reserved the domain, and once a site
is running on a server they will configure DNS to point at it. That is exactly
this step, and it is the only one they are involved in.

**First, in Render:** your service → **Settings** → **Custom Domains** →
**Add**. Enter `jbs-qr.com`, then add `www.jbs-qr.com` as well. Render will
immediately show the DNS records it wants, and will say something like
"verifying" or "DNS not configured". That is expected — it is waiting for IT.

**Then send IT exactly these values.** Copy them from the Render screen; do not
retype from memory.

| Type | Name / Host | Value |
|---|---|---|
| `A` | `@` (the bare domain) | the IP address Render displays |
| `CNAME` | `www` | your `xxxx.onrender.com` address |

Useful to include in the request:

- Ask for **TTL 300** on both records if their panel exposes it. A short TTL
  means a wrong value takes five minutes to correct instead of a day. It can
  be raised later.
- Flag the apex gotcha up front: **`jbs-qr.com` itself needs an A record, not
  a CNAME.** A bare domain cannot be a CNAME. `www` can be. This is the single
  most common point of confusion, and naming it before they hit it saves a
  round trip.
- Mention HTTPS is handled automatically by the host, so they do not need to
  supply or install a certificate. People often assume they do.

**After they confirm:** DNS takes anywhere from a few minutes to a few hours
to propagate. Render detects the records on its own and issues the HTTPS
certificate automatically — no further action from you or IT.

There is no deadlock here, despite appearances. Render asks for DNS before it
will issue a certificate, and IT asks for a running site before they configure
DNS. Both are satisfied by this order: site up → add custom domain in Render →
records to IT → IT configures → certificate issues by itself.

---

## Step 7 — Switch the domain on

Only once `https://jbs-qr.com/admin/` actually loads.

In Render → **Environment**, add:

| Key | Value |
|---|---|
| `JBS_DL_DOMAIN` | `jbs-qr.com` |
| `JBS_DL_SCHEME` | `https` |

This is what makes generated codes carry the real address. The orange
"provisional domain" banner disappears — that banner is your safety catch, so
don't set these early.

---

## Step 8 — Test before printing anything

```
python -m tests.conformance https://jbs-qr.com
```

Expect 14/14. Then run the official GS1 test suite, which needs a public
address and so couldn't run until now:
<https://ref.gs1.org/test-suites/resolver/>

**Then the test that actually counts:**

1. Create a code in the admin
2. Print it — on packaging stock if you can get any, not just copy paper
3. **Turn off Wi-Fi on your phone**, so you're on cellular like a shopper
4. Scan it
5. The product page should load

If that works, you're live. Office-laser-on-copy-paper proves very little
about ink on film, so do push for a real substrate proof before a print run.

---

## Keeping it alive

Four things, none of which take long.

**Back up monthly.** Visit `/admin/export.json`, save the file somewhere in
OneDrive. That's your whole catalog in one file. Render's disk is reliable but
it is not a backup, and a backup nobody has tested isn't one either.

**Watch the domain expiry.** This is the biggest long-term risk in the whole
project. If `jbs-qr.com` lapses, every printed package breaks, and nobody finds
out until a customer complains. Ask IT to confirm auto-renew is on and the
registration is paid several years out. Put a calendar reminder on it yourself
regardless.

**Monitor uptime.** Sign up for a free account at <https://uptimerobot.com> and
point it at `https://jbs-qr.com/healthz` every 5 minutes, alerting a shared
address. That endpoint checks the database too, so a healthy response means
more than "the server is on."

**Never change the URL format.** New content and new link types are fine
forever. The shape — `jbs-qr.com/01/{GTIN}` — is frozen the moment the first
package prints.

---

## Still unresolved

**Nutrition content.** Unrelated to deployment, but it remains the real
workload: the GDSN export has no nutrition, allergen or serving data for any
item, so every product page needs that authored by hand.
