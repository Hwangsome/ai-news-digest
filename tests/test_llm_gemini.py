import httpx
import pytest
from tenacity import wait_none

from ai_news.llm.base import LLMError
from ai_news.llm.gemini import GeminiProvider


def test_gemini_sends_expected_payload(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}
        def raise_for_status(self): pass

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)
    p = GeminiProvider(api_key="k", model="gemini-2.0-flash")
    out = p.complete(system="sys", user="u", max_tokens=200)
    assert out == "hello"
    assert calls[0][0] == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent?key=k"
    )
    assert calls[0][1]["systemInstruction"]["parts"][0]["text"] == "sys"
    assert calls[0][1]["generationConfig"]["maxOutputTokens"] == 200


def test_http_error_wrapped(monkeypatch):
    monkeypatch.setattr("ai_news.llm.gemini._RETRY_WAIT", wait_none())

    def raiser(**kw):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("httpx.post", raiser)
    p = GeminiProvider(api_key="k", model="m")
    with pytest.raises(LLMError):
        p.complete(system="s", user="u", max_tokens=10)


def test_malformed_response_wrapped(monkeypatch):
    monkeypatch.setattr("ai_news.llm.gemini._RETRY_WAIT", wait_none())

    class FakeResp:
        def json(self): return {"unexpected": "shape"}
        def raise_for_status(self): pass
    monkeypatch.setattr("httpx.post",
                       lambda url, json, headers, timeout: FakeResp())
    p = GeminiProvider(api_key="k", model="m")
    with pytest.raises(LLMError):
        p.complete(system="s", user="u", max_tokens=10)


def test_concatenates_text_parts(monkeypatch):
    class FakeResp:
        def json(self):
            return {"candidates": [{"content": {"parts": [
                {"text": "foo "},
                {"inlineData": {}},          # non-text part, skipped
                {"text": "bar"},
            ]}}]}
        def raise_for_status(self): pass
    monkeypatch.setattr("httpx.post",
                       lambda url, json, headers, timeout: FakeResp())
    p = GeminiProvider(api_key="k", model="m")
    assert p.complete(system="s", user="u", max_tokens=10) == "foo bar"


def test_retries_on_transient_httperror(monkeypatch):
    monkeypatch.setattr("ai_news.llm.gemini._RETRY_WAIT", wait_none())
    calls = {"n": 0}

    class FakeResp:
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        def raise_for_status(self): pass

    def flaky_post(url, json, headers, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("transient")
        return FakeResp()

    monkeypatch.setattr("httpx.post", flaky_post)
    p = GeminiProvider(api_key="k", model="m")
    assert p.complete(system="s", user="u", max_tokens=10) == "ok"
    assert calls["n"] == 3
