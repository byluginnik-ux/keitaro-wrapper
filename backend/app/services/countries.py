import gettext
from dataclasses import dataclass
from functools import cache

import pycountry


@dataclass(frozen=True, slots=True)
class Country:
    code: str
    name: str


@cache
def all_countries() -> tuple[Country, ...]:
    """ISO 3166-1 countries with Russian names, sorted by name (R-CR-02)."""
    russian = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["ru"])
    countries = (Country(item.alpha_2, russian.gettext(item.name)) for item in pycountry.countries)
    return tuple(sorted(countries, key=lambda country: country.name))


@cache
def _by_code() -> dict[str, Country]:
    return {country.code: country for country in all_countries()}


def find_country(code: str) -> Country | None:
    """Look a country up by its alpha-2 code in any letter case."""
    return _by_code().get(code.strip().upper())


def search_countries(query: str) -> list[Country]:
    """Countries whose name contains the query or whose code starts with it."""
    needle = query.strip().casefold()
    return [
        country
        for country in all_countries()
        if needle in country.name.casefold() or country.code.casefold().startswith(needle)
    ]
