from datetime import datetime, timezone

from ai_news.sources.github import GitHubReleasesSource

UTC = timezone.utc

SAMPLE = [
    {
        "name": "v0.5.0",
        "html_url": "https://github.com/anthropics/claude-code/releases/tag/v0.5.0",
        "published_at": "2026-04-22T10:00:00Z",
        "body": "New features: subagents, skills.",
        "prerelease": False,
        "draft": False,
    },
    {
        "name": "v0.4.0 draft",
        "html_url": "https://github.com/anthropics/claude-code/releases/tag/v0.4.0",
        "published_at": "2026-04-21T10:00:00Z",
        "body": "draft",
        "prerelease": False,
        "draft": True,
    },
]


def test_github_releases_parses(monkeypatch):
    src = GitHubReleasesSource(name="claude-code", repo="anthropics/claude-code",
                               weight=0.9, token=None)
    monkeypatch.setattr(src, "_fetch_json", lambda: SAMPLE)
    items = src.fetch(since=datetime(2026, 4, 22, tzinfo=UTC))
    assert len(items) == 1
    assert items[0].title == "claude-code v0.5.0"
    assert "subagents" in items[0].raw_text
