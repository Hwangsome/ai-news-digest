"""Composite LLM provider that falls back on sustained primary failure."""
from __future__ import annotations

import logging

from ai_news.llm.base import LLMError, LLMProvider

logger = logging.getLogger(__name__)


class FallbackLLM:
    """Try primary first; on LLMError, use fallback and flip `used_fallback`."""

    def __init__(self, *, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = f"{primary.name}|{fallback.name}"
        self.used_fallback = False

    def complete(self, *, system: str, user: str, max_tokens: int) -> str:
        try:
            return self.primary.complete(
                system=system, user=user, max_tokens=max_tokens,
            )
        except LLMError as exc:
            logger.warning(
                "primary LLM failed (%s); switching to fallback=%s",
                exc, self.fallback.name,
            )
            self.used_fallback = True
            return self.fallback.complete(
                system=system, user=user, max_tokens=max_tokens,
            )
