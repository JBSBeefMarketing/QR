"""SQLite storage.

Four tables, in dependency order:

  products  - normalised product data ingested from the GDSN/Syndigo exports
  pages     - the authored consumer page for a GTIN (draft or published)
  links     - the link map: what a Digital Link URI resolves to
  catalog   - the register of every JBS QR code, Digital Link or not

Everything here is exportable by design (see export.py). The point of hosting
internally is that the data is never trapped, including by this tool.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

DATA_DIR = config.DATA_DIR
DB_PATH = DATA_DIR / "catalog.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    gtin14              TEXT PRIMARY KEY,
    jbs_sku             TEXT,
    brand               TEXT,
    trade_item_desc     TEXT,
    short_description   TEXT,
    functional_name     TEXT,
    net_weight          TEXT,
    net_weight_uom      TEXT,
    ingredients         TEXT,
    storage             TEXT,
    prep_serving        TEXT,
    marketing_message   TEXT,
    country_of_origin   TEXT,
    nutrition_raw       TEXT,
    allergens_raw       TEXT,
    image_ref           TEXT,
    unit_descriptor     TEXT,
    sold_to_consumer    TEXT,
    source_file         TEXT,
    ingested_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pages (
    gtin14      TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'draft',   -- draft | published
    content     TEXT NOT NULL,                   -- JSON, see pages.blank_content()
    updated_at  TEXT NOT NULL,
    FOREIGN KEY (gtin14) REFERENCES products(gtin14)
);

CREATE TABLE IF NOT EXISTS links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    gtin14      TEXT NOT NULL,
    lot         TEXT,
    serial      TEXT,
    link_type   TEXT NOT NULL,
    href        TEXT NOT NULL,
    title       TEXT,
    lang        TEXT DEFAULT 'en',
    region      TEXT DEFAULT 'US',
    is_default  INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_links_gtin ON links(gtin14);

CREATE TABLE IF NOT EXISTS catalog (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    category          TEXT NOT NULL,      -- I | II | III
    code_kind         TEXT NOT NULL,      -- digital_link | plain_url
    gtin14            TEXT,               -- null for Category I / plain URLs
    brand             TEXT,
    label             TEXT NOT NULL,
    target_url        TEXT NOT NULL,
    world_location    TEXT,               -- where the code exists in the world
    is_dynamic        INTEGER NOT NULL DEFAULT 1,
    owner             TEXT,
    owner_contact     TEXT,
    needs_pdp         INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'logged',
    notes             TEXT,
    qr_png            TEXT,
    qr_svg            TEXT,
    qr_dark           TEXT NOT NULL DEFAULT '#000000',
    qr_light          TEXT NOT NULL DEFAULT '#ffffff',
    created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_catalog_gtin ON catalog(gtin14);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def cursor():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with cursor() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


# Columns added after the first databases were created. SQLite has no
# "ADD COLUMN IF NOT EXISTS", so check first. Dropped columns are left alone -
# an old database keeps them, nothing reads them, and that is cheaper than a
# table rebuild on a prototype.
ADDED_COLUMNS = {
    "catalog": {
        "qr_dark": "TEXT NOT NULL DEFAULT '#000000'",
        "qr_light": "TEXT NOT NULL DEFAULT '#ffffff'",
    },
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in ADDED_COLUMNS.items():
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, spec in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")


# --- products ---------------------------------------------------------------

def upsert_product(conn: sqlite3.Connection, row: dict) -> None:
    row = dict(row)
    row["ingested_at"] = utcnow()
    cols = ", ".join(row)
    placeholders = ", ".join(f":{c}" for c in row)
    updates = ", ".join(f"{c}=excluded.{c}" for c in row if c != "gtin14")
    conn.execute(
        f"INSERT INTO products ({cols}) VALUES ({placeholders}) "
        f"ON CONFLICT(gtin14) DO UPDATE SET {updates}",
        row,
    )


def get_product(gtin14: str) -> sqlite3.Row | None:
    with cursor() as conn:
        return conn.execute(
            "SELECT * FROM products WHERE gtin14 = ?", (gtin14,)
        ).fetchone()


def list_products(search: str = "", limit: int = 500) -> list[sqlite3.Row]:
    q = """
        SELECT p.*,
               pg.status AS page_status,
               (SELECT COUNT(*) FROM catalog c WHERE c.gtin14 = p.gtin14) AS code_count
        FROM products p
        LEFT JOIN pages pg ON pg.gtin14 = p.gtin14
    """
    params: list = []
    if search:
        q += """ WHERE p.gtin14 LIKE ? OR p.brand LIKE ? OR p.trade_item_desc LIKE ?
                    OR p.jbs_sku LIKE ?"""
        params += [f"%{search}%"] * 4
    q += " ORDER BY p.brand, p.trade_item_desc LIMIT ?"
    params.append(limit)
    with cursor() as conn:
        return conn.execute(q, params).fetchall()


# --- pages ------------------------------------------------------------------

def get_page(gtin14: str) -> dict | None:
    with cursor() as conn:
        row = conn.execute(
            "SELECT * FROM pages WHERE gtin14 = ?", (gtin14,)
        ).fetchone()
    if not row:
        return None
    return {
        "gtin14": row["gtin14"],
        "status": row["status"],
        "content": json.loads(row["content"]),
        "updated_at": row["updated_at"],
    }


def save_page(gtin14: str, content: dict, status: str = "draft") -> None:
    with cursor() as conn:
        conn.execute(
            """INSERT INTO pages (gtin14, status, content, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(gtin14) DO UPDATE SET
                   status=excluded.status,
                   content=excluded.content,
                   updated_at=excluded.updated_at""",
            (gtin14, status, json.dumps(content, indent=2), utcnow()),
        )


# --- links ------------------------------------------------------------------

def add_link(
    gtin14: str,
    href: str,
    link_type: str,
    *,
    lot: str | None = None,
    serial: str | None = None,
    title: str | None = None,
    is_default: bool = False,
) -> None:
    """Insert a link, enforcing exactly one default per (gtin, lot, serial).

    The Resolver standard requires that for any request URI, however granular,
    there is always exactly one default link.
    """
    with cursor() as conn:
        if is_default:
            conn.execute(
                """UPDATE links SET is_default = 0
                   WHERE gtin14 = ? AND IFNULL(lot,'') = IFNULL(?,'')
                     AND IFNULL(serial,'') = IFNULL(?,'')""",
                (gtin14, lot, serial),
            )
        conn.execute(
            """INSERT INTO links
               (gtin14, lot, serial, link_type, href, title, is_default, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (gtin14, lot, serial, link_type, href, title, int(is_default), utcnow()),
        )


def get_links(gtin14: str, lot: str | None = None, serial: str | None = None):
    """Links for an entity, most specific match first.

    A request for /01/x/10/y falls back to the links registered against /01/x
    when nothing lot-specific exists, so a GTIN-level default always answers.
    """
    with cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM links WHERE gtin14 = ? ORDER BY is_default DESC, id",
            (gtin14,),
        ).fetchall()

    exact = [r for r in rows if (r["lot"] or None) == lot and (r["serial"] or None) == serial]
    if exact:
        return exact
    return [r for r in rows if not r["lot"] and not r["serial"]]


# --- catalog ----------------------------------------------------------------

def add_catalog_entry(entry: dict) -> int:
    entry = dict(entry)
    entry["created_at"] = utcnow()
    cols = ", ".join(entry)
    placeholders = ", ".join(f":{c}" for c in entry)
    with cursor() as conn:
        cur = conn.execute(
            f"INSERT INTO catalog ({cols}) VALUES ({placeholders})", entry
        )
        return cur.lastrowid


def list_catalog(category: str = "", search: str = "") -> list[sqlite3.Row]:
    q = "SELECT * FROM catalog WHERE 1=1"
    params: list = []
    if category:
        q += " AND category = ?"
        params.append(category)
    if search:
        q += " AND (label LIKE ? OR gtin14 LIKE ? OR owner LIKE ? OR brand LIKE ?)"
        params += [f"%{search}%"] * 4
    q += " ORDER BY category, brand, label"
    with cursor() as conn:
        return conn.execute(q, params).fetchall()


def get_catalog_entry(entry_id: int) -> sqlite3.Row | None:
    with cursor() as conn:
        return conn.execute("SELECT * FROM catalog WHERE id = ?", (entry_id,)).fetchone()
