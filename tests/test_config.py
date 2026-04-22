from pathlib import Path

import pytest

from ai_news.config import Config, SourceSpec, load_config


def test_load_config_test_toml(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    cfg = load_config(Path("config.test.toml"))
    assert isinstance(cfg, Config)
    assert cfg.general.recipient_email == "test@example.com"
    assert cfg.daily.pre_filter_top_n == 40
    assert cfg.keywords.high == ["claude", "gpt", "agent"]
    assert cfg.llm.api_key == "k"
    assert cfg.smtp.host == "smtp.example.com"
    assert cfg.smtp.port == 465
    assert cfg.sources[0] == SourceSpec(
        type="rss", name="Fake", url="https://example.com/feed.xml", weight=1.0
    )


def test_missing_smtp_secret_raises(monkeypatch, tmp_path: Path):
    (tmp_path / "c.toml").write_text(Path("config.test.toml").read_text())
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        load_config(tmp_path / "c.toml")


def test_source_spec_rejects_rss_without_url():
    with pytest.raises(ValueError, match="requires 'url'"):
        SourceSpec(type="rss", name="X", weight=1.0)


def test_source_spec_rejects_github_without_repo():
    with pytest.raises(ValueError, match="requires 'repo'"):
        SourceSpec(type="github_releases", name="X", weight=1.0)


def test_source_spec_rejects_unknown_type():
    with pytest.raises(ValueError, match="unknown type"):
        SourceSpec(type="twitter", name="X", weight=1.0, url="https://x")


def test_non_numeric_smtp_port_raises_clear_error(monkeypatch, tmp_path: Path):
    (tmp_path / "c.toml").write_text(Path("config.test.toml").read_text())
    for k, v in {"LLM_API_KEY": "k", "SMTP_HOST": "h",
                 "SMTP_PORT": "not-a-number",
                 "SMTP_USER": "u", "SMTP_PASS": "p"}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(RuntimeError, match="SMTP_PORT must be an integer"):
        load_config(tmp_path / "c.toml")
