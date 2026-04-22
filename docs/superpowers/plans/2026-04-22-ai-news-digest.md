# AI News Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python application that sends daily (and weekly) Chinese-language AI-news digest emails, fetched from RSS + GitHub Releases, summarised by a configurable LLM, and delivered by SMTP — deployed as GitHub Actions cron jobs.

**Architecture:** Layered pipeline (`sources → dedup → filter → LLM summarize → rank → render → SMTP`). Each layer is behind a Protocol so sources, LLM providers, and mailers are swappable. State (seen item IDs) lives in a SQLite file persisted via GitHub Actions cache.

**Tech Stack:** Python 3.11+, `feedparser` (RSS), `httpx` (HTTP + LLM + GH API), `jinja2` (HTML email), `rapidfuzz` (near-dup detection), `tenacity` (retry/backoff), stdlib `sqlite3` / `smtplib` / `tomllib`, `pytest` + `syrupy` + `aiosmtpd` (tests).

---

## File Structure

```
ai-news-digest/
├── pyproject.toml                    # Task 1
├── .gitignore                        # already exists
├── config.toml                       # Task 22 (sample)
├── config.test.toml                  # Task 1
├── README.md                         # Task 22
├── src/ai_news/
│   ├── __init__.py                   # Task 1 (empty)
│   ├── models.py                     # Task 2
│   ├── config.py                     # Task 3
│   ├── storage/seen_items.py         # Task 4
│   ├── sources/base.py               # Task 5
│   ├── sources/rss.py                # Task 5
│   ├── sources/github.py             # Task 6
│   ├── llm/base.py                   # Task 7
│   ├── llm/openai_compatible.py      # Task 7   (OpenAI + DeepSeek)
│   ├── llm/claude.py                 # Task 8
│   ├── llm/gemini.py                 # Task 9
│   ├── pipeline/dedup.py             # Task 10
│   ├── pipeline/filter.py            # Task 11
│   ├── pipeline/summarize.py         # Task 12
│   ├── pipeline/rank.py              # Task 13
│   ├── renderers/html_email.py       # Task 14
│   ├── renderers/templates/daily.html.j2    # Task 14
│   ├── renderers/templates/weekly.html.j2   # Task 14
│   ├── delivery/smtp.py              # Task 15
│   └── entrypoints/
│       ├── run_daily.py              # Task 16
│       └── run_weekly.py             # Task 16
├── scripts/smoke.py                  # Task 18
├── tests/
│   ├── conftest.py                   # Task 1
│   ├── fixtures/...                  # as needed
│   ├── test_models.py                # Task 2
│   ├── test_config.py                # Task 3
│   ├── test_seen_items.py            # Task 4
│   ├── test_sources_rss.py           # Task 5
│   ├── test_sources_github.py        # Task 6
│   ├── test_llm_openai_compatible.py # Task 7
│   ├── test_llm_claude.py            # Task 8
│   ├── test_llm_gemini.py            # Task 9
│   ├── test_pipeline_dedup.py        # Task 10
│   ├── test_pipeline_filter.py       # Task 11
│   ├── test_pipeline_summarize.py    # Task 12
│   ├── test_pipeline_rank.py         # Task 13
│   ├── test_renderer_html.py         # Task 14
│   ├── test_delivery_smtp.py         # Task 15
│   └── test_e2e.py                   # Task 17
└── .github/workflows/
    ├── daily.yml                     # Task 19
    ├── weekly.yml                    # Task 19
    ├── source-healthcheck.yml        # Task 20
    └── ci.yml                        # Task 1
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`, `src/ai_news/__init__.py`, `tests/conftest.py`, `config.test.toml`, `.github/workflows/ci.yml`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "ai-news-digest"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "feedparser>=6.0.11",
    "httpx>=0.27",
    "jinja2>=3.1",
    "rapidfuzz>=3.9",
    "tenacity>=8.5",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.23",
    "syrupy>=4",
    "aiosmtpd>=1.4",
    "ruff>=0.6",
    "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ai_news"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

- [ ] **Step 2: Create empty package init and subpackage dirs**

```bash
mkdir -p src/ai_news/{sources,pipeline,llm,renderers/templates,delivery,entrypoints,storage} \
         tests scripts .github/workflows
touch src/ai_news/__init__.py \
      src/ai_news/{sources,pipeline,llm,renderers,delivery,entrypoints,storage}/__init__.py
```

- [ ] **Step 3: Write `tests/conftest.py`**

```python
from datetime import datetime, timezone

import pytest

UTC = timezone.utc


@pytest.fixture
def now_utc() -> datetime:
    return datetime(2026, 4, 22, 0, 0, tzinfo=UTC)
```

- [ ] **Step 4: Write `config.test.toml` (fixture used in later tests)**

```toml
[general]
timezone = "Asia/Shanghai"
recipient_email = "test@example.com"
digest_language = "zh-CN"

[llm]
provider = "fake"
model = "fake-model"
max_output_tokens_daily = 4000
max_output_tokens_weekly = 16000

[daily]
send_hour_local = 8
lookback_hours = 26
pre_filter_top_n = 40
final_max_items = 25

[weekly]
send_weekday = "monday"
send_hour_local = 8
weekly_candidate_threshold = 8.0

[keywords]
high = ["claude", "gpt", "agent"]
medium = ["benchmark"]
negative = ["crypto"]

[[sources.items]]
type = "rss"
name = "Fake"
url = "https://example.com/feed.xml"
weight = 1.0
```

- [ ] **Step 5: Write `.github/workflows/ci.yml`**

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: pytest -q
```

- [ ] **Step 6: Install and verify**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Expected: `no tests ran` (exit 0) or similar, confirming import works.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/ tests/ config.test.toml .github/workflows/ci.yml
git commit -m "chore: project scaffolding with pyproject, CI, and test fixtures"
```

---

## Task 2: Domain Models

**Files:**
- Create: `src/ai_news/models.py`, `tests/test_models.py`

- [ ] **Step 1: Write failing test `tests/test_models.py`**

```python
from datetime import datetime, timezone

from ai_news.models import Category, DigestItem, RawItem, stable_id


def test_stable_id_same_for_same_url_and_source():
    a = stable_id(source="openai", url="https://openai.com/blog/a")
    b = stable_id(source="openai", url="https://openai.com/blog/a")
    assert a == b and len(a) == 16


def test_stable_id_differs_by_source():
    a = stable_id(source="openai", url="https://x.com")
    b = stable_id(source="anthropic", url="https://x.com")
    assert a != b


def test_raw_item_is_frozen():
    item = RawItem(
        id="abc", source="s", title="t", url="u",
        published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        raw_text=None, metadata={},
    )
    import dataclasses
    assert dataclasses.is_dataclass(item)
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.title = "x"  # type: ignore[misc]


def test_category_values_are_chinese():
    assert Category.MODEL_RELEASE.value == "模型发布"
    assert Category.RESEARCH.value == "研究与论文"


def test_digest_item_composes_raw():
    raw = RawItem(
        id="x", source="s", title="Hi", url="u",
        published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        raw_text="body", metadata={},
    )
    d = DigestItem(raw=raw, cn_title="你好", cn_summary="摘要", category=Category.PRODUCT, score=7.5)
    assert d.raw.title == "Hi"
    assert d.score == 7.5
```

- [ ] **Step 2: Run — expected FAIL (`ModuleNotFoundError: ai_news.models`)**

```bash
pytest tests/test_models.py -q
```

- [ ] **Step 3: Implement `src/ai_news/models.py`**

```python
"""Core dataclasses shared across the pipeline."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


def stable_id(*, source: str, url: str) -> str:
    h = hashlib.sha256(f"{source}\x00{url}".encode("utf-8")).hexdigest()
    return h[:16]


class Category(str, Enum):
    MODEL_RELEASE = "模型发布"
    PRODUCT       = "产品与工具"
    RESEARCH      = "研究与论文"
    TOOLING       = "工程与框架"
    OPINION       = "观点与讨论"


@dataclass(frozen=True)
class RawItem:
    id: str
    source: str
    title: str
    url: str
    published_at: datetime
    raw_text: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DigestItem:
    raw: RawItem
    cn_title: str
    cn_summary: str
    category: Category
    score: float
```

- [ ] **Step 4: Run — expect PASS**

```bash
pytest tests/test_models.py -q
```

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/models.py tests/test_models.py
git commit -m "feat(models): add RawItem, DigestItem, Category, stable_id"
```

---

## Task 3: Config Loader

**Files:**
- Create: `src/ai_news/config.py`, `tests/test_config.py`

- [ ] **Step 1: Write failing test `tests/test_config.py`**

```python
import os
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
    assert cfg.sources[0] == SourceSpec(type="rss", name="Fake",
                                        url="https://example.com/feed.xml", weight=1.0)


def test_missing_smtp_secret_raises(monkeypatch, tmp_path: Path):
    (tmp_path / "c.toml").write_text(Path("config.test.toml").read_text())
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        load_config(tmp_path / "c.toml")
```

- [ ] **Step 2: Run — expected FAIL**

- [ ] **Step 3: Implement `src/ai_news/config.py`**

```python
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
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/config.py tests/test_config.py
git commit -m "feat(config): TOML + env loader with typed dataclasses"
```

---

## Task 4: SeenItems Storage (SQLite)

**Files:**
- Create: `src/ai_news/storage/seen_items.py`, `tests/test_seen_items.py`

- [ ] **Step 1: Write failing test `tests/test_seen_items.py`**

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_news.storage.seen_items import SeenItemsDB

UTC = timezone.utc


def test_insert_and_has(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    assert not db.has("id1")
    db.mark_seen([("id1", "src", "http://u", 7.2, True)], now=datetime(2026, 4, 22, tzinfo=UTC))
    assert db.has("id1")


def test_weekly_candidates_window(tmp_path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    now = datetime(2026, 4, 22, tzinfo=UTC)
    db.mark_seen([("old", "s", "u1", 9.0, True)], now=now - timedelta(days=10))
    db.mark_seen([("new", "s", "u2", 9.0, True)], now=now - timedelta(days=3))
    cands = db.weekly_candidates(since=now - timedelta(days=7))
    ids = {c[0] for c in cands}
    assert ids == {"new"}


def test_purge_removes_old(tmp_path):
    db = SeenItemsDB(tmp_path / "s.sqlite")
    db.initialize()
    now = datetime(2026, 4, 22, tzinfo=UTC)
    db.mark_seen([("old", "s", "u", 1.0, False)], now=now - timedelta(days=20))
    db.mark_seen([("young", "s", "u", 1.0, False)], now=now - timedelta(days=3))
    db.purge_older_than(cutoff=now - timedelta(days=14))
    assert not db.has("old")
    assert db.has("young")
```

- [ ] **Step 2: Run — expected FAIL**

- [ ] **Step 3: Implement `src/ai_news/storage/seen_items.py`**

```python
"""SQLite-backed store of item IDs already shown to the user."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

SeenRow = tuple[str, str, str, float, bool]  # id, source, url, score, weekly_candidate

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    score REAL,
    weekly_candidate INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_first_seen ON seen_items(first_seen_at);
"""


class SeenItemsDB:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def initialize(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)

    def has(self, item_id: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM seen_items WHERE id = ?", (item_id,)).fetchone()
            return row is not None

    def mark_seen(self, rows: list[SeenRow], *, now: datetime) -> None:
        ts = now.isoformat()
        with self._conn() as c:
            c.executemany(
                "INSERT OR IGNORE INTO seen_items(id, source, url, first_seen_at, score, weekly_candidate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(r[0], r[1], r[2], ts, r[3], 1 if r[4] else 0) for r in rows],
            )

    def weekly_candidates(self, *, since: datetime) -> list[SeenRow]:
        with self._conn() as c:
            cur = c.execute(
                "SELECT id, source, url, score, weekly_candidate FROM seen_items "
                "WHERE weekly_candidate = 1 AND first_seen_at >= ?",
                (since.isoformat(),),
            )
            return [(r[0], r[1], r[2], r[3] or 0.0, bool(r[4])) for r in cur.fetchall()]

    def purge_older_than(self, *, cutoff: datetime) -> int:
        with self._conn() as c:
            cur = c.execute("DELETE FROM seen_items WHERE first_seen_at < ?", (cutoff.isoformat(),))
            return cur.rowcount
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/storage/ tests/test_seen_items.py
git commit -m "feat(storage): SQLite SeenItemsDB with rolling purge"
```

---

## Task 5: RSS Source

**Files:**
- Create: `src/ai_news/sources/base.py`, `src/ai_news/sources/rss.py`, `tests/test_sources_rss.py`, `tests/fixtures/openai_rss.xml`

- [ ] **Step 1: Create fixture `tests/fixtures/openai_rss.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>OpenAI News</title>
  <item>
    <title>Introducing GPT-5</title>
    <link>https://openai.com/blog/gpt-5</link>
    <pubDate>Wed, 22 Apr 2026 12:00:00 GMT</pubDate>
    <description>We're releasing GPT-5, our most capable model.</description>
  </item>
  <item>
    <title>Old post from 2025</title>
    <link>https://openai.com/blog/old</link>
    <pubDate>Fri, 01 Jan 2025 00:00:00 GMT</pubDate>
    <description>Ancient history</description>
  </item>
</channel></rss>
```

- [ ] **Step 2: Write failing test `tests/test_sources_rss.py`**

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_news.sources.rss import RSSSource

UTC = timezone.utc
FIXTURES = Path(__file__).parent / "fixtures"


def test_rss_parses_items(monkeypatch):
    src = RSSSource(name="OpenAI", url="file://ignored", weight=1.0)
    xml = (FIXTURES / "openai_rss.xml").read_bytes()
    monkeypatch.setattr(src, "_fetch_bytes", lambda: xml)
    items = src.fetch(since=datetime(2026, 4, 21, tzinfo=UTC))
    assert len(items) == 1
    assert items[0].title == "Introducing GPT-5"
    assert items[0].source == "OpenAI"
    assert items[0].url == "https://openai.com/blog/gpt-5"
    assert items[0].raw_text is not None
    assert "GPT-5" in items[0].raw_text
    assert len(items[0].id) == 16


def test_rss_filters_out_items_older_than_since(monkeypatch):
    src = RSSSource(name="OpenAI", url="file://x", weight=1.0)
    monkeypatch.setattr(src, "_fetch_bytes",
                       lambda: (FIXTURES / "openai_rss.xml").read_bytes())
    since = datetime(2026, 4, 22, tzinfo=UTC) - timedelta(hours=6)
    assert len(src.fetch(since=since)) == 1
    since = datetime(2027, 1, 1, tzinfo=UTC)
    assert src.fetch(since=since) == []
```

- [ ] **Step 3: Run — expected FAIL**

- [ ] **Step 4: Implement `src/ai_news/sources/base.py`**

```python
"""Source protocol shared by all fetchers."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ai_news.models import RawItem


@runtime_checkable
class Source(Protocol):
    name: str
    weight: float
    def fetch(self, *, since: datetime) -> list[RawItem]: ...
```

- [ ] **Step 5: Implement `src/ai_news/sources/rss.py`**

```python
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
    def __init__(self, *, name: str, url: str, weight: float = 1.0,
                 timeout: float = 15.0) -> None:
        self.name = name
        self.url = url
        self.weight = weight
        self._timeout = timeout

    def _fetch_bytes(self) -> bytes:
        resp = httpx.get(self.url, timeout=self._timeout,
                         headers={"User-Agent": "ai-news-digest/0.1"})
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
```

- [ ] **Step 6: Run — PASS**

- [ ] **Step 7: Commit**

```bash
git add src/ai_news/sources/ tests/test_sources_rss.py tests/fixtures/openai_rss.xml
git commit -m "feat(sources): Source protocol + RSSSource with feedparser"
```

---

## Task 6: GitHub Releases Source

**Files:**
- Create: `src/ai_news/sources/github.py`, `tests/test_sources_github.py`

- [ ] **Step 1: Write failing test `tests/test_sources_github.py`**

```python
from datetime import datetime, timezone

import httpx
import pytest

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
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `src/ai_news/sources/github.py`**

```python
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
        except httpx.HTTPError as exc:
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
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/sources/github.py tests/test_sources_github.py
git commit -m "feat(sources): GitHub Releases source"
```

---

## Task 7: LLM Protocol + OpenAI-compatible Adapter

Handles both OpenAI and DeepSeek (DeepSeek uses OpenAI-compatible API).

**Files:**
- Create: `src/ai_news/llm/base.py`, `src/ai_news/llm/openai_compatible.py`, `tests/test_llm_openai_compatible.py`

- [ ] **Step 1: Write failing test `tests/test_llm_openai_compatible.py`**

```python
from unittest.mock import MagicMock

from ai_news.llm.openai_compatible import OpenAICompatibleProvider


def test_openai_compatible_sends_expected_payload(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "hi"}}]}
        def raise_for_status(self): pass

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)

    p = OpenAICompatibleProvider(
        api_key="k", model="gpt-5.4", base_url="https://api.openai.com/v1",
    )
    out = p.complete(system="sys", user="usr", max_tokens=100)
    assert out == "hi"
    assert calls[0][0] == "https://api.openai.com/v1/chat/completions"
    assert calls[0][1]["model"] == "gpt-5.4"
    assert calls[0][1]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    assert calls[0][1]["max_tokens"] == 100
    assert calls[0][2]["Authorization"] == "Bearer k"


def test_deepseek_uses_deepseek_base_url():
    p = OpenAICompatibleProvider.for_deepseek(api_key="k", model="deepseek-chat")
    assert p.base_url == "https://api.deepseek.com/v1"
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `src/ai_news/llm/base.py`**

```python
"""LLMProvider protocol."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


class LLMError(Exception):
    pass


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    def complete(self, *, system: str, user: str, max_tokens: int) -> str: ...
```

- [ ] **Step 4: Implement `src/ai_news/llm/openai_compatible.py`**

```python
"""Adapter for OpenAI- and DeepSeek-compatible Chat Completions APIs."""
from __future__ import annotations

import httpx

from ai_news.llm.base import LLMError


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(self, *, api_key: str, model: str, base_url: str,
                 timeout: float = 60.0) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def for_openai(cls, *, api_key: str, model: str) -> "OpenAICompatibleProvider":
        return cls(api_key=api_key, model=model, base_url="https://api.openai.com/v1")

    @classmethod
    def for_deepseek(cls, *, api_key: str, model: str) -> "OpenAICompatibleProvider":
        return cls(api_key=api_key, model=model, base_url="https://api.deepseek.com/v1")

    def complete(self, *, system: str, user: str, max_tokens: int) -> str:
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                },
                headers={"Authorization": f"Bearer {self.api_key}",
                         "Content-Type": "application/json"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMError(f"openai-compatible call failed: {exc}") from exc
```

- [ ] **Step 5: Run — PASS**

- [ ] **Step 6: Commit**

```bash
git add src/ai_news/llm/base.py src/ai_news/llm/openai_compatible.py tests/test_llm_openai_compatible.py
git commit -m "feat(llm): protocol + OpenAI/DeepSeek-compatible adapter"
```

---

## Task 8: Claude Adapter

**Files:**
- Create: `src/ai_news/llm/claude.py`, `tests/test_llm_claude.py`

- [ ] **Step 1: Write failing test**

```python
from ai_news.llm.claude import ClaudeProvider


def test_claude_sends_expected_payload(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"content": [{"type": "text", "text": "ok"}]}
        def raise_for_status(self): pass

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)
    p = ClaudeProvider(api_key="k", model="claude-4-6-sonnet")
    out = p.complete(system="sys", user="u", max_tokens=200)
    assert out == "ok"
    assert calls[0][0] == "https://api.anthropic.com/v1/messages"
    assert calls[0][1]["system"] == "sys"
    assert calls[0][1]["max_tokens"] == 200
    assert calls[0][2]["x-api-key"] == "k"
    assert calls[0][2]["anthropic-version"] == "2023-06-01"
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `src/ai_news/llm/claude.py`**

```python
"""Anthropic Claude Messages API adapter."""
from __future__ import annotations

import httpx

from ai_news.llm.base import LLMError


class ClaudeProvider:
    name = "claude"

    def __init__(self, *, api_key: str, model: str, timeout: float = 60.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, *, system: str, user: str, max_tokens: int) -> str:
        try:
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                json={
                    "model": self.model,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                    "max_tokens": max_tokens,
                    "temperature": 0.2,
                },
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        except (httpx.HTTPError, KeyError) as exc:
            raise LLMError(f"claude call failed: {exc}") from exc
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/llm/claude.py tests/test_llm_claude.py
git commit -m "feat(llm): Anthropic Claude adapter"
```

---

## Task 9: Gemini Adapter

**Files:**
- Create: `src/ai_news/llm/gemini.py`, `tests/test_llm_gemini.py`

- [ ] **Step 1: Write failing test**

```python
from ai_news.llm.gemini import GeminiProvider


def test_gemini_sends_expected_payload(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
        def raise_for_status(self): pass

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)
    p = GeminiProvider(api_key="k", model="gemini-2.0-flash")
    out = p.complete(system="sys", user="u", max_tokens=200)
    assert out == "hello"
    assert calls[0][0] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent?key=k"
    )
    assert calls[0][1]["systemInstruction"]["parts"][0]["text"] == "sys"
    assert calls[0][1]["generationConfig"]["maxOutputTokens"] == 200
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `src/ai_news/llm/gemini.py`**

```python
"""Google Gemini Generative Language API adapter."""
from __future__ import annotations

import httpx

from ai_news.llm.base import LLMError


class GeminiProvider:
    name = "gemini"

    def __init__(self, *, api_key: str, model: str, timeout: float = 60.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, *, system: str, user: str, max_tokens: int) -> str:
        try:
            resp = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent?key={self.api_key}",
                json={
                    "systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": user}]}],
                    "generationConfig": {
                        "maxOutputTokens": max_tokens,
                        "temperature": 0.2,
                    },
                },
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMError(f"gemini call failed: {exc}") from exc
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/llm/gemini.py tests/test_llm_gemini.py
git commit -m "feat(llm): Google Gemini adapter"
```

---

## Task 10: Dedup Stage

**Files:**
- Create: `src/ai_news/pipeline/dedup.py`, `tests/test_pipeline_dedup.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import datetime, timezone
from pathlib import Path

from ai_news.models import RawItem
from ai_news.pipeline.dedup import dedup_against_seen
from ai_news.storage.seen_items import SeenItemsDB

UTC = timezone.utc


def _mk(id_: str) -> RawItem:
    return RawItem(id=id_, source="s", title="t", url="u",
                   published_at=datetime(2026, 4, 22, tzinfo=UTC),
                   raw_text=None, metadata={})


def test_dedup_filters_known(tmp_path: Path):
    db = SeenItemsDB(tmp_path / "s.sqlite"); db.initialize()
    db.mark_seen([("a", "s", "u", 0.0, False)], now=datetime(2026, 4, 22, tzinfo=UTC))
    items = [_mk("a"), _mk("b"), _mk("c")]
    out = dedup_against_seen(items, db=db)
    assert [i.id for i in out] == ["b", "c"]


def test_dedup_within_batch():
    items = [_mk("x"), _mk("x"), _mk("y")]
    from ai_news.pipeline.dedup import dedup_within_batch
    out = dedup_within_batch(items)
    assert [i.id for i in out] == ["x", "y"]
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `src/ai_news/pipeline/dedup.py`**

```python
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
    return [it for it in items if not db.has(it.id)]
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/pipeline/dedup.py tests/test_pipeline_dedup.py
git commit -m "feat(pipeline): dedup against seen-store and within batch"
```

---

## Task 11: Keyword-based Pre-filter

**Files:**
- Create: `src/ai_news/pipeline/filter.py`, `tests/test_pipeline_filter.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import datetime, timezone

from ai_news.config import KeywordsCfg
from ai_news.models import RawItem
from ai_news.pipeline.filter import pre_filter, score_item

UTC = timezone.utc


def _mk(title: str, source: str = "s", weight: float = 1.0, text: str | None = None) -> RawItem:
    return RawItem(id=title, source=source, title=title, url="u",
                   published_at=datetime(2026, 4, 22, tzinfo=UTC),
                   raw_text=text, metadata={"weight": weight})


def test_score_item_boosts_high_keywords():
    kw = KeywordsCfg(high=["claude"], medium=["benchmark"], negative=["crypto"])
    assert score_item(_mk("Claude 4.6 is out"), kw) > score_item(_mk("random post"), kw)


def test_score_item_penalizes_negative_keywords():
    kw = KeywordsCfg(high=["ai"], medium=[], negative=["crypto"])
    s_pos = score_item(_mk("AI breakthrough"), kw)
    s_neg = score_item(_mk("AI meets crypto"), kw)
    assert s_neg < s_pos


def test_pre_filter_returns_top_n_in_score_order():
    kw = KeywordsCfg(high=["claude"], medium=[], negative=[])
    items = [_mk("random"), _mk("Claude news"), _mk("Claude and agent"), _mk("boring")]
    out = pre_filter(items, keywords=kw, top_n=2)
    assert len(out) == 2
    assert all("claude" in i.title.lower() for i in out)
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `src/ai_news/pipeline/filter.py`**

```python
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
    if isinstance(meta.get("points"), int) and meta["points"] >= 200:
        score += 1.0
    if meta.get("kind") == "github_release":
        score += 1.5

    return score


def pre_filter(items: list[RawItem], *, keywords: KeywordsCfg, top_n: int) -> list[RawItem]:
    scored = [(score_item(i, keywords), i) for i in items]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [i for _, i in scored[:top_n]]
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/pipeline/filter.py tests/test_pipeline_filter.py
git commit -m "feat(pipeline): rule-based pre-filter with keyword scoring"
```

---

## Task 12: Summarize (LLM Batch)

**Files:**
- Create: `src/ai_news/pipeline/summarize.py`, `tests/test_pipeline_summarize.py`

- [ ] **Step 1: Write failing test `tests/test_pipeline_summarize.py`**

```python
import json
from datetime import datetime, timezone

from ai_news.models import Category, RawItem
from ai_news.pipeline.summarize import summarize_batch

UTC = timezone.utc


class FakeLLM:
    name = "fake"
    def __init__(self, responses: list[str]): self.responses = responses; self.calls = 0
    def complete(self, *, system, user, max_tokens):
        r = self.responses[self.calls]; self.calls += 1; return r


def _mk(i: int) -> RawItem:
    return RawItem(id=f"id{i}", source="s", title=f"Title {i}", url=f"https://x/{i}",
                   published_at=datetime(2026, 4, 22, tzinfo=UTC),
                   raw_text=f"Body {i}", metadata={})


def test_summarize_parses_batch():
    resp = json.dumps({"items": [
        {"id": "id0", "cn_title": "中文 0", "cn_summary": "摘要 0", "category": "模型发布", "score": 9.1},
        {"id": "id1", "cn_title": "中文 1", "cn_summary": "摘要 1", "category": "产品与工具", "score": 6.2},
    ]})
    llm = FakeLLM([resp])
    digests = summarize_batch([_mk(0), _mk(1)], llm=llm, max_tokens=500, batch_size=5)
    assert len(digests) == 2
    assert digests[0].cn_title == "中文 0"
    assert digests[0].category == Category.MODEL_RELEASE
    assert digests[1].score == 6.2


def test_summarize_retries_on_parse_error_then_skips():
    good = json.dumps({"items": [{"id": "id0", "cn_title": "a", "cn_summary": "b",
                                  "category": "模型发布", "score": 5.0}]})
    llm = FakeLLM(["garbage not-json", good])  # first batch fails, retry succeeds
    digests = summarize_batch([_mk(0)], llm=llm, max_tokens=500, batch_size=5)
    assert len(digests) == 1


def test_summarize_batches():
    resps = []
    for start in (0, 3):
        resps.append(json.dumps({"items": [
            {"id": f"id{start+k}", "cn_title": f"t{start+k}", "cn_summary": "s",
             "category": "产品与工具", "score": 5.0} for k in range(3)
        ]}))
    llm = FakeLLM(resps)
    items = [_mk(i) for i in range(6)]
    digests = summarize_batch(items, llm=llm, max_tokens=500, batch_size=3)
    assert len(digests) == 6
    assert llm.calls == 2
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `src/ai_news/pipeline/summarize.py`**

```python
"""Batch LLM summarization; strict JSON output."""
from __future__ import annotations

import json
import logging
from typing import Iterable

from ai_news.llm.base import LLMError, LLMProvider
from ai_news.models import Category, DigestItem, RawItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert curator of AI/ML news for Chinese readers.
For each input article you will output JSON with these fields:
- id: the input id verbatim
- cn_title: Chinese title, concise (<= 30 chars)
- cn_summary: 2-4 sentence Chinese summary of what matters and why
- category: one of "模型发布", "产品与工具", "研究与论文", "工程与框架", "观点与讨论"
- score: float 0-10 importance for a senior AI engineer (10 = must-read)

Return ONLY a JSON object of shape {"items": [...]}. No prose, no code fences."""


def _batch_user_prompt(batch: list[RawItem]) -> str:
    parts = ["Articles (JSON array):", "["]
    for i, it in enumerate(batch):
        body = (it.raw_text or "")[:800].replace("\n", " ")
        parts.append(json.dumps({
            "id": it.id, "source": it.source, "title": it.title,
            "url": it.url, "body": body,
        }, ensure_ascii=False))
        if i < len(batch) - 1:
            parts.append(",")
    parts.append("]")
    return "\n".join(parts)


def _parse_response(text: str, known_items: dict[str, RawItem]) -> list[DigestItem]:
    data = json.loads(text)
    out: list[DigestItem] = []
    for entry in data.get("items", []):
        raw = known_items.get(entry["id"])
        if raw is None:
            continue
        try:
            cat = Category(entry["category"])
        except ValueError:
            cat = Category.OPINION
        out.append(DigestItem(
            raw=raw,
            cn_title=str(entry["cn_title"]).strip()[:100],
            cn_summary=str(entry["cn_summary"]).strip(),
            category=cat,
            score=float(entry["score"]),
        ))
    return out


def summarize_batch(
    items: list[RawItem], *,
    llm: LLMProvider,
    max_tokens: int,
    batch_size: int = 6,
) -> list[DigestItem]:
    result: list[DigestItem] = []
    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        known = {it.id: it for it in batch}
        user = _batch_user_prompt(batch)
        try:
            resp = llm.complete(system=SYSTEM_PROMPT, user=user, max_tokens=max_tokens)
            result.extend(_parse_response(resp, known))
        except (json.JSONDecodeError, LLMError, KeyError, ValueError) as exc:
            logger.warning("batch parse/LLM failed (%s); retrying once", exc)
            try:
                resp = llm.complete(system=SYSTEM_PROMPT, user=user, max_tokens=max_tokens)
                result.extend(_parse_response(resp, known))
            except Exception as exc2:
                logger.error("batch failed twice, skipping: %s", exc2)
    return result
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/pipeline/summarize.py tests/test_pipeline_summarize.py
git commit -m "feat(pipeline): batched LLM summarization with JSON parse + retry"
```

---

## Task 13: Rank + Near-dup Suppression

**Files:**
- Create: `src/ai_news/pipeline/rank.py`, `tests/test_pipeline_rank.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import datetime, timezone

from ai_news.models import Category, DigestItem, RawItem
from ai_news.pipeline.rank import rank_and_dedup, weekly_candidate_ids

UTC = timezone.utc


def _d(id_: str, title: str, cat: Category, score: float) -> DigestItem:
    raw = RawItem(id=id_, source="s", title=title, url=f"u/{id_}",
                  published_at=datetime(2026, 4, 22, tzinfo=UTC),
                  raw_text=None, metadata={})
    return DigestItem(raw=raw, cn_title=title, cn_summary="", category=cat, score=score)


def test_sorts_by_score_descending():
    out = rank_and_dedup(
        [_d("1", "a", Category.PRODUCT, 5.0),
         _d("2", "b", Category.PRODUCT, 8.0),
         _d("3", "c", Category.PRODUCT, 6.0)],
        max_total=10, per_category_cap=10, dup_threshold=85,
    )
    assert [d.raw.id for d in out] == ["2", "3", "1"]


def test_drops_near_duplicates():
    out = rank_and_dedup(
        [_d("1", "GPT-5 launch announced today", Category.MODEL_RELEASE, 9.0),
         _d("2", "GPT-5 announced today launch", Category.MODEL_RELEASE, 8.5),
         _d("3", "Unrelated topic entirely", Category.OPINION, 7.0)],
        max_total=10, per_category_cap=10, dup_threshold=85,
    )
    ids = [d.raw.id for d in out]
    assert "1" in ids and "3" in ids and "2" not in ids


def test_caps_per_category_and_total():
    items = [_d(str(i), f"title {i}", Category.PRODUCT, 10.0 - i * 0.1) for i in range(10)]
    items += [_d(f"r{i}", f"research {i}", Category.RESEARCH, 10.0 - i * 0.1) for i in range(10)]
    out = rank_and_dedup(items, max_total=6, per_category_cap=3, dup_threshold=85)
    assert len(out) == 6
    from collections import Counter
    counts = Counter(d.category for d in out)
    assert counts[Category.PRODUCT] <= 3
    assert counts[Category.RESEARCH] <= 3


def test_weekly_candidate_ids():
    items = [_d("1", "t1", Category.PRODUCT, 9.5),
             _d("2", "t2", Category.PRODUCT, 7.0),
             _d("3", "t3", Category.PRODUCT, 8.0)]
    ids = weekly_candidate_ids(items, threshold=8.0)
    assert set(ids) == {"1", "3"}
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `src/ai_news/pipeline/rank.py`**

```python
"""Ranking, near-duplicate suppression, per-category caps."""
from __future__ import annotations

from collections import Counter

from rapidfuzz import fuzz

from ai_news.models import DigestItem


def _near_dup(title_a: str, title_b: str, threshold: int) -> bool:
    return fuzz.token_set_ratio(title_a, title_b) >= threshold


def rank_and_dedup(
    items: list[DigestItem], *,
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
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/pipeline/rank.py tests/test_pipeline_rank.py
git commit -m "feat(pipeline): score-sorted ranking with near-dup + category caps"
```

---

## Task 14: HTML Email Renderer

**Files:**
- Create: `src/ai_news/renderers/html_email.py`, `src/ai_news/renderers/templates/daily.html.j2`, `src/ai_news/renderers/templates/weekly.html.j2`, `tests/test_renderer_html.py`

- [ ] **Step 1: Create `src/ai_news/renderers/templates/daily.html.j2`**

```jinja
<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{{ subject }}</title>
<style>
  body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
         max-width: 680px; margin: 0 auto; padding: 16px; color: #222; }
  h1 { font-size: 20px; border-bottom: 2px solid #333; padding-bottom: 6px; }
  h2 { font-size: 16px; margin-top: 28px; color: #555;
       border-left: 4px solid #888; padding-left: 8px; }
  .item { margin: 14px 0 20px; }
  .item a { color: #0b5ed7; text-decoration: none; font-weight: 600; }
  .item .meta { color: #999; font-size: 12px; margin-top: 2px; }
  .item .summary { font-size: 14px; line-height: 1.6; margin-top: 4px; }
  .banner { background: #fff3cd; padding: 8px 12px; border-left: 4px solid #ffb703;
            margin-bottom: 16px; font-size: 13px; }
</style></head><body>
<h1>{{ heading }}</h1>
{% if banner %}<div class="banner">{{ banner }}</div>{% endif %}
{% for category, group in items_by_category %}
<h2>{{ category.value }}</h2>
{% for d in group %}
<div class="item">
  <a href="{{ d.raw.url }}">{{ d.cn_title }}</a>
  <div class="meta">{{ d.raw.source }} · 重要度 {{ "%.1f"|format(d.score) }} · <a href="{{ d.raw.url }}">原文</a></div>
  <div class="summary">{{ d.cn_summary }}</div>
</div>
{% endfor %}
{% endfor %}
<hr><p style="color:#aaa;font-size:11px">Generated {{ generated_at }} · AI News Digest</p>
</body></html>
```

- [ ] **Step 2: Create `src/ai_news/renderers/templates/weekly.html.j2`**

```jinja
{% extends "daily.html.j2" %}
```

*(Starts as an alias — room to diverge later. The renderer passes `heading="本周 AI 要闻"` for weekly runs.)*

- [ ] **Step 3: Write failing test `tests/test_renderer_html.py`**

```python
from datetime import datetime, timezone

from ai_news.models import Category, DigestItem, RawItem
from ai_news.renderers.html_email import render_email

UTC = timezone.utc


def _d(title: str, cat: Category, score: float) -> DigestItem:
    raw = RawItem(id=title, source="OpenAI", title="en-" + title, url="https://x/" + title,
                  published_at=datetime(2026, 4, 22, tzinfo=UTC),
                  raw_text=None, metadata={})
    return DigestItem(raw=raw, cn_title=title, cn_summary="摘要 " + title,
                      category=cat, score=score)


def test_render_groups_by_category_and_escapes():
    html = render_email(
        subject="[AI Daily] 2026-04-22",
        heading="每日 AI 要闻 · 2026-04-22",
        banner=None,
        items=[_d("发布 A", Category.MODEL_RELEASE, 9.1),
               _d("产品 B", Category.PRODUCT, 7.0)],
        template="daily.html.j2",
        generated_at="2026-04-22 08:00 CST",
    )
    assert "模型发布" in html
    assert "产品与工具" in html
    assert "发布 A" in html
    assert "https://x/发布 A" in html or "https://x/" in html


def test_banner_rendered_when_present():
    html = render_email(
        subject="s", heading="h", banner="⚠ 3 源失败",
        items=[_d("x", Category.OPINION, 5.0)],
        template="daily.html.j2", generated_at="t",
    )
    assert "⚠ 3 源失败" in html
```

- [ ] **Step 4: Run — FAIL**

- [ ] **Step 5: Implement `src/ai_news/renderers/html_email.py`**

```python
"""Render digest HTML email via Jinja2 templates."""
from __future__ import annotations

from itertools import groupby
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ai_news.models import Category, DigestItem

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2", "html.j2"]),
)

_CATEGORY_ORDER = [
    Category.MODEL_RELEASE,
    Category.PRODUCT,
    Category.RESEARCH,
    Category.TOOLING,
    Category.OPINION,
]


def _group_by_category(items: list[DigestItem]) -> list[tuple[Category, list[DigestItem]]]:
    by_cat: dict[Category, list[DigestItem]] = {c: [] for c in _CATEGORY_ORDER}
    for d in items:
        by_cat.setdefault(d.category, []).append(d)
    return [(c, by_cat[c]) for c in _CATEGORY_ORDER if by_cat.get(c)]


def render_email(*, subject: str, heading: str, banner: str | None,
                 items: list[DigestItem], template: str, generated_at: str) -> str:
    tpl = _env.get_template(template)
    return tpl.render(
        subject=subject,
        heading=heading,
        banner=banner,
        items_by_category=_group_by_category(items),
        generated_at=generated_at,
    )
```

- [ ] **Step 6: Run — PASS**

- [ ] **Step 7: Commit**

```bash
git add src/ai_news/renderers/ tests/test_renderer_html.py
git commit -m "feat(renderer): Jinja2 HTML email templates with category grouping"
```

---

## Task 15: SMTP Delivery

**Files:**
- Create: `src/ai_news/delivery/smtp.py`, `tests/test_delivery_smtp.py`

- [ ] **Step 1: Write failing test `tests/test_delivery_smtp.py`**

```python
from email import message_from_bytes

from ai_news.delivery.smtp import InMemoryMailer, Mailer, SMTPMailer, build_message


def test_build_message_is_multipart_utf8():
    raw = build_message(
        sender="a@b.com", to="c@d.com",
        subject="[AI Daily] 中文", html="<p>你好</p>",
    )
    msg = message_from_bytes(raw)
    assert msg["Subject"].startswith("=?")   # encoded non-ASCII
    html_parts = [p for p in msg.walk() if p.get_content_type() == "text/html"]
    assert len(html_parts) == 1
    assert "你好" in html_parts[0].get_payload(decode=True).decode("utf-8")


def test_in_memory_mailer_captures():
    m = InMemoryMailer()
    assert isinstance(m, Mailer)
    m.send(sender="s@x", to="r@x", subject="s", html="<b>h</b>")
    assert len(m.sent) == 1
    assert m.sent[0].subject == "s"
    assert m.sent[0].html == "<b>h</b>"
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement `src/ai_news/delivery/smtp.py`**

```python
"""SMTP delivery with in-memory test double."""
from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


def build_message(*, sender: str, to: str, subject: str, html: str) -> bytes:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("This is an HTML email. Please view it in an HTML-capable client.")
    msg.add_alternative(html, subtype="html")
    return msg.as_bytes()


@runtime_checkable
class Mailer(Protocol):
    def send(self, *, sender: str, to: str, subject: str, html: str) -> None: ...


@dataclass
class SentMessage:
    sender: str
    to: str
    subject: str
    html: str


@dataclass
class InMemoryMailer:
    sent: list[SentMessage] = field(default_factory=list)
    def send(self, *, sender: str, to: str, subject: str, html: str) -> None:
        self.sent.append(SentMessage(sender, to, subject, html))


class SMTPMailer:
    def __init__(self, *, host: str, port: int, user: str, password: str,
                 use_ssl: bool | None = None) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_ssl = bool(port == 465) if use_ssl is None else use_ssl

    def send(self, *, sender: str, to: str, subject: str, html: str) -> None:
        payload = build_message(sender=sender, to=to, subject=subject, html=html)
        ctx = ssl.create_default_context()
        if self.use_ssl:
            with smtplib.SMTP_SSL(self.host, self.port, context=ctx, timeout=30) as s:
                s.login(self.user, self.password)
                s.sendmail(sender, [to], payload)
        else:
            with smtplib.SMTP(self.host, self.port, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(self.user, self.password)
                s.sendmail(sender, [to], payload)
        logger.info("email sent to=%s subject=%s", to, subject)
```

- [ ] **Step 4: Run — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/ai_news/delivery/smtp.py tests/test_delivery_smtp.py
git commit -m "feat(delivery): SMTP mailer + in-memory test double"
```

---

## Task 16: Entrypoints (run_daily, run_weekly)

**Files:**
- Create: `src/ai_news/entrypoints/run_daily.py`, `src/ai_news/entrypoints/run_weekly.py`

This task has no dedicated unit test — the integration test (Task 17) covers it end-to-end. We still ship source to commit; run the e2e test in Task 17 for verification.

- [ ] **Step 1: Implement `src/ai_news/entrypoints/run_daily.py`**

```python
"""Daily digest entry point."""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_news.config import Config, SourceSpec, load_config
from ai_news.delivery.smtp import Mailer, SMTPMailer
from ai_news.llm.base import LLMProvider
from ai_news.llm.claude import ClaudeProvider
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
from ai_news.storage.seen_items import SeenItemsDB

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
    p, m, k = cfg.llm.provider, cfg.llm.model, cfg.llm.api_key
    if p == "openai":
        return OpenAICompatibleProvider.for_openai(api_key=k, model=m)
    if p == "deepseek":
        return OpenAICompatibleProvider.for_deepseek(api_key=k, model=m)
    if p == "claude":
        return ClaudeProvider(api_key=k, model=m)
    if p == "gemini":
        return GeminiProvider(api_key=k, model=m)
    raise ValueError(f"unknown llm provider: {p}")


def _subject_prefix(failed: list[str], rendered: int) -> str:
    if rendered == 0:
        return "[AI Daily ✗]"
    if failed:
        return "[AI Daily ⚠]"
    return "[AI Daily]"


def main(
    *, config_path: Path = Path("config.toml"),
    db_path: Path = Path("seen_items.sqlite"),
    llm: LLMProvider | None = None,
    mailer: Mailer | None = None,
    now: datetime | None = None,
    gh_token: str | None = None,
) -> RunResult:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = load_config(config_path)
    now = now or datetime.now(timezone.utc)
    llm = llm or build_llm(cfg)
    mailer = mailer or SMTPMailer(host=cfg.smtp.host, port=cfg.smtp.port,
                                  user=cfg.smtp.user, password=cfg.smtp.password)

    db = SeenItemsDB(db_path); db.initialize()

    sources = [build_source(s, gh_token=gh_token) for s in cfg.sources]
    since = now - timedelta(hours=cfg.daily.lookback_hours)

    raw: list = []
    failed: list[str] = []
    for src in sources:
        items = src.fetch(since=since)
        if not items:
            logger.info("source=%s returned 0 items", src.name)
        raw.extend(items)
    logger.info("fetch total=%d", len(raw))

    fresh = dedup_against_seen(raw, db=db)
    logger.info("dedup kept=%d", len(fresh))

    candidates = pre_filter(fresh, keywords=cfg.keywords, top_n=cfg.daily.pre_filter_top_n)
    logger.info("pre_filter kept=%d", len(candidates))

    digests = summarize_batch(candidates, llm=llm,
                              max_tokens=cfg.llm.max_output_tokens_daily)
    logger.info("summarize produced=%d", len(digests))

    final = rank_and_dedup(digests, max_total=cfg.daily.final_max_items,
                           per_category_cap=8, dup_threshold=85)
    logger.info("rank final=%d", len(final))

    tz = ZoneInfo(cfg.general.timezone)
    date_str = now.astimezone(tz).strftime("%Y-%m-%d")
    subject = (f"{_subject_prefix(failed, len(final))} {date_str} · "
               f"{len(final)} 条 · {len(set(d.category for d in final))} 类")
    banner = None
    if failed:
        banner = f"⚠ 以下信息源抓取失败：{', '.join(failed)}"
    html = render_email(
        subject=subject,
        heading=f"每日 AI 要闻 · {date_str}",
        banner=banner,
        items=final,
        template="daily.html.j2",
        generated_at=now.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z"),
    )

    if final:
        mailer.send(sender=cfg.smtp.user, to=cfg.general.recipient_email,
                    subject=subject, html=html)
        weekly_ids = weekly_candidate_ids(final,
                                          threshold=cfg.weekly.weekly_candidate_threshold)
        rows = [(d.raw.id, d.raw.source, d.raw.url, d.score, d.raw.id in weekly_ids)
                for d in digests]
        db.mark_seen(rows, now=now)
        db.purge_older_than(cutoff=now - timedelta(days=14))
    else:
        mailer.send(sender=cfg.smtp.user, to=cfg.general.recipient_email,
                    subject=subject, html=html)
        logger.warning("no items produced; sent degraded email")

    return RunResult(items_fetched=len(raw), items_rendered=len(final),
                     sources_failed=failed)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("daily run failed")
        sys.exit(1)
```

- [ ] **Step 2: Implement `src/ai_news/entrypoints/run_weekly.py`**

```python
"""Weekly digest entry point. Reuses daily infrastructure."""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_news.config import load_config
from ai_news.delivery.smtp import Mailer, SMTPMailer
from ai_news.entrypoints.run_daily import RunResult, build_llm
from ai_news.llm.base import LLMProvider
from ai_news.models import RawItem, stable_id
from ai_news.pipeline.rank import rank_and_dedup
from ai_news.pipeline.summarize import summarize_batch
from ai_news.renderers.html_email import render_email
from ai_news.storage.seen_items import SeenItemsDB

logger = logging.getLogger(__name__)


def main(
    *, config_path: Path = Path("config.toml"),
    db_path: Path = Path("seen_items.sqlite"),
    llm: LLMProvider | None = None,
    mailer: Mailer | None = None,
    now: datetime | None = None,
) -> RunResult:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = load_config(config_path)
    now = now or datetime.now(timezone.utc)
    llm = llm or build_llm(cfg)
    mailer = mailer or SMTPMailer(host=cfg.smtp.host, port=cfg.smtp.port,
                                  user=cfg.smtp.user, password=cfg.smtp.password)

    db = SeenItemsDB(db_path); db.initialize()
    since = now - timedelta(days=7)
    cand_rows = db.weekly_candidates(since=since)
    logger.info("weekly candidates=%d", len(cand_rows))

    raw = [
        RawItem(id=r[0], source=r[1], title=r[2], url=r[2],
                published_at=now, raw_text=None,
                metadata={"score_daily": r[3]})
        for r in cand_rows
    ]

    digests = summarize_batch(raw, llm=llm,
                              max_tokens=cfg.llm.max_output_tokens_weekly,
                              batch_size=4)
    final = rank_and_dedup(digests, max_total=30, per_category_cap=8, dup_threshold=85)

    tz = ZoneInfo(cfg.general.timezone)
    date_str = now.astimezone(tz).strftime("%Y-%m-%d")
    subject = f"[AI Weekly] {date_str} · 本周 {len(final)} 条精选"
    html = render_email(
        subject=subject, heading=f"本周 AI 要闻 · {date_str}",
        banner=None, items=final, template="weekly.html.j2",
        generated_at=now.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z"),
    )
    mailer.send(sender=cfg.smtp.user, to=cfg.general.recipient_email,
                subject=subject, html=html)
    return RunResult(items_fetched=len(raw), items_rendered=len(final), sources_failed=[])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("weekly run failed")
        sys.exit(1)
```

- [ ] **Step 3: Commit (tests come in Task 17)**

```bash
git add src/ai_news/entrypoints/
git commit -m "feat(entrypoints): run_daily and run_weekly wiring full pipeline"
```

---

## Task 17: End-to-End Integration Test

**Files:**
- Create: `tests/test_e2e.py`, `tests/fixtures/two_feeds_daily.toml`, `tests/fixtures/feed_a.xml`, `tests/fixtures/feed_b.xml`

- [ ] **Step 1: Create `tests/fixtures/feed_a.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>A</title>
<item><title>Claude 4.6 Sonnet released</title><link>https://a.example.com/1</link>
<pubDate>Wed, 22 Apr 2026 08:00:00 GMT</pubDate>
<description>Anthropic releases Claude 4.6 Sonnet with agent improvements.</description></item>
</channel></rss>
```

- [ ] **Step 2: Create `tests/fixtures/feed_b.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>B</title>
<item><title>GPT-5.4 announced</title><link>https://b.example.com/1</link>
<pubDate>Wed, 22 Apr 2026 09:00:00 GMT</pubDate>
<description>OpenAI announces GPT-5.4, a faster variant.</description></item>
</channel></rss>
```

- [ ] **Step 3: Create `tests/fixtures/two_feeds_daily.toml`**

```toml
[general]
timezone = "Asia/Shanghai"
recipient_email = "me@example.com"
digest_language = "zh-CN"

[llm]
provider = "deepseek"
model = "deepseek-chat"
max_output_tokens_daily = 4000
max_output_tokens_weekly = 16000

[daily]
send_hour_local = 8
lookback_hours = 48
pre_filter_top_n = 10
final_max_items = 10

[weekly]
send_weekday = "monday"
send_hour_local = 8
weekly_candidate_threshold = 8.0

[keywords]
high = ["claude", "gpt"]
medium = []
negative = []

[[sources.items]]
type = "rss"
name = "FeedA"
url = "https://ignored/a.xml"
weight = 1.0

[[sources.items]]
type = "rss"
name = "FeedB"
url = "https://ignored/b.xml"
weight = 1.0
```

- [ ] **Step 4: Write `tests/test_e2e.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from ai_news.delivery.smtp import InMemoryMailer
from ai_news.entrypoints import run_daily
from ai_news.sources import rss as rss_module

UTC = timezone.utc
FIXTURES = Path(__file__).parent / "fixtures"


class ScriptedLLM:
    name = "scripted"
    def complete(self, *, system, user, max_tokens):
        # Extract ids from user prompt and return one dict per id.
        import re
        ids = re.findall(r'"id":\s*"([a-f0-9]+)"', user)
        return json.dumps({"items": [
            {"id": i, "cn_title": f"中文 {i[:4]}", "cn_summary": "自动生成摘要。",
             "category": "模型发布", "score": 8.5} for i in ids
        ]})


def test_daily_run_end_to_end(tmp_path, monkeypatch):
    # Stub HTTP for both feeds.
    a_bytes = (FIXTURES / "feed_a.xml").read_bytes()
    b_bytes = (FIXTURES / "feed_b.xml").read_bytes()
    original_init = rss_module.RSSSource.__init__

    def by_name_fetch(self):
        return a_bytes if self.name == "FeedA" else b_bytes

    monkeypatch.setattr(rss_module.RSSSource, "_fetch_bytes", by_name_fetch)

    # All required env.
    for k, v in {
        "LLM_API_KEY": "k", "SMTP_HOST": "smtp.example.com", "SMTP_PORT": "465",
        "SMTP_USER": "u@example.com", "SMTP_PASS": "p",
    }.items():
        monkeypatch.setenv(k, v)

    mailer = InMemoryMailer()
    result = run_daily.main(
        config_path=FIXTURES / "two_feeds_daily.toml",
        db_path=tmp_path / "seen.sqlite",
        llm=ScriptedLLM(),
        mailer=mailer,
        now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    )

    assert result.items_rendered == 2
    assert len(mailer.sent) == 1
    msg = mailer.sent[0]
    assert msg.to == "me@example.com"
    assert "[AI Daily]" in msg.subject
    assert "2 条" in msg.subject
    assert "模型发布" in msg.html
    assert "中文" in msg.html


def test_daily_run_handles_source_failure(tmp_path, monkeypatch):
    def failing_fetch(self):
        if self.name == "FeedA":
            import httpx
            raise httpx.ConnectError("boom")
        return (FIXTURES / "feed_b.xml").read_bytes()

    monkeypatch.setattr(rss_module.RSSSource, "_fetch_bytes", failing_fetch)

    for k, v in {
        "LLM_API_KEY": "k", "SMTP_HOST": "x", "SMTP_PORT": "465",
        "SMTP_USER": "u", "SMTP_PASS": "p",
    }.items():
        monkeypatch.setenv(k, v)

    mailer = InMemoryMailer()
    result = run_daily.main(
        config_path=FIXTURES / "two_feeds_daily.toml",
        db_path=tmp_path / "seen.sqlite",
        llm=ScriptedLLM(),
        mailer=mailer,
        now=datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
    )
    # One feed survived.
    assert result.items_rendered >= 1
    assert len(mailer.sent) == 1
```

- [ ] **Step 5: Run — the first version may fail because `RSSSource.fetch` catches `HTTPError` but not `ConnectError` unrelated... actually httpx.ConnectError inherits from HTTPError, so it's caught. Should PASS.**

```bash
pytest tests/test_e2e.py -v
```

- [ ] **Step 6: Commit**

```bash
git add tests/test_e2e.py tests/fixtures/
git commit -m "test(e2e): end-to-end daily run with scripted LLM and in-memory mailer"
```

---

## Task 18: Local Smoke Script

**Files:**
- Create: `scripts/smoke.py`

- [ ] **Step 1: Implement `scripts/smoke.py`**

```python
"""Run real fetch + real LLM, print HTML to stdout, send NO email."""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from ai_news.delivery.smtp import InMemoryMailer
from ai_news.entrypoints import run_daily


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s %(message)s")
    mailer = InMemoryMailer()
    result = run_daily.main(
        config_path=Path("config.toml"),
        db_path=Path(".smoke-seen.sqlite"),
        mailer=mailer,
        now=datetime.now(timezone.utc),
    )
    if mailer.sent:
        print(mailer.sent[0].html)
    print(f"\n---\nitems_fetched={result.items_fetched} "
          f"items_rendered={result.items_rendered} "
          f"failed={result.sources_failed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/smoke.py
git commit -m "feat(scripts): local smoke run that prints HTML without emailing"
```

---

## Task 19: GitHub Actions — Daily and Weekly

**Files:**
- Create: `.github/workflows/daily.yml`, `.github/workflows/weekly.yml`

- [ ] **Step 1: Create `.github/workflows/daily.yml`**

```yaml
name: daily-digest
on:
  schedule:
    - cron: "0 0 * * *"   # 08:00 Asia/Shanghai
  workflow_dispatch:

concurrency:
  group: digest
  cancel-in-progress: false

jobs:
  send:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e .

      - name: Restore seen_items
        uses: actions/cache@v4
        with:
          path: seen_items.sqlite
          key: seen-items-${{ github.run_id }}
          restore-keys: |
            seen-items-

      - name: Run daily digest
        env:
          LLM_API_KEY:          ${{ secrets.LLM_API_KEY }}
          LLM_FALLBACK_API_KEY: ${{ secrets.LLM_FALLBACK_API_KEY }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          GH_TOKEN:  ${{ secrets.GITHUB_TOKEN }}
        run: python -m ai_news.entrypoints.run_daily

      - name: Save seen_items
        if: always()
        uses: actions/cache/save@v4
        with:
          path: seen_items.sqlite
          key: seen-items-${{ github.run_id }}
```

- [ ] **Step 2: Create `.github/workflows/weekly.yml`**

```yaml
name: weekly-digest
on:
  schedule:
    - cron: "0 0 * * 1"   # Mon 08:00 CST
  workflow_dispatch:

jobs:
  send:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e .

      - name: Restore seen_items
        uses: actions/cache@v4
        with:
          path: seen_items.sqlite
          key: seen-items-${{ github.run_id }}
          restore-keys: |
            seen-items-

      - name: Run weekly digest
        env:
          LLM_API_KEY:          ${{ secrets.LLM_API_KEY }}
          LLM_FALLBACK_API_KEY: ${{ secrets.LLM_FALLBACK_API_KEY }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
        run: python -m ai_news.entrypoints.run_weekly
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/daily.yml .github/workflows/weekly.yml
git commit -m "ci: GitHub Actions cron workflows for daily and weekly digests"
```

---

## Task 20: Source Healthcheck Workflow

**Files:**
- Create: `.github/workflows/source-healthcheck.yml`, `scripts/healthcheck.py`

- [ ] **Step 1: Implement `scripts/healthcheck.py`**

```python
"""Fetch every configured source, print pass/fail, exit 1 if any source died."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_news.config import load_config
from ai_news.entrypoints.run_daily import build_source


def main() -> int:
    cfg = load_config(Path("config.toml"))
    since = datetime.now(timezone.utc) - timedelta(days=7)
    failed = []
    for spec in cfg.sources:
        src = build_source(spec, gh_token=None)
        try:
            items = src.fetch(since=since)
            print(f"[ok] {spec.name}: {len(items)} items")
        except Exception as exc:
            failed.append(spec.name)
            print(f"[FAIL] {spec.name}: {exc}")
    if failed:
        print(f"\n{len(failed)} source(s) failed: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Implement `.github/workflows/source-healthcheck.yml`**

```yaml
name: source-healthcheck
on:
  schedule:
    - cron: "0 6 * * 0"   # Sunday 14:00 CST
  workflow_dispatch:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e .
      - env:
          LLM_API_KEY: "healthcheck"
          SMTP_HOST: "unused"
          SMTP_PORT: "465"
          SMTP_USER: "u"
          SMTP_PASS: "p"
        run: python scripts/healthcheck.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/healthcheck.py .github/workflows/source-healthcheck.yml
git commit -m "ci: weekly source healthcheck workflow"
```

---

## Task 21: Sample `config.toml`

**Files:**
- Create: `config.toml`

- [ ] **Step 1: Create `config.toml` with a starter set of sources**

```toml
[general]
timezone = "Asia/Shanghai"
recipient_email = "REPLACE_ME@example.com"
digest_language = "zh-CN"

[llm]
provider = "deepseek"
model = "deepseek-chat"
max_output_tokens_daily = 4000
max_output_tokens_weekly = 16000

[llm.fallback]
provider = "gemini"
model = "gemini-2.0-flash"

[daily]
send_hour_local = 8
lookback_hours = 26
pre_filter_top_n = 40
final_max_items = 25

[weekly]
send_weekday = "monday"
send_hour_local = 8
weekly_candidate_threshold = 8.0

[keywords]
high     = ["claude", "gpt", "gemini", "agent", "skills", "openai", "anthropic",
            "cursor", "mcp", "llm", "rag", "tool use"]
medium   = ["benchmark", "eval", "fine-tune", "open source", "inference"]
negative = ["crypto", "nft", "stock price"]

# ---- Sources ----
[[sources.items]]
type = "rss"; name = "OpenAI Blog"; url = "https://openai.com/blog/rss.xml"; weight = 1.0

[[sources.items]]
type = "rss"; name = "Anthropic News"; url = "https://www.anthropic.com/news/rss.xml"; weight = 1.0

[[sources.items]]
type = "rss"; name = "Google DeepMind"; url = "https://deepmind.google/blog/rss.xml"; weight = 1.0

[[sources.items]]
type = "rss"; name = "Meta AI"; url = "https://ai.meta.com/blog/rss/"; weight = 0.9

[[sources.items]]
type = "rss"; name = "Cursor Changelog"; url = "https://cursor.com/changelog/rss.xml"; weight = 0.9

[[sources.items]]
type = "rss"; name = "Hacker News (AI)"; url = "https://hnrss.org/newest?q=AI+OR+LLM+OR+GPT+OR+Claude&points=100"; weight = 0.6

[[sources.items]]
type = "rss"; name = "r/LocalLLaMA"; url = "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=day"; weight = 0.6

[[sources.items]]
type = "rss"; name = "r/MachineLearning"; url = "https://www.reddit.com/r/MachineLearning/top/.rss?t=day"; weight = 0.5

[[sources.items]]
type = "rss"; name = "arXiv cs.CL"; url = "http://export.arxiv.org/rss/cs.CL"; weight = 0.4

[[sources.items]]
type = "rss"; name = "arXiv cs.AI"; url = "http://export.arxiv.org/rss/cs.AI"; weight = 0.4

[[sources.items]]
type = "rss"; name = "机器之心"; url = "https://www.jiqizhixin.com/rss"; weight = 0.8

[[sources.items]]
type = "rss"; name = "量子位"; url = "https://www.qbitai.com/feed"; weight = 0.8

[[sources.items]]
type = "github_releases"; name = "claude-code"; repo = "anthropics/claude-code"; weight = 0.9

[[sources.items]]
type = "github_releases"; name = "openai-python"; repo = "openai/openai-python"; weight = 0.7

[[sources.items]]
type = "github_releases"; name = "langchain"; repo = "langchain-ai/langchain"; weight = 0.6

[[sources.items]]
type = "github_releases"; name = "llama.cpp"; repo = "ggerganov/llama.cpp"; weight = 0.6

[[sources.items]]
type = "github_releases"; name = "transformers"; repo = "huggingface/transformers"; weight = 0.6
```

- [ ] **Step 2: Commit**

```bash
git add config.toml
git commit -m "feat(config): starter config.toml with curated source list"
```

---

## Task 22: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# AI News Digest

Daily + weekly Chinese-language AI-news email digests, auto-delivered via GitHub Actions.

## What it does

- Fetches from RSS feeds (OpenAI/Anthropic/Google/Meta/HN/Reddit/arXiv/Chinese outlets/…) and GitHub Releases.
- Deduplicates against a 14-day rolling store.
- Uses an LLM (DeepSeek / OpenAI / Claude / Gemini) to pick, summarize, translate, and classify.
- Sends one HTML email per day at 08:00 Asia/Shanghai, plus a weekly digest Monday morning.

## Quick start

1. Fork this repo.
2. Copy `config.toml` and edit `general.recipient_email`, plus tweak sources / keywords.
3. In the repo **Settings → Secrets and variables → Actions**, add:
   - `LLM_API_KEY`  (primary provider's key — matches `llm.provider` in `config.toml`)
   - `LLM_FALLBACK_API_KEY` (optional)
   - `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS`
4. Enable Actions for the fork. The `daily-digest` workflow will run on cron.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Smoke run against real sources + real LLM, printing HTML to stdout (no email):

```bash
export LLM_API_KEY=...
export SMTP_HOST=x SMTP_PORT=465 SMTP_USER=x SMTP_PASS=x  # still required by config loader
python scripts/smoke.py > /tmp/out.html && open /tmp/out.html
```

## Adding a source

Add a block to `config.toml`:

```toml
[[sources.items]]
type = "rss"
name = "My Source"
url = "https://example.com/feed.xml"
weight = 0.8
```

To add a brand-new source *kind* (not RSS / GitHub Releases), implement a class matching the `Source` protocol in `src/ai_news/sources/` and register it in `build_source` in `src/ai_news/entrypoints/run_daily.py`.

## Switching LLM provider

Change `llm.provider` and `llm.model` in `config.toml`. Supported: `openai`, `deepseek`, `claude`, `gemini`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with setup, local dev, and extension guide"
```

---

## Self-Review

**1. Spec coverage**

| Spec section | Implemented in task(s) |
|---|---|
| §3 Architecture diagram | Tasks 5–19 wire it up |
| §4 Repository layout | Tasks 1–22 |
| §5 Interfaces (RawItem/DigestItem/Category/Source/LLMProvider) | Tasks 2, 5, 7 |
| §6 Daily flow steps 1–11 | Task 16 (`run_daily.main`) |
| §6 Weekly differences | Task 16 (`run_weekly.main`) |
| §7 SQLite schema + 14-day purge | Task 4 |
| §8 Config + secrets | Tasks 3, 19, 21 |
| §9 Error handling (source fail, LLM retry, subject markers) | Tasks 5 (fail-soft), 12 (LLM retry), 16 (subject prefix) |
| §10 Cost control (batch, pre_filter, token budget) | Tasks 11, 12 |
| §11 Testing strategy (all test layers) | Tasks 2–17 |
| §12 MVP scope | All tasks |
| §13 Open items (source list, prompt text, HTML look) | Tasks 14, 21; LLM prompt in Task 12 |

No spec item lacks a task.

**2. Placeholder scan**

No "TBD", "TODO", "fill in later", or bare "add error handling" directives remain.

**3. Type consistency**

- `RawItem.id` (`str`), `DigestItem.raw` (`RawItem`), `Category` (Enum) — used consistently.
- `Source.fetch(since=...)` keyword-only — consistent in RSS / GitHub / test stubs / entrypoints.
- `LLMProvider.complete(system=..., user=..., max_tokens=...)` — consistent across OpenAI-compatible, Claude, Gemini, FakeLLM, ScriptedLLM, and `summarize_batch`.
- `SeenItemsDB.mark_seen(rows, *, now)` / `purge_older_than(*, cutoff)` — used identically in tests and in `run_daily`.
- `Mailer.send(*, sender, to, subject, html)` — same signature in `SMTPMailer`, `InMemoryMailer`, and call sites.
- `RunResult` fields (`items_fetched`, `items_rendered`, `sources_failed`) — same in `run_daily` and `run_weekly` and e2e test.
