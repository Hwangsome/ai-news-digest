from datetime import datetime, timezone

from ai_news.config import KeywordsCfg
from ai_news.models import RawItem
from ai_news.pipeline.filter import pre_filter, score_item

UTC = timezone.utc


def _mk(title: str, source: str = "s", weight: float = 1.0,
        text: str | None = None) -> RawItem:
    return RawItem(id=title, source=source, title=title, url="u",
                   published_at=datetime(2026, 4, 22, tzinfo=UTC),
                   raw_text=text, metadata={"weight": weight})


def test_score_item_boosts_high_keywords():
    kw = KeywordsCfg(high=["claude"], medium=["benchmark"], negative=["crypto"])
    assert score_item(_mk("Claude 4.6 is out"), kw) > score_item(_mk("random post"), kw)


def test_score_item_penalizes_negative_keywords():
    kw = KeywordsCfg(high=["ai"], medium=[], negative=["crypto"])
    s_pos = score_item(_mk("AI breakthrough"), kw)
    s_neg = score_item(_mk("AI meets crypto"), kw)
    assert s_neg < s_pos


def test_pre_filter_returns_top_n_in_score_order():
    kw = KeywordsCfg(high=["claude"], medium=[], negative=[])
    items = [_mk("random"), _mk("Claude news"),
             _mk("Claude and agent"), _mk("boring")]
    out = pre_filter(items, keywords=kw, top_n=2)
    assert len(out) == 2
    assert all("claude" in i.title.lower() for i in out)


def test_pre_filter_empty_input():
    kw = KeywordsCfg(high=[], medium=[], negative=[])
    assert pre_filter([], keywords=kw, top_n=10) == []


def test_github_release_gets_bonus():
    kw = KeywordsCfg()
    plain = _mk("plain")
    release = RawItem(id="r", source="s", title="r", url="u",
                      published_at=datetime(2026, 4, 22, tzinfo=UTC),
                      raw_text=None, metadata={"weight": 1.0, "kind": "github_release"})
    assert score_item(release, kw) > score_item(plain, kw)


def test_popularity_threshold_adds_points():
    kw = KeywordsCfg()
    hot = RawItem(id="h", source="s", title="h", url="u",
                  published_at=datetime(2026, 4, 22, tzinfo=UTC),
                  raw_text=None, metadata={"weight": 1.0, "points": 300})
    cold = RawItem(id="c", source="s", title="c", url="u",
                   published_at=datetime(2026, 4, 22, tzinfo=UTC),
                   raw_text=None, metadata={"weight": 1.0, "points": 50})
    assert score_item(hot, kw) > score_item(cold, kw)
