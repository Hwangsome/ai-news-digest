from datetime import datetime, timezone

import httpx

from ai_news.sources.github import GitHubReleasesSource

UTC = timezone.utc


def _src(monkeypatch, json_or_exc):
    src = GitHubReleasesSource(name="claude-code", repo="anthropics/claude-code",
                               weight=0.9, token=None)
    if isinstance(json_or_exc, Exception):
        def _raise():
            raise json_or_exc
        monkeypatch.setattr(src, "_fetch_json", _raise)
    else:
        monkeypatch.setattr(src, "_fetch_json", lambda: json_or_exc)
    return src


def _release(**overrides):
    base = {
        "name": "v1.0.0",
        "html_url": "https://github.com/anthropics/claude-code/releases/tag/v1.0.0",
        "published_at": "2026-04-22T10:00:00Z",
        "body": "notes",
        "prerelease": False,
        "draft": False,
    }
    base.update(overrides)
    return base


def test_parses_published_release(monkeypatch):
    src = _src(monkeypatch, [_release(name="v0.5.0", body="New features: subagents, skills.")])
    items = src.fetch(since=datetime(2026, 4, 22, tzinfo=UTC))
    assert len(items) == 1
    assert items[0].title == "claude-code v0.5.0"
    assert "subagents" in items[0].raw_text
    assert items[0].metadata["kind"] == "github_release"


def test_excludes_drafts_even_when_in_time_window(monkeypatch):
    # Draft's published_at is AFTER `since`, so only the draft guard can exclude it.
    src = _src(monkeypatch, [_release(name="draft-v", draft=True,
                                      published_at="2026-04-22T15:00:00Z")])
    assert src.fetch(since=datetime(2026, 4, 22, tzinfo=UTC)) == []


def test_excludes_prereleases(monkeypatch):
    src = _src(monkeypatch, [_release(name="rc1", prerelease=True,
                                      published_at="2026-04-22T15:00:00Z")])
    assert src.fetch(since=datetime(2026, 4, 22, tzinfo=UTC)) == []


def test_filters_by_published_at(monkeypatch):
    src = _src(monkeypatch, [
        _release(name="old", published_at="2026-04-20T00:00:00Z"),
        _release(name="new", published_at="2026-04-22T10:00:00Z"),
    ])
    items = src.fetch(since=datetime(2026, 4, 22, tzinfo=UTC))
    assert [i.title for i in items] == ["claude-code new"]


def test_empty_body_yields_empty_raw_text(monkeypatch):
    src = _src(monkeypatch, [_release(body=None)])
    items = src.fetch(since=datetime(2026, 4, 22, tzinfo=UTC))
    assert len(items) == 1
    assert items[0].raw_text == ""


def test_http_error_returns_empty(monkeypatch):
    src = _src(monkeypatch, httpx.ConnectError("boom"))
    assert src.fetch(since=datetime(2026, 4, 22, tzinfo=UTC)) == []


def test_json_decode_error_returns_empty(monkeypatch):
    src = _src(monkeypatch, ValueError("not json"))
    assert src.fetch(since=datetime(2026, 4, 22, tzinfo=UTC)) == []
