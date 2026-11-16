"""GraphQL contract of Keitaro Wrapper: the schema text and the types generated from it."""

from importlib.resources import files
from pathlib import Path

SCHEMA_FILE = "schema.graphql"


def load_schema_sdl() -> str:
    """Return the contract as GraphQL SDL — the single source both sides are generated from."""
    packaged = files(__package__ or "keitaro_contracts").joinpath(SCHEMA_FILE)
    if packaged.is_file():
        return packaged.read_text(encoding="utf-8")
    # editable install: the schema stays next to the package, where it is edited
    return (Path(__file__).parent.parent / SCHEMA_FILE).read_text(encoding="utf-8")
