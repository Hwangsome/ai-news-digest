"""LLMProvider protocol."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


class LLMError(Exception):
    pass


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete(self, *, system: str, user: str, max_tokens: int) -> str: ...
