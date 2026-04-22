"""Fetch every configured source, print pass/fail, exit 1 if any source died."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_news.config import load_config
from ai_news.entrypoints.run_daily import build_source


def main() -> int:
    cfg = load_config(Path("config.toml"))
    since = datetime.now(timezone.utc) - timedelta(days=7)
    failed: list[str] = []
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
