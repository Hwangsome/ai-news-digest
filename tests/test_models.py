from datetime import datetime, timezone

from ai_news.models import Category, DigestItem, RawItem, stable_id


def test_stable_id_same_for_same_url_and_source():
    a = stable_id(source="openai", url="https://openai.com/blog/a")
    b = stable_id(source="openai", url="https://openai.com/blog/a")
    assert a == b and len(a) == 16


def test_stable_id_differs_by_source():
    a = stable_id(source="openai", url="https://x.com")
    b = stable_id(source="anthropic", url="https://x.com")
    assert a != b


def test_raw_item_is_frozen():
    item = RawItem(
        id="abc", source="s", title="t", url="u",
        published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        raw_text=None, metadata={},
    )
    import dataclasses
    assert dataclasses.is_dataclass(item)
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.title = "x"  # type: ignore[misc]


def test_category_values_are_chinese():
    assert Category.MODEL_RELEASE.value == "模型发布"
    assert Category.RESEARCH.value == "研究与论文"


def test_digest_item_composes_raw():
    raw = RawItem(
        id="x", source="s", title="Hi", url="u",
        published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        raw_text="body", metadata={},
    )
    d = DigestItem(
        raw=raw, cn_title="你好", cn_summary="摘要", category=Category.PRODUCT, score=7.5,
    )
    assert d.raw.title == "Hi"
    assert d.score == 7.5
