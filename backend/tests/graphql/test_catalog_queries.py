import pytest

from app.graphql.context import Context
from app.graphql.schema import schema
from app.services.catalog import CatalogService
from tests.fakes import FakeKeitaro

pytestmark = pytest.mark.anyio

CREATOR_OPTIONS = """
query CreatorOptions($offerSearch: String!, $countrySearch: String!) {
  domains { id name }
  groups { id name }
  trafficSources { id name }
  offers(search: $offerSearch) { id name }
  countries(search: $countrySearch) { code name }
}
"""


async def test_creator_form_gets_all_reference_data_in_one_query() -> None:
    """R-UX-02, R-ARCH-03."""
    context = Context(catalog=CatalogService(FakeKeitaro()))

    result = await schema.execute(
        CREATOR_OPTIONS,
        variable_values={"offerSearch": "offer c", "countrySearch": "kz"},
        context_value=context,
    )

    assert result.errors is None
    assert result.data == {
        "domains": [{"id": 1813, "name": "tracker.example.com"}],
        "groups": [{"id": 10332, "name": "FORTESTS"}],
        "trafficSources": [{"id": 836, "name": "FORTESTS"}],
        "offers": [{"id": 11113, "name": "Offer C"}],
        "countries": [{"code": "KZ", "name": "Казахстан"}],
    }


async def test_tracker_failure_is_reported_without_internals() -> None:
    """R-KT-02."""
    keitaro = FakeKeitaro(fail_on={"list_domains"})
    context = Context(catalog=CatalogService(keitaro))

    result = await schema.execute("{ domains { id } }", context_value=context)

    assert result.data is None
    assert result.errors is not None
    assert result.errors[0].message == "Keitaro: list_domains failed"
    assert result.errors[0].extensions == {"code": "keitaro_error"}
