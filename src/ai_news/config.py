"""Load ``config.toml`` and validate required env secrets."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _env(name: str, *, required: bool = True, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val or ""


@dataclass(frozen=True)
class GeneralCfg:
    timezone: str
    recipient_email: str
    digest_language: str


@dataclass(frozen=True)
class LLMCfg:
    provider: str
    model: str
    api_key: str
    max_output_tokens_daily: int
    max_output_tokens_weekly: int
    fallback_provider: str | None = None
    fallback_model: str | None = None
    fallback_api_key: str | None = None


@dataclass(frozen=True)
class DailyCfg:
    send_hour_local: int
    lookback_hours: int
    pre_filter_top_n: int
    final_max_items: int


@dataclass(frozen=True)
class WeeklyCfg:
    send_weekday: str
    send_hour_local: int
    weekly_candidate_threshold: float


@dataclass(frozen=True)
class KeywordsCfg:
    high: list[str] = field(default_factory=list)
    medium: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SMTPCfg:
    host: str
    port: int
    user: str
    password: str


@dataclass(frozen=True)
class SourceSpec:
    type: str
    name: str
    weight: float
    url: str | None = None
    repo: str | None = None


@dataclass(frozen=True)
class Config:
    general: GeneralCfg
    llm: LLMCfg
    daily: DailyCfg
    weekly: WeeklyCfg
    keywords: KeywordsCfg
    smtp: SMTPCfg
    sources: list[SourceSpec]


def load_config(path: Path) -> Config:
    raw: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))

    llm_raw = raw["llm"]
    fb = llm_raw.get("fallback") or {}

    return Config(
        general=GeneralCfg(**raw["general"]),
        llm=LLMCfg(
            provider=llm_raw["provider"],
            model=llm_raw["model"],
            api_key=_env("LLM_API_KEY"),
            max_output_tokens_daily=llm_raw["max_output_tokens_daily"],
            max_output_tokens_weekly=llm_raw["max_output_tokens_weekly"],
            fallback_provider=fb.get("provider"),
            fallback_model=fb.get("model"),
            fallback_api_key=_env("LLM_FALLBACK_API_KEY", required=False) or None,
        ),
        daily=DailyCfg(**raw["daily"]),
        weekly=WeeklyCfg(**raw["weekly"]),
        keywords=KeywordsCfg(**raw.get("keywords", {})),
        smtp=SMTPCfg(
            host=_env("SMTP_HOST"),
            port=int(_env("SMTP_PORT")),
            user=_env("SMTP_USER"),
            password=_env("SMTP_PASS"),
        ),
        sources=[SourceSpec(**s) for s in raw["sources"]["items"]],
    )
