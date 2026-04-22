"""Adapter for OpenAI- and DeepSeek-compatible Chat Completions APIs."""
from __future__ import annotations

import httpx

from ai_news.llm._retry import llm_retry_attempts
from ai_news.llm.base import LLMError

_RETRY_WAIT = None  # tests monkeypatch to tenacity.wait_none() to skip sleeps


class OpenAICompatibleProvider:
    name = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 60.0,
        json_mode: bool = True,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.json_mode = json_mode

    @classmethod
    def for_openai(cls, *, api_key: str, model: str) -> OpenAICompatibleProvider:
        return cls(api_key=api_key, model=model, base_url="https://api.openai.com/v1")

    @classmethod
    def for_deepseek(cls, *, api_key: str, model: str) -> OpenAICompatibleProvider:
        return cls(api_key=api_key, model=model, base_url="https://api.deepseek.com/v1")

    def complete(self, *, system: str, user: str, max_tokens: int) -> str:
        for attempt in llm_retry_attempts(wait=_RETRY_WAIT):
            with attempt:
                return self._complete_once(
                    system=system, user=user, max_tokens=max_tokens,
                )
        raise RuntimeError("unreachable")  # tenacity reraises on failure

    def _complete_once(self, *, system: str, user: str, max_tokens: int) -> str:
        try:
            body: dict = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.2,
            }
            if self.json_mode:
                body["response_format"] = {"type": "json_object"}
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise LLMError(
                    f"openai-compatible returned non-string content: {content!r}"
                )
            if not content.strip():
                raise LLMError("openai-compatible returned empty content")
            return content
        except LLMError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise LLMError(f"openai-compatible call failed: {exc}") from exc
