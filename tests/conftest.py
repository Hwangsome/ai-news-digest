from datetime import datetime, timezone

import pytest

UTC = timezone.utc


@pytest.fixture
def now_utc() -> datetime:
    return datetime(2026, 4, 22, 0, 0, tzinfo=UTC)
