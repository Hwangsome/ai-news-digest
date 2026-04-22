"""Source protocol shared by all fetchers."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from ai_news.models import RawItem


@runtime_checkable
class Source(Protocol):
    name: str
    weight: float

    def fetch(self, *, since: datetime) -> list[RawItem]: ...
