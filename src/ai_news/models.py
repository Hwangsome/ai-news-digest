"""Core dataclasses shared across the pipeline."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


def stable_id(*, source: str, url: str) -> str:
    h = hashlib.sha256(f"{source}\x00{url}".encode()).hexdigest()
    return h[:16]


class Category(StrEnum):
    MODEL_RELEASE = "模型发布"
    PRODUCT       = "产品与工具"
    RESEARCH      = "研究与论文"
    TOOLING       = "工程与框架"
    OPINION       = "观点与讨论"


@dataclass(frozen=True)
class RawItem:
    id: str
    source: str
    title: str
    url: str
    published_at: datetime
    raw_text: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DigestItem:
    raw: RawItem
    cn_title: str
    cn_summary: str
    category: Category
    score: float
