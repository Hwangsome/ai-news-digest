"""GitHub Releases source."""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from ai_news.models import RawItem, stable_id

logger = logging.getLogger(__name__)


class GitHubReleasesSource:
    def __init__(self, *, name: str, repo: str, weight: float = 1.0,
                 token: str | None = None, timeout: float = 15.0) -> None:
        self.name = name
        self.repo = repo
        self.weight = weight
        self._token = token
        self._timeout = timeout

    def _fetch_json(self) -> list[dict]:
        headers = {"Accept": "application/vnd.github+json",
                   "User-Agent": "ai-news-digest/0.1"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        resp = httpx.get(
            f"https://api.github.com/repos/{self.repo}/releases",
            headers=headers, timeout=self._timeout, params={"per_page": 20},
        )
        resp.raise_for_status()
        return resp.json()

    def fetch(self, *, since: datetime) -> list[RawItem]:
        try:
            releases = self._fetch_json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("source=%s (github) fetch failed: %s", self.name, exc)
            return []

        items: list[RawItem] = []
        for r in releases:
            if r.get("draft") or r.get("prerelease"):
                continue
            pub_str = r.get("published_at") or ""
            try:
                published = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if published < since:
                continue
            url = r.get("html_url") or ""
            version = r.get("name") or r.get("tag_name") or ""
            items.append(RawItem(
                id=stable_id(source=self.name, url=url),
                source=self.name,
                title=f"{self.name} {version}".strip(),
                url=url,
                published_at=published,
                raw_text=(r.get("body") or "")[:4000],
                metadata={"weight": self.weight, "kind": "github_release"},
            ))
        return items
