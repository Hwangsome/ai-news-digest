"""Adapter for OpenAI- and DeepSeek-compatible Chat Completions APIs."""
from __future__ import annotations

import httpx

from ai_news.llm.base import LLMError


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def for_openai(cls, *, api_key: str, model: str) -> OpenAICompatibleProvider:
        return cls(api_key=api_key, model=model, base_url="https://api.openai.com/v1")

    @classmethod
    def for_deepseek(cls, *, api_key: str, model: str) -> OpenAICompatibleProvider:
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
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMError(f"openai-compatible call failed: {exc}") from exc
