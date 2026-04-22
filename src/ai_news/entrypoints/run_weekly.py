"""Weekly digest entry point. Reuses content already summarized by daily runs."""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_news.config import load_config
from ai_news.delivery.smtp import Mailer, SMTPMailer
from ai_news.entrypoints.run_daily import RunResult, build_llm  # noqa: F401
from ai_news.llm.base import LLMProvider
from ai_news.models import Category, DigestItem, RawItem
from ai_news.pipeline.rank import rank_and_dedup
from ai_news.renderers.html_email import render_email
from ai_news.storage.seen_items import SeenItemsDB

logger = logging.getLogger(__name__)


def _digest_from_seen(row, *, published_at: datetime) -> DigestItem | None:
    """Reconstruct a DigestItem from stored SeenRow fields."""
    if not row.cn_title or not row.cn_summary or not row.category:
        return None
    try:
        cat = Category(row.category)
    except ValueError:
        cat = Category.OPINION
    raw = RawItem(
        id=row.id, source=row.source, title=row.title, url=row.url,
        published_at=published_at, raw_text=None, metadata={},
    )
    return DigestItem(
        raw=raw, cn_title=row.cn_title, cn_summary=row.cn_summary,
        category=cat, score=row.score,
    )


def main(
    *,
    config_path: Path = Path("config.toml"),
    db_path: Path = Path("seen_items.sqlite"),
    llm: LLMProvider | None = None,   # kept for parity; unused (no LLM needed for weekly)
    mailer: Mailer | None = None,
    now: datetime | None = None,
) -> RunResult:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cfg = load_config(config_path)
    now = now or datetime.now(timezone.utc)
    mailer = mailer or SMTPMailer(
        host=cfg.smtp.host, port=cfg.smtp.port,
        user=cfg.smtp.user, password=cfg.smtp.password,
    )
    _ = llm  # silence unused-var lint; weekly doesn't need LLM

    db = SeenItemsDB(db_path)
    db.initialize()

    since = now - timedelta(days=7)
    rows = db.weekly_candidates(since=since)
    logger.info("weekly candidates=%d", len(rows))

    digests = [d for d in (_digest_from_seen(r, published_at=now) for r in rows)
               if d is not None]
    final = rank_and_dedup(
        digests, max_total=30, per_category_cap=8, dup_threshold=85,
    )

    tz = ZoneInfo(cfg.general.timezone)
    date_str = now.astimezone(tz).strftime("%Y-%m-%d")
    subject = f"[AI Weekly] {date_str} · 本周 {len(final)} 条精选"
    html = render_email(
        subject=subject, heading=f"本周 AI 要闻 · {date_str}",
        banner=None, items=final, template="weekly.html.j2",
        generated_at=now.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z"),
    )
    mailer.send(
        sender=cfg.smtp.user, to=cfg.general.recipient_email,
        subject=subject, html=html,
    )
    return RunResult(
        items_fetched=len(rows), items_rendered=len(final), sources_failed=[],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("weekly run failed")
        sys.exit(1)
