# AI News Digest

Daily + weekly Chinese-language AI-news email digests, auto-delivered via GitHub Actions.

## What it does

- Fetches from RSS feeds (OpenAI/Anthropic/Google/Meta/HN/Reddit/arXiv/Chinese outlets/…) and GitHub Releases.
- Deduplicates against a 14-day rolling store.
- Uses an LLM (DeepSeek / OpenAI / Claude / Gemini) to pick, summarize, translate, and classify.
- Sends one HTML email per day at 08:00 Asia/Shanghai, plus a weekly digest Monday morning.

## Quick start

1. Fork this repo.
2. Edit `config.toml`: set `general.recipient_email`, tweak sources/keywords.
3. In the repo **Settings → Secrets and variables → Actions**, add:
   - `LLM_API_KEY`  (primary provider's key — matches `llm.provider` in `config.toml`)
   - `LLM_FALLBACK_API_KEY` (optional)
   - `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS`
4. Enable Actions for the fork. The `daily-digest` workflow runs on cron.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Smoke run (real sources + real LLM, prints HTML to stdout, sends no email):

```bash
export LLM_API_KEY=...
export SMTP_HOST=x SMTP_PORT=465 SMTP_USER=x SMTP_PASS=x  # still required by loader
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

For a brand-new source *kind* (not RSS / GitHub Releases), implement a class that satisfies the `Source` protocol in `src/ai_news/sources/base.py` and register it in `build_source` in `src/ai_news/entrypoints/run_daily.py`.

## Switching LLM provider

Change `llm.provider` and `llm.model` in `config.toml`. Supported: `openai`, `deepseek`, `claude`, `gemini`.

## Architecture

See `docs/superpowers/specs/2026-04-22-ai-news-digest-design.md` for the full design; `docs/superpowers/plans/2026-04-22-ai-news-digest.md` for the implementation plan.
