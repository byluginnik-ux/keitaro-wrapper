import pytest

from app.keitaro.models import Offer
from app.services.catalog import CatalogService
from tests.fakes import B, FakeKeitaro

pytestmark = pytest.mark.anyio


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_reference_lists_come_from_the_tracker() -> None:
    catalog = CatalogService(FakeKeitaro())

    assert [domain.name for domain in await catalog.domains()] == ["tracker.example.com"]
    assert [group.name for group in await catalog.groups()] == ["FORTESTS"]
    assert [source.name for source in await catalog.traffic_sources()] == ["FORTESTS"]


async def test_offers_are_searched_by_name_ignoring_case() -> None:
    """R-KT-07."""
    catalog = CatalogService(FakeKeitaro())

    assert [offer.name for offer in await catalog.search_offers("offer b")] == ["Offer B"]


async def test_offers_are_searched_by_id_prefix() -> None:
    """R-KT-07."""
    catalog = CatalogService(FakeKeitaro())

    assert [offer.id for offer in await catalog.search_offers("11112")] == [B]
    assert len(await catalog.search_offers("1111")) == 4


async def test_empty_query_returns_the_first_offers_up_to_the_limit() -> None:
    catalog = CatalogService(FakeKeitaro())

    assert [offer.name for offer in await catalog.search_offers(limit=2)] == ["Offer A", "Offer B"]


async def test_archived_offers_are_not_offered() -> None:
    keitaro = FakeKeitaro()
    keitaro.offers.append(Offer(id=1, name="Offer Z", state="deleted"))

    assert await CatalogService(keitaro).search_offers("Offer Z") == []


async def test_offer_list_is_cached_for_a_short_time() -> None:
    """R-KT-07: the tracker returns the whole list on every call."""
    keitaro, clock = FakeKeitaro(), Clock()
    catalog = CatalogService(keitaro, offers_ttl=30, clock=clock)

    await catalog.search_offers("a")
    await catalog.search_offers("b")
    assert keitaro.calls["list_offers"] == 1

    clock.now = 31
    await catalog.search_offers("c")
    assert keitaro.calls["list_offers"] == 2


async def test_offer_is_looked_up_by_id() -> None:
    """R-CR-03."""
    catalog = CatalogService(FakeKeitaro())

    found = await catalog.get_offer(B)

    assert found is not None
    assert found.name == "Offer B"
    assert await catalog.get_offer(42) is None
