"""Batch LLM summarization; strict JSON output."""
from __future__ import annotations

import json
import logging

from ai_news.llm.base import LLMError, LLMProvider
from ai_news.models import Category, DigestItem, RawItem

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert curator of AI/ML news for Chinese readers.
For each input article you will output JSON with these fields:
- id: the input id verbatim
- cn_title: Chinese title, concise (<= 30 chars)
- cn_summary: 2-4 sentence Chinese summary of what matters and why
- category: one of "模型发布", "产品与工具", "研究与论文", "工程与框架", "观点与讨论"
- score: float 0-10 importance for a senior AI engineer (10 = must-read)

Return ONLY a JSON object of shape {"items": [...]}. No prose, no code fences."""


def _batch_user_prompt(batch: list[RawItem]) -> str:
    payload = [
        {
            "id": it.id,
            "source": it.source,
            "title": it.title,
            "url": it.url,
            "body": (it.raw_text or "")[:800].replace("\n", " "),
        }
        for it in batch
    ]
    return "Articles (JSON array):\n" + json.dumps(payload, ensure_ascii=False)


def _parse_response(text: str, known_items: dict[str, RawItem]) -> list[DigestItem]:
    data = json.loads(text)
    out: list[DigestItem] = []
    for entry in data.get("items", []):
        raw = known_items.get(entry["id"])
        if raw is None:
            continue
        try:
            cat = Category(entry["category"])
        except ValueError:
            cat = Category.OPINION
        out.append(DigestItem(
            raw=raw,
            cn_title=str(entry["cn_title"]).strip()[:100],
            cn_summary=str(entry["cn_summary"]).strip(),
            category=cat,
            score=float(entry["score"]),
        ))
    return out


def summarize_batch(
    items: list[RawItem],
    *,
    llm: LLMProvider,
    max_tokens: int,
    batch_size: int = 6,
) -> list[DigestItem]:
    result: list[DigestItem] = []
    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        known = {it.id: it for it in batch}
        user = _batch_user_prompt(batch)
        try:
            resp = llm.complete(system=SYSTEM_PROMPT, user=user, max_tokens=max_tokens)
            result.extend(_parse_response(resp, known))
        except (json.JSONDecodeError, LLMError, KeyError, ValueError, TypeError) as exc:
            logger.warning("batch parse/LLM failed (%s); retrying once", exc)
            try:
                resp = llm.complete(system=SYSTEM_PROMPT, user=user, max_tokens=max_tokens)
                result.extend(_parse_response(resp, known))
            except Exception as exc2:
                logger.error("batch failed twice, skipping: %s", exc2)
    return result
