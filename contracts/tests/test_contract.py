import json
from importlib.metadata import version
from pathlib import Path
from typing import cast

import strawberry
from graphql import (
    GraphQLNamedType,
    GraphQLSchema,
    build_schema,
    is_introspection_type,
    is_specified_scalar_type,
    is_union_type,
    print_type,
)
from strawberry.tools import create_type
from strawberry.types.field import StrawberryField

from keitaro_contracts import load_schema_sdl, types

ROOT = Path(__file__).parent.parent
ROOT_OPERATIONS = {"Query", "Mutation", "Subscription"}


def contract() -> GraphQLSchema:
    return build_schema(load_schema_sdl())


def shared_types(schema: GraphQLSchema) -> dict[str, GraphQLNamedType]:
    return {
        name: kind
        for name, kind in schema.type_map.items()
        if name not in ROOT_OPERATIONS
        and not is_introspection_type(kind)
        and not is_specified_scalar_type(kind)
    }


def returning(kind: object, name: str) -> StrawberryField:
    """Build a field of that type: a union enters a schema only through a field."""

    def resolver() -> None:
        raise NotImplementedError

    resolver.__annotations__["return"] = kind
    field = strawberry.field(resolver=resolver, name=f"probe{name}")
    return cast("StrawberryField", field)  # the overload reports the resolver's own return type


def test_schema_is_valid_graphql_with_a_query_root() -> None:
    """R-ARCH-02."""
    assert contract().query_type is not None


def test_python_types_are_exactly_the_schema_types() -> None:
    """R-ARCH-02, R-ARCH-09: generated Strawberry types print back to the same SDL."""

    expected = shared_types(contract())
    unions = {name for name, kind in expected.items() if is_union_type(kind)}
    query = create_type("Query", [returning(getattr(types, name), name) for name in unions])
    python_types = [getattr(types, name) for name in expected if name not in unions]
    actual = strawberry.Schema(query=query, types=python_types)._schema.type_map  # noqa: SLF001  # pyright: ignore[reportPrivateUsage] — no public access to the core schema

    assert expected
    for name, kind in expected.items():
        assert print_type(actual[name]) == print_type(kind)


def test_typescript_types_mention_every_schema_type() -> None:
    """R-ARCH-02: the TypeScript side is generated from the same schema."""
    generated = (ROOT / "ts" / "generated.ts").read_text(encoding="utf-8")

    for name in shared_types(contract()):
        assert f"export type {name} =" in generated or f"export enum {name} " in generated


def test_both_packages_carry_the_same_version() -> None:
    """R-ARCH-08."""
    declared = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    npm = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]

    assert version("keitaro-wrapper-contracts") == declared
    assert npm == declared


def test_every_version_has_a_changelog_entry() -> None:
    """R-ARCH-08."""
    declared = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    assert f"## {declared}" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
