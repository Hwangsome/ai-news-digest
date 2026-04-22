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
    print(
        f"\n---\nitems_fetched={result.items_fetched} "
        f"items_rendered={result.items_rendered} "
        f"failed={result.sources_failed}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
