"""Generic RSS/Atom source via feedparser."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx

from ai_news.models import RawItem, stable_id

logger = logging.getLogger(__name__)


class RSSSource:
    def __init__(
        self,
        *,
        name: str,
        url: str,
        weight: float = 1.0,
        timeout: float = 15.0,
    ) -> None:
        self.name = name
        self.url = url
        self.weight = weight
        self._timeout = timeout

    def _fetch_bytes(self) -> bytes:
        resp = httpx.get(
            self.url,
            timeout=self._timeout,
            headers={"User-Agent": "ai-news-digest/0.1"},
        )
        resp.raise_for_status()
        return resp.content

    def fetch(self, *, since: datetime) -> list[RawItem]:
        try:
            data = self._fetch_bytes()
        except httpx.HTTPError as exc:
            logger.warning("source=%s fetch failed: %s", self.name, exc)
            return []

        feed = feedparser.parse(data)
        items: list[RawItem] = []
        for e in feed.entries:
            published = _entry_time(e)
            if published is None or published < since:
                continue
            url = getattr(e, "link", "") or ""
            if not url:
                continue
            summary = getattr(e, "summary", None) or getattr(e, "description", None)
            items.append(RawItem(
                id=stable_id(source=self.name, url=url),
                source=self.name,
                title=(getattr(e, "title", "") or "").strip(),
                url=url,
                published_at=published,
                raw_text=summary,
                metadata={"weight": self.weight},
            ))
        return items


def _entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None)
        if t:
            return datetime.fromtimestamp(mktime(t), tz=timezone.utc)
    return None
