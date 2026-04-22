from datetime import datetime, timezone
from pathlib import Path

from ai_news.models import RawItem
from ai_news.pipeline.dedup import dedup_against_seen, dedup_within_batch
from ai_news.storage.seen_items import SeenItemsDB, SeenRow

UTC = timezone.utc


def _mk(id_: str) -> RawItem:
    return RawItem(id=id_, source="s", title="t", url="u",
                   published_at=datetime(2026, 4, 22, tzinfo=UTC),
                   raw_text=None, metadata={})


def _seen_row(id_: str) -> SeenRow:
    return SeenRow(id=id_, source="s", url="u", title="t",
                   cn_title=None, cn_summary=None, category=None,
                   score=0.0, weekly_candidate=False)


def test_dedup_filters_known(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    db.mark_seen([_seen_row("a")], now=datetime(2026, 4, 22, tzinfo=UTC))
    items = [_mk("a"), _mk("b"), _mk("c")]
    out = dedup_against_seen(items, db=db)
    assert [i.id for i in out] == ["b", "c"]


def test_dedup_within_batch_keeps_first_occurrence():
    items = [_mk("x"), _mk("x"), _mk("y")]
    out = dedup_within_batch(items)
    assert [i.id for i in out] == ["x", "y"]


def test_dedup_against_seen_also_dedups_within_batch(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    items = [_mk("x"), _mk("x"), _mk("y")]
    out = dedup_against_seen(items, db=db)
    assert [i.id for i in out] == ["x", "y"]


def test_dedup_empty_inputs(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    assert dedup_within_batch([]) == []
    assert dedup_against_seen([], db=db) == []
