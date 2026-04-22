import json
from datetime import datetime, timezone

from ai_news.models import Category, RawItem
from ai_news.pipeline.summarize import summarize_batch

UTC = timezone.utc


class FakeLLM:
    name = "fake"
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls = 0
    def complete(self, *, system, user, max_tokens):
        r = self.responses[self.calls]
        self.calls += 1
        return r


def _mk(i: int) -> RawItem:
    return RawItem(id=f"id{i}", source="s", title=f"Title {i}", url=f"https://x/{i}",
                   published_at=datetime(2026, 4, 22, tzinfo=UTC),
                   raw_text=f"Body {i}", metadata={})


def test_summarize_parses_batch():
    resp = json.dumps({"items": [
        {"id": "id0", "cn_title": "中文 0", "cn_summary": "摘要 0",
         "category": "模型发布", "score": 9.1},
        {"id": "id1", "cn_title": "中文 1", "cn_summary": "摘要 1",
         "category": "产品与工具", "score": 6.2},
    ]})
    llm = FakeLLM([resp])
    digests = summarize_batch([_mk(0), _mk(1)], llm=llm, max_tokens=500, batch_size=5)
    assert len(digests) == 2
    assert digests[0].cn_title == "中文 0"
    assert digests[0].category == Category.MODEL_RELEASE
    assert digests[1].score == 6.2


def test_summarize_retries_on_parse_error_then_succeeds():
    good = json.dumps({"items": [{"id": "id0", "cn_title": "a", "cn_summary": "b",
                                  "category": "模型发布", "score": 5.0}]})
    llm = FakeLLM(["garbage not-json", good])
    digests = summarize_batch([_mk(0)], llm=llm, max_tokens=500, batch_size=5)
    assert len(digests) == 1
    assert llm.calls == 2


def test_summarize_batches():
    resps = []
    for start in (0, 3):
        resps.append(json.dumps({"items": [
            {"id": f"id{start+k}", "cn_title": f"t{start+k}", "cn_summary": "s",
             "category": "产品与工具", "score": 5.0} for k in range(3)
        ]}))
    llm = FakeLLM(resps)
    items = [_mk(i) for i in range(6)]
    digests = summarize_batch(items, llm=llm, max_tokens=500, batch_size=3)
    assert len(digests) == 6
    assert llm.calls == 2


def test_summarize_skips_unknown_ids():
    resp = json.dumps({"items": [
        {"id": "id0", "cn_title": "ok", "cn_summary": "s",
         "category": "模型发布", "score": 7.0},
        {"id": "hallucinated", "cn_title": "x", "cn_summary": "x",
         "category": "模型发布", "score": 9.0},
    ]})
    llm = FakeLLM([resp])
    digests = summarize_batch([_mk(0)], llm=llm, max_tokens=500, batch_size=5)
    assert len(digests) == 1
    assert digests[0].raw.id == "id0"


def test_summarize_tolerates_unknown_category_label():
    resp = json.dumps({"items": [
        {"id": "id0", "cn_title": "ok", "cn_summary": "s",
         "category": "未知分类", "score": 5.0},
    ]})
    llm = FakeLLM([resp])
    digests = summarize_batch([_mk(0)], llm=llm, max_tokens=500, batch_size=5)
    assert len(digests) == 1
    assert digests[0].category == Category.OPINION


def test_summarize_skips_batch_after_two_failures():
    llm = FakeLLM(["bad", "also bad"])
    digests = summarize_batch([_mk(0)], llm=llm, max_tokens=500, batch_size=5)
    assert digests == []
    assert llm.calls == 2


def test_summarize_empty_input():
    llm = FakeLLM([])
    assert summarize_batch([], llm=llm, max_tokens=500, batch_size=5) == []
    assert llm.calls == 0
