"""Ranking, near-duplicate suppression, per-category caps."""
from __future__ import annotations

from collections import Counter

from rapidfuzz import fuzz

from ai_news.models import DigestItem


def _near_dup(title_a: str, title_b: str, threshold: int) -> bool:
    # Gate on token overlap so titles like "title 1" / "title 2" — which
    # share one common token but differ in the distinguishing one — are not
    # treated as duplicates just because rapidfuzz's character-level ratio
    # puts them marginally over the threshold.
    a_tokens = set(title_a.lower().split())
    b_tokens = set(title_b.lower().split())
    if a_tokens and b_tokens:
        jaccard = len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
        if jaccard < 0.5:
            return False
    return fuzz.token_set_ratio(title_a, title_b) >= threshold


def rank_and_dedup(
    items: list[DigestItem],
    *,
    max_total: int,
    per_category_cap: int,
    dup_threshold: int = 85,
) -> list[DigestItem]:
    ordered = sorted(items, key=lambda d: d.score, reverse=True)
    kept: list[DigestItem] = []
    per_cat: Counter = Counter()
    for d in ordered:
        if len(kept) >= max_total:
            break
        if per_cat[d.category] >= per_category_cap:
            continue
        if any(_near_dup(d.raw.title, k.raw.title, dup_threshold) for k in kept):
            continue
        kept.append(d)
        per_cat[d.category] += 1
    return kept


def weekly_candidate_ids(items: list[DigestItem], *, threshold: float) -> list[str]:
    return [d.raw.id for d in items if d.score >= threshold]
