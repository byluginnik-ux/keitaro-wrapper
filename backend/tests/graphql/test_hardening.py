"""R-Q-07: the API gives away nothing a client of the service does not need."""

import pytest

from app.graphql.schema import build_schema
from app.settings import Settings
from tests.fakes import FakeKeitaro
from tests.graphql.support import context_for

INTROSPECTION = "{ __schema { queryType { name } } }"


def aliased(count: int) -> str:
    return (
        "{ " + " ".join(f"a{index}: serviceInfo {{ trackerUrl }}" for index in range(count)) + " }"
    )


@pytest.mark.anyio
async def test_schema_is_not_described_outside_debug() -> None:
    result = await build_schema(debug=False).execute(
        INTROSPECTION, context_value=context_for(FakeKeitaro())
    )

    assert result.data is None
    assert result.errors


@pytest.mark.anyio
async def test_schema_is_described_in_debug() -> None:
    result = await build_schema(debug=True).execute(
        INTROSPECTION, context_value=context_for(FakeKeitaro())
    )

    assert result.errors is None
    assert result.data == {"__schema": {"queryType": {"name": "Query"}}}


@pytest.mark.anyio
async def test_one_request_cannot_repeat_a_field_without_limit() -> None:
    context = context_for(FakeKeitaro())

    for schema in (build_schema(debug=False), build_schema(debug=True)):
        allowed = await schema.execute(aliased(15), context_value=context)
        refused = await schema.execute(aliased(16), context_value=context)

        assert allowed.errors is None
        assert refused.data is None
        assert refused.errors


@pytest.mark.anyio
async def test_an_oversized_request_is_refused() -> None:
    padding = " ".join(["trackerUrl"] * 1200)

    result = await build_schema(debug=False).execute(
        f"{{ serviceInfo {{ {padding} }} }}", context_value=context_for(FakeKeitaro())
    )

    assert result.data is None
    # refused while reading the text, before the costly validation starts
    assert result.errors
    assert "tokens" in str(result.errors[0])


def test_printed_settings_do_not_show_the_tracker_key() -> None:
    settings = Settings(keitaro_api_key="very-secret-key", storage_backend="memory")  # pyright: ignore[reportArgumentType] — pydantic turns the text into a secret

    assert "very-secret-key" not in repr(settings)
    assert "very-secret-key" not in settings.model_dump_json()
