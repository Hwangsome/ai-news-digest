"""SQLite-backed store of item IDs already shown to the user."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

SeenRow = tuple[str, str, str, float, bool]  # id, source, url, score, weekly_candidate

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    score REAL,
    weekly_candidate INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_first_seen ON seen_items(first_seen_at);
"""


class SeenItemsDB:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def initialize(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)

    def has(self, item_id: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM seen_items WHERE id = ?", (item_id,)).fetchone()
            return row is not None

    def mark_seen(self, rows: list[SeenRow], *, now: datetime) -> None:
        ts = now.isoformat()
        with self._conn() as c:
            c.executemany(
                "INSERT OR IGNORE INTO seen_items"
                "(id, source, url, first_seen_at, score, weekly_candidate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(r[0], r[1], r[2], ts, r[3], 1 if r[4] else 0) for r in rows],
            )

    def weekly_candidates(self, *, since: datetime) -> list[SeenRow]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT id, source, url, score, weekly_candidate FROM seen_items "
                "WHERE weekly_candidate = 1 AND first_seen_at >= ?",
                (since.isoformat(),),
            )
            return [(r[0], r[1], r[2], r[3] or 0.0, bool(r[4])) for r in cur.fetchall()]

    def purge_older_than(self, *, cutoff: datetime) -> int:
        with self._conn() as c:
            cur = c.execute("DELETE FROM seen_items WHERE first_seen_at < ?", (cutoff.isoformat(),))
            return cur.rowcount
