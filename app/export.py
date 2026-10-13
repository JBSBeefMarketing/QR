"""Export everything, always.

This tool is being built so JBS is not dependent on someone else's database.
It would be a poor joke if the tool then became the trap, so every table is
dumpable to JSON and CSV with no ceremony.
"""

from __future__ import annotations

import csv
import io
import json

from . import db

TABLES = ["products", "pages", "links", "catalog"]


def dump_table(name: str) -> list[dict]:
    if name not in TABLES:
        raise ValueError(f"unknown table: {name}")
    with db.cursor() as conn:
        rows = conn.execute(f"SELECT * FROM {name}").fetchall()
    return [dict(r) for r in rows]


def dump_all() -> dict:
    payload = {name: dump_table(name) for name in TABLES}
    # Pages store JSON in a text column; unpack it so the export is readable
    # rather than a string containing escaped JSON.
    for page in payload["pages"]:
        try:
            page["content"] = json.loads(page["content"])
        except (TypeError, ValueError):
            pass
    return payload


def to_json() -> str:
    return json.dumps(dump_all(), indent=2, ensure_ascii=False)


def to_csv(name: str) -> str:
    rows = dump_table(name)
    buffer = io.StringIO()
    if not rows:
        return ""
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()
