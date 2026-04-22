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
