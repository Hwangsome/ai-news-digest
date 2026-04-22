"""Shared retry policy for LLM adapters."""
from __future__ import annotations

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai_news.llm.base import LLMError


def llm_retry_attempts(wait=None) -> Retrying:
    """3 attempts total, 1s/4s/16s-ish exponential backoff on LLMError.

    The optional ``wait`` argument lets tests substitute ``wait_none()`` so
    failure-path tests don't actually sleep between attempts.
    """
    return Retrying(
        retry=retry_if_exception_type(LLMError),
        stop=stop_after_attempt(3),
        wait=wait if wait is not None else wait_exponential(
            multiplier=1, min=1, max=16,
        ),
        reraise=True,
    )
