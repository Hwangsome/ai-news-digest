from datetime import datetime, timezone

from ai_news.models import Category, DigestItem, RawItem
from ai_news.pipeline.rank import rank_and_dedup, weekly_candidate_ids

UTC = timezone.utc


def _d(id_: str, title: str, cat: Category, score: float) -> DigestItem:
    raw = RawItem(id=id_, source="s", title=title, url=f"u/{id_}",
                  published_at=datetime(2026, 4, 22, tzinfo=UTC),
                  raw_text=None, metadata={})
    return DigestItem(raw=raw, cn_title=title, cn_summary="", category=cat, score=score)


def test_sorts_by_score_descending():
    out = rank_and_dedup(
        [_d("1", "a", Category.PRODUCT, 5.0),
         _d("2", "b", Category.PRODUCT, 8.0),
         _d("3", "c", Category.PRODUCT, 6.0)],
        max_total=10, per_category_cap=10, dup_threshold=85,
    )
    assert [d.raw.id for d in out] == ["2", "3", "1"]


def test_drops_near_duplicates():
    out = rank_and_dedup(
        [_d("1", "GPT-5 launch announced today", Category.MODEL_RELEASE, 9.0),
         _d("2", "GPT-5 announced today launch", Category.MODEL_RELEASE, 8.5),
         _d("3", "Unrelated topic entirely", Category.OPINION, 7.0)],
        max_total=10, per_category_cap=10, dup_threshold=85,
    )
    ids = [d.raw.id for d in out]
    assert "1" in ids and "3" in ids and "2" not in ids


def test_caps_per_category_and_total():
    items = [_d(str(i), f"title {i}", Category.PRODUCT, 10.0 - i * 0.1) for i in range(10)]
    items += [_d(f"r{i}", f"research {i}", Category.RESEARCH, 10.0 - i * 0.1) for i in range(10)]
    out = rank_and_dedup(items, max_total=6, per_category_cap=3, dup_threshold=85)
    assert len(out) == 6
    from collections import Counter
    counts = Counter(d.category for d in out)
    assert counts[Category.PRODUCT] <= 3
    assert counts[Category.RESEARCH] <= 3


def test_weekly_candidate_ids():
    items = [_d("1", "t1", Category.PRODUCT, 9.5),
             _d("2", "t2", Category.PRODUCT, 7.0),
             _d("3", "t3", Category.PRODUCT, 8.0)]
    ids = weekly_candidate_ids(items, threshold=8.0)
    assert set(ids) == {"1", "3"}


def test_empty_input():
    assert rank_and_dedup([], max_total=10, per_category_cap=3, dup_threshold=85) == []
    assert weekly_candidate_ids([], threshold=8.0) == []
