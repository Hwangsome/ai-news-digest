"""Deduplication against persistent seen-store and within a single batch."""
from __future__ import annotations

from ai_news.models import RawItem
from ai_news.storage.seen_items import SeenItemsDB


def dedup_within_batch(items: list[RawItem]) -> list[RawItem]:
    seen: set[str] = set()
    out: list[RawItem] = []
    for it in items:
        if it.id in seen:
            continue
        seen.add(it.id)
        out.append(it)
    return out


def dedup_against_seen(items: list[RawItem], *, db: SeenItemsDB) -> list[RawItem]:
    items = dedup_within_batch(items)
    if not items:
        return []
    known = db.has_many([it.id for it in items])
    return [it for it in items if it.id not in known]
