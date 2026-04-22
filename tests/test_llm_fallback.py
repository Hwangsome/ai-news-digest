import pytest

from ai_news.llm.base import LLMError
from ai_news.llm.fallback import FallbackLLM


class FakeLLM:
    def __init__(self, name, responses):
        self.name = name
        self.responses = list(responses)  # strings or LLMError instances
        self.calls = 0

    def complete(self, *, system, user, max_tokens):
        r = self.responses[self.calls]
        self.calls += 1
        if isinstance(r, LLMError):
            raise r
        return r


def test_fallback_uses_primary_when_ok():
    p = FakeLLM("p", ["hi"])
    f = FakeLLM("f", [])
    llm = FallbackLLM(primary=p, fallback=f)
    assert llm.complete(system="s", user="u", max_tokens=10) == "hi"
    assert llm.used_fallback is False
    assert f.calls == 0


def test_fallback_switches_on_primary_failure():
    p = FakeLLM("p", [LLMError("down")])
    f = FakeLLM("f", ["fb"])
    llm = FallbackLLM(primary=p, fallback=f)
    assert llm.complete(system="s", user="u", max_tokens=10) == "fb"
    assert llm.used_fallback is True


def test_fallback_propagates_fallback_failure():
    p = FakeLLM("p", [LLMError("down")])
    f = FakeLLM("f", [LLMError("also down")])
    llm = FallbackLLM(primary=p, fallback=f)
    with pytest.raises(LLMError):
        llm.complete(system="s", user="u", max_tokens=10)
