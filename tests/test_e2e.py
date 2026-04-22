import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ai_news.delivery.smtp import InMemoryMailer
from ai_news.entrypoints import run_daily
from ai_news.sources import rss as rss_module

UTC = timezone.utc
FIXTURES = Path(__file__).parent / "fixtures"


class ScriptedLLM:
    name = "scripted"

    def complete(self, *, system, user, max_tokens):
        ids = re.findall(r'"id":\s*"([a-f0-9]{16})"', user)
        return json.dumps({"items": [
            {"id": i, "cn_title": f"中文 {i[:4]}",
             "cn_summary": "自动生成摘要。",
             "category": "模型发布", "score": 8.5}
            for i in ids
        ]})


def _set_smtp_env(monkeypatch):
    for k, v in {
        "LLM_API_KEY": "k",
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "465",
        "SMTP_USER": "u@example.com",
        "SMTP_PASS": "p",
    }.items():
        monkeypatch.setenv(k, v)


def test_daily_run_end_to_end(tmp_path, monkeypatch):
    a_bytes = (FIXTURES / "feed_a.xml").read_bytes()
    b_bytes = (FIXTURES / "feed_b.xml").read_bytes()

    def by_name_fetch(self):
        return a_bytes if self.name == "FeedA" else b_bytes

    monkeypatch.setattr(rss_module.RSSSource, "_fetch_bytes", by_name_fetch)
    _set_smtp_env(monkeypatch)

    mailer = InMemoryMailer()
    result = run_daily.main(
        config_path=FIXTURES / "two_feeds_daily.toml",
        db_path=tmp_path / "seen.sqlite",
        llm=ScriptedLLM(),
        mailer=mailer,
        now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    )

    assert result.items_rendered == 2
    assert result.sources_failed == []
    assert len(mailer.sent) == 1
    msg = mailer.sent[0]
    assert msg.to == "me@example.com"
    assert "[AI Daily]" in msg.subject
    assert "2 条" in msg.subject
    assert "模型发布" in msg.html
    assert "中文" in msg.html


def test_daily_run_handles_source_failure(tmp_path, monkeypatch):
    def failing_fetch(self):
        if self.name == "FeedA":
            raise httpx.ConnectError("boom")
        return (FIXTURES / "feed_b.xml").read_bytes()

    monkeypatch.setattr(rss_module.RSSSource, "_fetch_bytes", failing_fetch)
    _set_smtp_env(monkeypatch)

    mailer = InMemoryMailer()
    result = run_daily.main(
        config_path=FIXTURES / "two_feeds_daily.toml",
        db_path=tmp_path / "seen.sqlite",
        llm=ScriptedLLM(),
        mailer=mailer,
        now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    )
    assert result.items_rendered >= 1
    assert len(mailer.sent) == 1


def test_daily_run_dedups_across_runs(tmp_path, monkeypatch):
    a_bytes = (FIXTURES / "feed_a.xml").read_bytes()
    b_bytes = (FIXTURES / "feed_b.xml").read_bytes()

    def by_name_fetch(self):
        return a_bytes if self.name == "FeedA" else b_bytes

    monkeypatch.setattr(rss_module.RSSSource, "_fetch_bytes", by_name_fetch)
    _set_smtp_env(monkeypatch)

    db = tmp_path / "seen.sqlite"
    mailer = InMemoryMailer()
    t0 = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    result1 = run_daily.main(
        config_path=FIXTURES / "two_feeds_daily.toml",
        db_path=db, llm=ScriptedLLM(), mailer=mailer, now=t0,
    )
    assert result1.items_rendered == 2

    result2 = run_daily.main(
        config_path=FIXTURES / "two_feeds_daily.toml",
        db_path=db, llm=ScriptedLLM(), mailer=mailer, now=t0,
    )
    assert result2.items_rendered == 0
    assert len(mailer.sent) == 2
    assert "[AI Daily ✗]" in mailer.sent[1].subject


def test_daily_run_isolates_unexpected_source_exception(tmp_path, monkeypatch):
    """A source that raises a non-HTTPError (not caught by RSSSource itself)
    must not take down the whole run; the other source still produces output."""

    def boom_or_ok(self):
        if self.name == "FeedA":
            raise RuntimeError("unexpected crash in parser")
        return (FIXTURES / "feed_b.xml").read_bytes()

    monkeypatch.setattr(rss_module.RSSSource, "_fetch_bytes", boom_or_ok)
    _set_smtp_env(monkeypatch)

    mailer = InMemoryMailer()
    result = run_daily.main(
        config_path=FIXTURES / "two_feeds_daily.toml",
        db_path=tmp_path / "seen.sqlite",
        llm=ScriptedLLM(),
        mailer=mailer,
        now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    )
    assert "FeedA" in result.sources_failed
    assert result.items_rendered >= 1
    assert "⚠" in mailer.sent[0].subject or "⚠" in mailer.sent[0].html


def test_weekly_digest_uses_cached_content(tmp_path, monkeypatch):
    """Weekly should reuse cn_title/cn_summary from the daily run — no LLM call."""
    from ai_news.entrypoints import run_weekly

    a_bytes = (FIXTURES / "feed_a.xml").read_bytes()
    b_bytes = (FIXTURES / "feed_b.xml").read_bytes()

    def by_name_fetch(self):
        return a_bytes if self.name == "FeedA" else b_bytes

    monkeypatch.setattr(rss_module.RSSSource, "_fetch_bytes", by_name_fetch)
    _set_smtp_env(monkeypatch)

    db = tmp_path / "seen.sqlite"
    mailer = InMemoryMailer()
    t_daily = datetime(2026, 4, 22, 12, 0, tzinfo=UTC)

    run_daily.main(
        config_path=FIXTURES / "two_feeds_daily.toml",
        db_path=db, llm=ScriptedLLM(), mailer=mailer, now=t_daily,
    )
    assert len(mailer.sent) == 1

    t_weekly = t_daily
    result = run_weekly.main(
        config_path=FIXTURES / "two_feeds_daily.toml",
        db_path=db, mailer=mailer, now=t_weekly,
    )
    assert result.items_rendered == 2
    assert len(mailer.sent) == 2
    weekly_msg = mailer.sent[1]
    assert "[AI Weekly]" in weekly_msg.subject
    assert "本周 2 条精选" in weekly_msg.subject
    assert "中文" in weekly_msg.html
