import httpx
import pytest

from ai_news.llm.base import LLMError
from ai_news.llm.claude import ClaudeProvider


def test_claude_sends_expected_payload(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200

        def json(self):
            return {"content": [{"type": "text", "text": "ok"}]}

        def raise_for_status(self):
            pass

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)
    p = ClaudeProvider(api_key="k", model="claude-4-6-sonnet")
    out = p.complete(system="sys", user="u", max_tokens=200)
    assert out == "ok"
    assert calls[0][0] == "https://api.anthropic.com/v1/messages"
    assert calls[0][1]["system"] == "sys"
    assert calls[0][1]["max_tokens"] == 200
    assert calls[0][2]["x-api-key"] == "k"
    assert calls[0][2]["anthropic-version"] == "2023-06-01"


def test_http_error_wrapped(monkeypatch):
    def raiser(**kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("httpx.post", raiser)
    p = ClaudeProvider(api_key="k", model="m")
    with pytest.raises(LLMError):
        p.complete(system="s", user="u", max_tokens=10)


def test_malformed_response_wrapped(monkeypatch):
    class FakeResp:
        def json(self):
            return {"unexpected": "shape"}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "httpx.post", lambda url, json, headers, timeout: FakeResp()
    )
    p = ClaudeProvider(api_key="k", model="m")
    with pytest.raises(LLMError):
        p.complete(system="s", user="u", max_tokens=10)


def test_concatenates_text_blocks(monkeypatch):
    class FakeResp:
        def json(self):
            return {
                "content": [
                    {"type": "text", "text": "hello "},
                    {"type": "tool_use", "input": {}},
                    {"type": "text", "text": "world"},
                ]
            }

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "httpx.post", lambda url, json, headers, timeout: FakeResp()
    )
    p = ClaudeProvider(api_key="k", model="m")
    assert p.complete(system="s", user="u", max_tokens=10) == "hello world"
