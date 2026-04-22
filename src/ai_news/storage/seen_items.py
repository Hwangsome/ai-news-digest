"""SQLite-backed store of item IDs already shown to the user."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    cn_title TEXT,
    cn_summary TEXT,
    category TEXT,
    first_seen_at TEXT NOT NULL,
    score REAL,
    weekly_candidate INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_first_seen ON seen_items(first_seen_at);
"""


@dataclass(frozen=True)
class SeenRow:
    id: str
    source: str
    url: str
    title: str
    cn_title: str | None
    cn_summary: str | None
    category: str | None
    score: float
    weekly_candidate: bool


class SeenItemsDB:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def initialize(self) -> None:
        conn = self._conn()
        try:
            # WAL is persistent on the file; set it once at initialization.
            conn.execute("PRAGMA journal_mode=WAL")
            with conn:
                conn.executescript(SCHEMA)
        finally:
            conn.close()

    def has(self, item_id: str) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM seen_items WHERE id = ?", (item_id,)
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def has_many(self, item_ids: list[str]) -> set[str]:
        """Return the subset of ids already present in the store."""
        if not item_ids:
            return set()
        found: set[str] = set()
        conn = self._conn()
        try:
            for start in range(0, len(item_ids), 500):
                chunk = item_ids[start : start + 500]
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT id FROM seen_items WHERE id IN ({placeholders})",
                    chunk,
                ).fetchall()
                found.update(r[0] for r in rows)
        finally:
            conn.close()
        return found

    def mark_seen(self, rows: list[SeenRow], *, now: datetime) -> None:
        if not rows:
            return
        ts = now.isoformat()
        conn = self._conn()
        try:
            with conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO seen_items"
                    "(id, source, url, title, cn_title, cn_summary, category,"
                    " first_seen_at, score, weekly_candidate) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        (
                            r.id,
                            r.source,
                            r.url,
                            r.title,
                            r.cn_title,
                            r.cn_summary,
                            r.category,
                            ts,
                            r.score,
                            1 if r.weekly_candidate else 0,
                        )
                        for r in rows
                    ],
                )
        finally:
            conn.close()

    def weekly_candidates(self, *, since: datetime) -> list[SeenRow]:
        conn = self._conn()
        try:
            cur = conn.execute(
                "SELECT id, source, url, title, cn_title, cn_summary, category,"
                " score, weekly_candidate "
                "FROM seen_items "
                "WHERE weekly_candidate = 1 AND first_seen_at >= ?",
                (since.isoformat(),),
            )
            return [
                SeenRow(
                    id=r[0],
                    source=r[1],
                    url=r[2],
                    title=r[3] or "",
                    cn_title=r[4],
                    cn_summary=r[5],
                    category=r[6],
                    score=r[7] or 0.0,
                    weekly_candidate=bool(r[8]),
                )
                for r in cur.fetchall()
            ]
        finally:
            conn.close()

    def purge_older_than(self, *, cutoff: datetime) -> int:
        conn = self._conn()
        try:
            with conn:
                cur = conn.execute(
                    "DELETE FROM seen_items WHERE first_seen_at < ?",
                    (cutoff.isoformat(),),
                )
                return cur.rowcount
        finally:
            conn.close()
