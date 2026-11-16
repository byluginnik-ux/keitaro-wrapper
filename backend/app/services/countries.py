from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Country:
    code: str
    name: str


def all_countries() -> tuple[Country, ...]:
    """ISO 3166-1 countries with Russian names, sorted by name (R-CR-02)."""
    raise NotImplementedError


def find_country(code: str) -> Country | None:
    """Look a country up by its alpha-2 code in any letter case."""
    raise NotImplementedError


def search_countries(query: str) -> list[Country]:
    """Countries whose name contains the query or whose code starts with it."""
    raise NotImplementedError
