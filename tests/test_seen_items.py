from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_news.storage.seen_items import SeenItemsDB

UTC = timezone.utc


def test_insert_and_has(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    assert not db.has("id1")
    db.mark_seen([("id1", "src", "http://u", 7.2, True)], now=datetime(2026, 4, 22, tzinfo=UTC))
    assert db.has("id1")


def test_weekly_candidates_window(tmp_path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    now = datetime(2026, 4, 22, tzinfo=UTC)
    db.mark_seen([("old", "s", "u1", 9.0, True)], now=now - timedelta(days=10))
    db.mark_seen([("new", "s", "u2", 9.0, True)], now=now - timedelta(days=3))
    cands = db.weekly_candidates(since=now - timedelta(days=7))
    ids = {c[0] for c in cands}
    assert ids == {"new"}


def test_purge_removes_old(tmp_path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    now = datetime(2026, 4, 22, tzinfo=UTC)
    db.mark_seen([("old", "s", "u", 1.0, False)], now=now - timedelta(days=20))
    db.mark_seen([("young", "s", "u", 1.0, False)], now=now - timedelta(days=3))
    db.purge_older_than(cutoff=now - timedelta(days=14))
    assert not db.has("old")
    assert db.has("young")
