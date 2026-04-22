from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_news.storage.seen_items import SeenItemsDB, SeenRow

UTC = timezone.utc


def _row(id_: str, *, title: str = "t", cn_title: str | None = "中",
         cn_summary: str | None = "摘", category: str | None = "模型发布",
         score: float = 5.0, weekly: bool = False) -> SeenRow:
    return SeenRow(id=id_, source="s", url=f"http://u/{id_}", title=title,
                   cn_title=cn_title, cn_summary=cn_summary, category=category,
                   score=score, weekly_candidate=weekly)


def test_insert_and_has(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    assert not db.has("id1")
    db.mark_seen([_row("id1", score=7.2, weekly=True)],
                 now=datetime(2026, 4, 22, tzinfo=UTC))
    assert db.has("id1")


def test_has_many_returns_subset(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    db.mark_seen([_row("a"), _row("b")], now=datetime(2026, 4, 22, tzinfo=UTC))
    assert db.has_many([]) == set()
    assert db.has_many(["a", "b", "c"]) == {"a", "b"}


def test_weekly_candidates_window(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    now = datetime(2026, 4, 22, tzinfo=UTC)
    db.mark_seen([_row("old", weekly=True)], now=now - timedelta(days=10))
    db.mark_seen([_row("new", weekly=True)], now=now - timedelta(days=3))
    cands = db.weekly_candidates(since=now - timedelta(days=7))
    assert {c.id for c in cands} == {"new"}


def test_weekly_candidates_carries_content(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    now = datetime(2026, 4, 22, tzinfo=UTC)
    db.mark_seen([_row("x", title="Title X", cn_title="中标题",
                       cn_summary="中摘要", category="产品与工具",
                       score=9.0, weekly=True)],
                 now=now - timedelta(days=1))
    cands = db.weekly_candidates(since=now - timedelta(days=7))
    assert len(cands) == 1
    c = cands[0]
    assert c.title == "Title X"
    assert c.cn_title == "中标题"
    assert c.cn_summary == "中摘要"
    assert c.category == "产品与工具"


def test_weekly_candidates_excludes_non_candidates(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    now = datetime(2026, 4, 22, tzinfo=UTC)
    db.mark_seen([_row("plain", weekly=False)], now=now - timedelta(days=1))
    assert db.weekly_candidates(since=now - timedelta(days=7)) == []


def test_purge_removes_old(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    now = datetime(2026, 4, 22, tzinfo=UTC)
    db.mark_seen([_row("old", weekly=False)], now=now - timedelta(days=20))
    db.mark_seen([_row("young", weekly=False)], now=now - timedelta(days=3))
    db.purge_older_than(cutoff=now - timedelta(days=14))
    assert not db.has("old")
    assert db.has("young")


def test_mark_seen_empty_list_is_noop(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    db.mark_seen([], now=datetime(2026, 4, 22, tzinfo=UTC))
