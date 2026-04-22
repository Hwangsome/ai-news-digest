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
            blocks = data["content"]
            text = "".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            )
            if not isinstance(text, str):
                raise LLMError(f"claude returned non-string content: {text!r}")
            return text
        except LLMError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"claude call failed: {exc}") from exc
