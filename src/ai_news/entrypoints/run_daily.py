"""Daily digest entry point."""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_news.config import Config, SourceSpec, load_config
from ai_news.delivery.smtp import Mailer, SMTPMailer
from ai_news.llm.base import LLMProvider
from ai_news.llm.claude import ClaudeProvider
from ai_news.llm.fallback import FallbackLLM
from ai_news.llm.gemini import GeminiProvider
from ai_news.llm.openai_compatible import OpenAICompatibleProvider
from ai_news.pipeline.dedup import dedup_against_seen
from ai_news.pipeline.filter import pre_filter
from ai_news.pipeline.rank import rank_and_dedup, weekly_candidate_ids
from ai_news.pipeline.summarize import summarize_batch
from ai_news.renderers.html_email import render_email
from ai_news.sources.base import Source
from ai_news.sources.github import GitHubReleasesSource
from ai_news.sources.rss import RSSSource
from ai_news.storage.seen_items import SeenItemsDB, SeenRow

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    items_fetched: int
    items_rendered: int
    sources_failed: list[str]


def build_source(spec: SourceSpec, *, gh_token: str | None) -> Source:
    if spec.type == "rss":
        return RSSSource(name=spec.name, url=spec.url or "", weight=spec.weight)
    if spec.type == "github_releases":
        return GitHubReleasesSource(name=spec.name, repo=spec.repo or "",
                                    weight=spec.weight, token=gh_token)
    raise ValueError(f"unknown source type: {spec.type}")


def build_llm(cfg: Config) -> LLMProvider:
    primary = _build_provider(cfg.llm.provider, cfg.llm.model, cfg.llm.api_key)
    fb_provider = cfg.llm.fallback_provider
    fb_key = cfg.llm.fallback_api_key
    fb_model = cfg.llm.fallback_model
    if fb_provider and fb_key and fb_model:
        fallback = _build_provider(fb_provider, fb_model, fb_key)
        return FallbackLLM(primary=primary, fallback=fallback)
    return primary


def _build_provider(provider: str, model: str, api_key: str) -> LLMProvider:
    if provider == "openai":
        return OpenAICompatibleProvider.for_openai(api_key=api_key, model=model)
    if provider == "deepseek":
        return OpenAICompatibleProvider.for_deepseek(api_key=api_key, model=model)
    if provider == "claude":
        return ClaudeProvider(api_key=api_key, model=model)
    if provider == "gemini":
        return GeminiProvider(api_key=api_key, model=model)
    raise ValueError(f"unknown llm provider: {provider}")


def _subject_prefix(failed: list[str], rendered: int) -> str:
    if rendered == 0:
        return "[AI Daily ✗]"
    if failed:
        return "[AI Daily ⚠]"
    return "[AI Daily]"


def main(
    *,
    config_path: Path = Path("config.toml"),
    db_path: Path = Path("seen_items.sqlite"),
    llm: LLMProvider | None = None,
    mailer: Mailer | None = None,
    now: datetime | None = None,
    gh_token: str | None = None,
) -> RunResult:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = load_config(config_path)
    now = now or datetime.now(timezone.utc)
    llm = llm or build_llm(cfg)
    mailer = mailer or SMTPMailer(
        host=cfg.smtp.host, port=cfg.smtp.port,
        user=cfg.smtp.user, password=cfg.smtp.password,
    )
    gh_token = gh_token or os.environ.get("GH_TOKEN")

    db = SeenItemsDB(db_path)
    db.initialize()

    sources = [build_source(s, gh_token=gh_token) for s in cfg.sources]
    since = now - timedelta(hours=cfg.daily.lookback_hours)

    raw: list = []
    failed: list[str] = []
    for src in sources:
        try:
            items = src.fetch(since=since)
        except Exception as exc:
            logger.warning("source=%s raised %s", src.name, exc)
            failed.append(src.name)
            continue
        raw.extend(items)
    logger.info("fetch total=%d failed=%d", len(raw), len(failed))

    fresh = dedup_against_seen(raw, db=db)
    logger.info("dedup kept=%d", len(fresh))

    candidates = pre_filter(fresh, keywords=cfg.keywords,
                            top_n=cfg.daily.pre_filter_top_n)
    logger.info("pre_filter kept=%d", len(candidates))

    digests = summarize_batch(
        candidates, llm=llm,
        max_tokens=cfg.llm.max_output_tokens_daily,
    )
    logger.info("summarize produced=%d", len(digests))

    final = rank_and_dedup(
        digests, max_total=cfg.daily.final_max_items,
        per_category_cap=8, dup_threshold=85,
    )
    logger.info("rank final=%d", len(final))

    tz = ZoneInfo(cfg.general.timezone)
    date_str = now.astimezone(tz).strftime("%Y-%m-%d")
    prefix = _subject_prefix(failed, len(final))
    if len(final) == 0:
        subject = f"{prefix} {date_str} · 抓取异常"
    else:
        tail = f"{len(final)} 条 · {len({d.category for d in final})} 类"
        if failed:
            tail += f" · {len(failed)} 源失败"
        subject = f"{prefix} {date_str} · {tail}"
    fallback_banner = None
    if isinstance(llm, FallbackLLM) and llm.used_fallback:
        fallback_banner = (
            f"ℹ 本期由 fallback provider ({llm.fallback.name}) 生成"
        )
    banner_parts = [
        p for p in [
            fallback_banner,
            f"⚠ 以下信息源抓取失败：{', '.join(failed)}" if failed else None,
        ] if p
    ]
    banner = " · ".join(banner_parts) if banner_parts else None

    html = render_email(
        subject=subject,
        heading=f"每日 AI 要闻 · {date_str}",
        banner=banner,
        items=final,
        template="daily.html.j2",
        generated_at=now.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z"),
    )
    mailer.send(
        sender=cfg.smtp.user, to=cfg.general.recipient_email,
        subject=subject, html=html,
    )

    # Persist everything we summarized (not only final) so next run dedups fully.
    weekly_ids = set(weekly_candidate_ids(
        digests, threshold=cfg.weekly.weekly_candidate_threshold,
    ))
    rows = [
        SeenRow(
            id=d.raw.id, source=d.raw.source, url=d.raw.url, title=d.raw.title,
            cn_title=d.cn_title, cn_summary=d.cn_summary,
            category=d.category.value, score=d.score,
            weekly_candidate=(d.raw.id in weekly_ids),
        )
        for d in digests
    ]
    db.mark_seen(rows, now=now)
    db.purge_older_than(cutoff=now - timedelta(days=14))

    return RunResult(
        items_fetched=len(raw), items_rendered=len(final),
        sources_failed=failed,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("daily run failed")
        sys.exit(1)
