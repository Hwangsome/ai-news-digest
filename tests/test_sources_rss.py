from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_news.sources.rss import RSSSource

UTC = timezone.utc
FIXTURES = Path(__file__).parent / "fixtures"


def test_rss_parses_items(monkeypatch):
    src = RSSSource(name="OpenAI", url="file://ignored", weight=1.0)
    xml = (FIXTURES / "openai_rss.xml").read_bytes()
    monkeypatch.setattr(src, "_fetch_bytes", lambda: xml)
    items = src.fetch(since=datetime(2026, 4, 21, tzinfo=UTC))
    assert len(items) == 1
    assert items[0].title == "Introducing GPT-5"
    assert items[0].source == "OpenAI"
    assert items[0].url == "https://openai.com/blog/gpt-5"
    assert items[0].raw_text is not None
    assert "GPT-5" in items[0].raw_text
    assert len(items[0].id) == 16


def test_rss_filters_out_items_older_than_since(monkeypatch):
    src = RSSSource(name="OpenAI", url="file://x", weight=1.0)
    monkeypatch.setattr(src, "_fetch_bytes",
                       lambda: (FIXTURES / "openai_rss.xml").read_bytes())
    since = datetime(2026, 4, 22, tzinfo=UTC) - timedelta(hours=6)
    assert len(src.fetch(since=since)) == 1
    since = datetime(2027, 1, 1, tzinfo=UTC)
    assert src.fetch(since=since) == []
