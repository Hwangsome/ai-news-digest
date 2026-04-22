import httpx
import pytest
from tenacity import wait_none

from ai_news.llm.base import LLMError
from ai_news.llm.openai_compatible import OpenAICompatibleProvider


def test_openai_compatible_sends_expected_payload(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "hi"}}]}

        def raise_for_status(self):
            pass

    def fake_post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)

    p = OpenAICompatibleProvider(
        api_key="k", model="gpt-5.4", base_url="https://api.openai.com/v1",
    )
    out = p.complete(system="sys", user="usr", max_tokens=100)
    assert out == "hi"
    assert calls[0][0] == "https://api.openai.com/v1/chat/completions"
    assert calls[0][1]["model"] == "gpt-5.4"
    assert calls[0][1]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    assert calls[0][1]["max_tokens"] == 100
    assert calls[0][2]["Authorization"] == "Bearer k"


def test_deepseek_uses_deepseek_base_url():
    p = OpenAICompatibleProvider.for_deepseek(api_key="k", model="deepseek-chat")
    assert p.base_url == "https://api.deepseek.com/v1"


def test_http_error_wrapped_as_llm_error(monkeypatch):
    monkeypatch.setattr(
        "ai_news.llm.openai_compatible._RETRY_WAIT", wait_none(),
    )

    def fake_post(url, json, headers, timeout):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("httpx.post", fake_post)
    p = OpenAICompatibleProvider(api_key="k", model="m", base_url="https://x/v1")
    with pytest.raises(LLMError, match="openai-compatible call failed"):
        p.complete(system="s", user="u", max_tokens=10)


def test_malformed_response_wrapped_as_llm_error(monkeypatch):
    monkeypatch.setattr(
        "ai_news.llm.openai_compatible._RETRY_WAIT", wait_none(),
    )

    class FakeResp:
        def json(self):
            return {"unexpected": "shape"}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "httpx.post", lambda url, json, headers, timeout: FakeResp()
    )
    p = OpenAICompatibleProvider(api_key="k", model="m", base_url="https://x/v1")
    with pytest.raises(LLMError):
        p.complete(system="s", user="u", max_tokens=10)


def test_non_string_content_wrapped_as_llm_error(monkeypatch):
    monkeypatch.setattr(
        "ai_news.llm.openai_compatible._RETRY_WAIT", wait_none(),
    )

    class FakeResp:
        def json(self):
            return {"choices": [{"message": {"content": None}}]}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        "httpx.post", lambda url, json, headers, timeout: FakeResp()
    )
    p = OpenAICompatibleProvider(api_key="k", model="m", base_url="https://x/v1")
    with pytest.raises(LLMError, match="non-string content"):
        p.complete(system="s", user="u", max_tokens=10)


def test_retries_on_transient_httperror(monkeypatch):
    monkeypatch.setattr(
        "ai_news.llm.openai_compatible._RETRY_WAIT", wait_none(),
    )
    calls = {"n": 0}

    class FakeResp:
        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

        def raise_for_status(self):
            pass

    def flaky_post(url, json, headers, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("transient")
        return FakeResp()

    monkeypatch.setattr("httpx.post", flaky_post)
    p = OpenAICompatibleProvider(api_key="k", model="m", base_url="https://x/v1")
    assert p.complete(system="s", user="u", max_tokens=10) == "ok"
    assert calls["n"] == 3
