# AI News Daily Digest — Design Spec

- Date: 2026-04-22
- Status: Approved (brainstorming complete, pending implementation plan)
- Owner: bill

## 1. Goal

Deliver a daily and weekly Chinese-language email digest of the most relevant news, releases, and discussions from the AI ecosystem (OpenAI, Anthropic, Google, agent/skills/MCP, open-source LLMs, research, products). The system runs unattended, costs near-zero, and degrades gracefully when individual sources fail.

**Non-goals:** real-time push, interactive web UI, multi-user, personalized reinforcement-learning ranking.

## 2. Success Criteria

- Receive one daily HTML email at ~08:00 Asia/Shanghai, 7 days a week, with 15–30 curated items grouped by category, each with a Chinese title and 2–4-sentence summary.
- Receive one weekly deep-digest email Monday 08:00, with a "top three stories of the week" lead section plus categorized archive.
- Single-source failure (Reddit down, arXiv slow) never prevents the email from going out; it shows up with a visible `⚠` marker instead.
- LLM cost per daily run ≤ $0.05, per weekly run ≤ $0.20 (typical).
- Adding a new source = implementing one class + one `config.toml` entry. Swapping LLM provider = one config line.

## 3. Architecture Overview

```
GitHub Actions cron (daily / weekly)
        │
        ▼
sources/*  ──► RawItem[] ──► pipeline (dedup → filter → LLM summarize → classify → rank) ──► DigestItem[]
                                                │
                                                ▼
                          renderers/html_email.j2 ──► delivery/smtp ──► inbox
                                                │
                     storage/seen_items.sqlite  ──► GitHub Actions cache (14-day rolling)
```

Two entry scripts (`run_daily.py`, `run_weekly.py`) reuse the same sources + pipeline; only configuration and prompt differ.

## 4. Repository Layout

```
ai-news-digest/
├── .github/workflows/
│   ├── daily.yml            # cron: 0 0 * * *  (UTC 00:00 = 08:00 Asia/Shanghai)
│   ├── weekly.yml           # cron: 0 0 * * 1
│   └── source-healthcheck.yml  # weekly dry-run, validates sources are alive
├── src/ai_news/
│   ├── __init__.py
│   ├── config.py            # loads config.toml + env secrets
│   ├── models.py            # RawItem, DigestItem, Category
│   ├── sources/
│   │   ├── base.py          # Source protocol
│   │   ├── rss.py
│   │   ├── github.py        # GitHub Releases
│   │   ├── product_hunt.py
│   │   └── newsletter.py
│   ├── pipeline/
│   │   ├── dedup.py
│   │   ├── filter.py
│   │   ├── summarize.py
│   │   ├── classify.py
│   │   └── rank.py
│   ├── llm/
│   │   ├── base.py          # LLMProvider protocol
│   │   ├── claude.py
│   │   ├── openai.py
│   │   ├── gemini.py
│   │   └── deepseek.py
│   ├── renderers/
│   │   ├── html_email.py
│   │   └── templates/{daily,weekly}.html.j2
│   ├── delivery/
│   │   └── smtp.py
│   ├── storage/
│   │   └── seen_items.py    # SQLite wrapper
│   └── entrypoints/
│       ├── run_daily.py
│       └── run_weekly.py
├── scripts/
│   └── smoke.py             # local dry-run, prints HTML to stdout, no email sent
├── tests/
├── config.toml
├── config.test.toml
├── pyproject.toml
└── README.md
```

## 5. Core Interfaces

```python
@dataclass(frozen=True)
class RawItem:
    id: str                         # stable hash(url + source)
    source: str
    title: str
    url: str
    published_at: datetime
    raw_text: str | None
    metadata: dict[str, Any]        # upvotes, author, stars, etc.

class Category(Enum):
    MODEL_RELEASE = "模型发布"
    PRODUCT       = "产品与工具"
    RESEARCH      = "研究与论文"
    TOOLING       = "工程与框架"
    OPINION       = "观点与讨论"

@dataclass(frozen=True)
class DigestItem:
    raw: RawItem
    cn_title: str
    cn_summary: str                 # 2–4 sentences, Chinese
    category: Category
    score: float                    # 0–10, used for ranking and weekly eligibility

class Source(Protocol):
    name: str
    def fetch(self, since: datetime) -> list[RawItem]: ...

class LLMProvider(Protocol):
    def complete(self, *, system: str, user: str, max_tokens: int) -> str: ...
```

All external dependencies (LLM, mailer, clock, storage path) are injectable into entry-point `main()` functions for testing.

## 6. Daily Run Flow

1. `load_config()` — `config.toml` + env secrets.
2. `load_seen()` — restore `seen_items.sqlite` from Actions cache; empty on cache miss.
3. `fetch_all(since=now-26h)` — concurrent fetch across sources; per-source failures captured, not fatal.
4. `dedup()` — drop any `RawItem.id` already in `seen_items`.
5. `pre_filter()` — rule-based scoring (source weight + keyword hits + popularity threshold); keep top 40.
6. `summarize_batch()` — LLM batched (5–8 items per call) produces Chinese title, 2–4-sentence summary, category, importance score 0–10. Strict JSON schema; on parse failure, single-item retry once.
7. `post_rank()` — sort by score, near-duplicate suppression (TF-IDF cosine over title tokens; threshold 0.85; no embedding model required), cap per-category, total 20–30 items. Items with score ≥ `weekly_candidate_threshold` marked `weekly_candidate=true` in `seen_items`.
8. `render_html()` — jinja2 `daily.html.j2`.
9. `send_email()` — SMTP; retry 3 times with exponential backoff.
10. `mark_seen() / save_seen()` — write new ids into SQLite (14-day rolling purge), save cache.

### Weekly Run Differences

- `since = now - 7d`; candidate pool = `seen_items` rows with `weekly_candidate=true` from the past 7 days.
- Different prompt: "summarize the top three stories of the week, then group remaining by category".
- `max_output_tokens` ≈ 4× daily.
- Renders `weekly.html.j2`.

## 7. Storage

SQLite file `seen_items.sqlite`, persisted via GitHub Actions cache (key rolls weekly, so cache eviction means at most a one-day dedup gap).

```sql
CREATE TABLE seen_items (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    score REAL,
    weekly_candidate INTEGER DEFAULT 0
);
CREATE INDEX idx_first_seen ON seen_items(first_seen_at);
-- purge: DELETE WHERE first_seen_at < now - 14 days
```

## 8. Configuration

### `config.toml` (committed)

```toml
[general]
timezone = "Asia/Shanghai"
recipient_email = "your@email.com"
digest_language = "zh-CN"

[llm]
provider = "deepseek"            # claude | openai | gemini | deepseek
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
high     = ["claude","gpt","gemini","agent","skills","openai","anthropic",
            "cursor","mcp","llm","rag","tool use"]
medium   = ["benchmark","eval","fine-tune","open source","inference"]
negative = ["crypto","nft","stock price"]

[[sources.items]]
type = "rss"; name = "OpenAI Blog"; url = "https://openai.com/blog/rss.xml"; weight = 1.0
# ... more
```

### Secrets (GitHub Actions, not committed)

| Secret | Purpose | Required |
|---|---|---|
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | Email delivery | Yes |
| `LLM_API_KEY` | Primary provider | Yes |
| `LLM_FALLBACK_API_KEY` | Fallback provider | Optional |
| `GH_TOKEN` | GitHub API rate-limit relief | Optional |

## 9. Error Handling & Observability

| Failure | Strategy |
|---|---|
| Single source fetch fails | Log warning, continue with other sources |
| All sources fail | Send degraded email titled `[AI Daily ✗] …抓取异常` |
| LLM call fails | Exponential backoff retry ×3 (1s/4s/16s) |
| Primary LLM sustained failure | Switch to `llm.fallback`, annotate email top banner |
| LLM JSON parse fails | Single-item retry ×1, then skip that item only |
| SMTP fails | Retry ×3, then `exit 1` (GitHub auto-notifies) |
| Cache miss on `seen_items` | Start empty + warning; at most one day of duplicates |

Email subject encodes health:

- Healthy: `[AI Daily] 2026-04-22 · 24 条 · 5 类`
- Degraded: `[AI Daily ⚠] 2026-04-22 · 18 条 · 3 源失败`
- Full failure: `[AI Daily ✗] 2026-04-22 · 抓取异常`

Logs to stdout, structured key=value pairs, consumed by GitHub Actions summary.

## 10. Cost Control

| Mechanism | Effect |
|---|---|
| `pre_filter` cap at 40 items | Avoids LLM over full 500-item fetch |
| Batch 5–8 items per LLM call | ~80% fewer API calls |
| Only feed title + first 800 chars of body | ~300 input tokens/item |
| Strict JSON output schema | No retries from malformed output |

Typical daily: ~12K input + ~4K output tokens → < $0.02 on Claude Haiku / Gemini Flash / DeepSeek.

## 11. Testing Strategy

| Layer | Type | Tools | Focus |
|---|---|---|---|
| models, config | unit | pytest | dataclass / TOML parsing edges |
| sources/* | unit + fixtures | pytest + VCR / static XML fixtures | parser correctness against recorded real responses |
| pipeline/dedup | unit | pytest | id collision, 14-day purge |
| pipeline/filter | unit | pytest | keyword scoring, thresholds |
| pipeline/summarize | unit (LLM mocked) | pytest + FakeLLM | prompt build, JSON parse, retry |
| llm/* | contract | pytest | each adapter honors `LLMProvider`, error mapping |
| renderers | snapshot | pytest + syrupy | HTML snapshot, prevents regressions |
| delivery/smtp | unit | pytest + aiosmtpd | local SMTP server, no external network |
| entrypoints | integration | pytest | full pipeline with FakeLLM + InMemoryMailer |

Plus:

- `scripts/smoke.py` — manual real fetch + real LLM, prints HTML to stdout, sends no email
- Weekly `source-healthcheck.yml` — dry-run that fetches all sources, no email, alerts when a source dies

## 12. MVP Scope (Balanced)

**In:**
- RSS-parseable sources: official blogs (OpenAI, Anthropic, Google DeepMind, Meta AI, Cursor, …), Hacker News, Reddit, arXiv, Chinese outlets (机器之心, 量子位, InfoQ), Product Hunt RSS, curated newsletter RSS/archives.
- GitHub Releases for major AI projects (claude-code, openai-python, anthropic-sdk-python, langchain, llama.cpp, transformers, …).
- Daily + weekly emails with full LLM pipeline (dedup, filter, summarize, classify, rank).
- Multi-provider LLM adapter (Claude / OpenAI / Gemini / DeepSeek), switchable via config.

**Out (deferred):**
- X/Twitter integration (paid API / brittle scraping).
- Push via non-email channels (WeChat, Telegram, Feishu).
- Web dashboard / history search UI.
- Personal thumbs-up/down feedback loop into ranking.

## 13. Open Items for Implementation Plan

- Exact RSS URL list for all sources (to be finalized during implementation from a seed list).
- Exact prompt text for summarize / classify / weekly-digest (iterated during `smoke.py` runs).
- HTML template visual design (simple, readable; template ships with the repo).
