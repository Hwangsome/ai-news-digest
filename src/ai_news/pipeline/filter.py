"""Rule-based pre-filter to keep LLM budget bounded."""
from __future__ import annotations

from ai_news.config import KeywordsCfg
from ai_news.models import RawItem


def score_item(item: RawItem, keywords: KeywordsCfg) -> float:
    text = f"{item.title}\n{item.raw_text or ''}".lower()

    score = float(item.metadata.get("weight", 1.0))
    for kw in keywords.high:
        if kw.lower() in text:
            score += 2.0
    for kw in keywords.medium:
        if kw.lower() in text:
            score += 1.0
    for kw in keywords.negative:
        if kw.lower() in text:
            score -= 3.0

    meta = item.metadata
    points = meta.get("points")
    if isinstance(points, int) and points >= 200:
        score += 1.0
    if meta.get("kind") == "github_release":
        score += 1.5

    return score


def pre_filter(items: list[RawItem], *, keywords: KeywordsCfg, top_n: int) -> list[RawItem]:
    scored = [(score_item(i, keywords), i) for i in items]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [i for _, i in scored[:top_n]]
