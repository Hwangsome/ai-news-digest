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
            text = "".join(p.get("text", "") for p in parts if "text" in p)
            if not isinstance(text, str):
                raise LLMError(f"gemini returned non-string content: {text!r}")
            return text
        except LLMError:
            raise
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"gemini call failed: {exc}") from exc
