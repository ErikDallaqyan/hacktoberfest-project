"""Every rename is written down first, so every rename can be undone."""
import sqlite3
import threading
import time
from pathlib import Path

from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS renames (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at REAL NOT NULL,
  old_path TEXT NOT NULL,
  new_path TEXT,
  what TEXT DEFAULT '',
  category TEXT DEFAULT '',
  secrets INTEGER DEFAULT 0,
  seconds REAL DEFAULT 0,
  model TEXT DEFAULT '',
  status TEXT NOT NULL,          -- renamed | undone | edited | deleted | error | preview
  error TEXT DEFAULT '',
  trash_path TEXT DEFAULT '',    -- where a deleted file waits, so it can be restored
  prev_status TEXT DEFAULT ''    -- what to go back to on restore
);
"""
# Columns added after the first release; older journals get them on open.
MIGRATIONS = ["ALTER TABLE renames ADD COLUMN trash_path TEXT DEFAULT ''",
              "ALTER TABLE renames ADD COLUMN prev_status TEXT DEFAULT ''"]


def _conn(db_path: Path | None = None) -> sqlite3.Connection:
    c = sqlite3.connect(db_path or config.DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    for sql in MIGRATIONS:
        try:
            c.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already there
    return c


def add(**row) -> int:
    row.setdefault("created_at", time.time())
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    with _lock, _conn() as c:
        return c.execute(f"INSERT INTO renames ({cols}) VALUES ({marks})", list(row.values())).lastrowid


def update(row_id: int, **fields) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _lock, _conn() as c:
        c.execute(f"UPDATE renames SET {sets} WHERE id = ?", [*fields.values(), row_id])


def get(row_id: int) -> dict | None:
    with _lock, _conn() as c:
        r = c.execute("SELECT * FROM renames WHERE id = ?", (row_id,)).fetchone()
    return dict(r) if r else None


def recent(limit: int = 200) -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT * FROM renames ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def should_skip(path: Path) -> bool:
    """True if we produced this name ourselves, or the user undid our rename of it."""
    p = str(path)
    with _lock, _conn() as c:
        r = c.execute(
            "SELECT 1 FROM renames WHERE (new_path = ? AND status IN ('renamed','edited'))"
            " OR (old_path = ? AND status = 'undone') LIMIT 1",
            (p, p),
        ).fetchone()
    return r is not None


def totals() -> dict:
    with _lock, _conn() as c:
        r = c.execute(
            "SELECT SUM(status IN ('renamed','edited')) AS named, COALESCE(SUM(seconds), 0) AS model_seconds,"
            " SUM(status = 'undone') AS undone, SUM(status = 'edited') AS edited,"
            " SUM(status = 'error') AS errors FROM renames WHERE status != 'preview'"
        ).fetchone()
    return {k: (r[k] or 0) for k in r.keys()}
