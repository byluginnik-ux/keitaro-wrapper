import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import pytest
import respx

from app.keitaro.client import KeitaroClient, create_http_client

BASE_URL = "https://tracker.test"
API = f"{BASE_URL}/admin_api/v1"
API_KEY = "fake-key"
FIXTURES = Path(__file__).parent.parent / "fixtures" / "keitaro"


def fixture_json(name: str) -> Any:  # noqa: ANN401 — raw tracker payloads are arbitrary JSON
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def tracker() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=API, assert_all_called=False) as router:
        yield router


@pytest.fixture
async def keitaro() -> AsyncIterator[KeitaroClient]:
    async with create_http_client(BASE_URL, API_KEY) as http:
        yield KeitaroClient(http, retry_delay=0)
