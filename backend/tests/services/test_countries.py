from app.services.countries import Country, all_countries, find_country, search_countries


def test_every_iso_country_is_listed_once_sorted_by_name() -> None:
    """R-CR-02."""
    countries = all_countries()

    assert len(countries) == 249
    assert len({country.code for country in countries}) == 249
    assert [country.name for country in countries] == sorted(country.name for country in countries)


def test_country_is_found_by_code_in_any_case() -> None:
    """R-CR-02."""
    assert find_country("au") == Country("AU", "Австралия")
    assert find_country("KZ") == Country("KZ", "Казахстан")
    assert find_country("XX") is None


def test_search_matches_russian_name_fragment() -> None:
    """R-UX-02."""
    assert Country("AU", "Австралия") in search_countries("авст")
    assert Country("AT", "Австрия") in search_countries("авст")


def test_search_matches_code_prefix() -> None:
    """R-UX-02."""
    assert [country.code for country in search_countries("kz")] == ["KZ"]


def test_empty_search_returns_everything() -> None:
    assert len(search_countries("  ")) == 249
