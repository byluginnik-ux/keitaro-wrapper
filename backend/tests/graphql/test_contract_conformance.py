from graphql import build_schema, lexicographic_sort_schema, print_schema
from keitaro_contracts import load_schema_sdl

from app.graphql.schema import schema


def normalised(sdl: str) -> str:
    return print_schema(lexicographic_sort_schema(build_schema(sdl)))


def test_backend_schema_is_exactly_the_contract() -> None:
    """R-ARCH-02: resolvers may not add, drop or reshape anything the contract declares."""
    assert normalised(schema.as_str()) == normalised(load_schema_sdl())
