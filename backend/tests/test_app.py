import pytest
import respx
from httpx import AsyncClient

from app.main import create_app
from app.settings import Settings

pytestmark = pytest.mark.anyio


async def test_graphql_is_served_over_http(client: AsyncClient) -> None:
    """R-ARCH-03: one endpoint, no tracker needed for countries."""
    response = await client.post(
        "/graphql", json={"query": '{ countries(search: "kz") { code name } }'}
    )

    assert response.status_code == 200
    assert response.json() == {"data": {"countries": [{"code": "KZ", "name": "Казахстан"}]}}


async def test_resolvers_reach_the_tracker_with_the_configured_key(client: AsyncClient) -> None:
    """R-KT-04: the key comes from settings and travels only in the header."""
    with respx.mock(base_url="https://tracker.test/admin_api/v1") as tracker:
        route = tracker.get("/domains").respond(json=[{"id": 1, "name": "tracker.example.com"}])

        response = await client.post("/graphql", json={"query": "{ domains { id name } }"})

    assert response.json() == {"data": {"domains": [{"id": 1, "name": "tracker.example.com"}]}}
    assert route.calls.last.request.headers["Api-Key"] == "fake-key"
    assert "fake-key" not in response.text


async def test_graphiql_is_off_unless_debugging(client: AsyncClient) -> None:
    """The interactive console is a development tool."""
    response = await client.get("/graphql", headers={"Accept": "text/html"})

    assert response.status_code == 404


def test_settings_without_a_key_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """R-KT-04: starting without a key must fail loudly, not at the first request."""
    monkeypatch.delenv("KEITARO_API_KEY", raising=False)

    with pytest.raises(ValueError, match="keitaro_api_key"):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue] — pydantic-settings init option


def test_application_is_built_from_settings(settings: Settings) -> None:
    assert create_app(settings).title == "Keitaro Wrapper"
