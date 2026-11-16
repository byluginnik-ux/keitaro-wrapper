from dataclasses import replace

import pytest

from app.keitaro.models import NewStream, Stream, StreamFilter, StreamOffer
from app.services.catalog import CatalogService
from app.services.creator import CreatorService, NewCampaignRequest
from app.services.errors import CampaignCreationError, KeitaroError, ValidationError
from app.services.models import OfferLink, Published
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from tests.fakes import A, FakeKeitaro
from tests.graphql.support import NOW, PREFIX

pytestmark = pytest.mark.anyio

REQUEST = NewCampaignRequest(
    name="test_bulygin_au_flexacil",
    country="au",
    offer_id=A,
    group_id=10332,
    traffic_source_id=836,
    domain_id=1813,
)
NEW_DOMAIN = replace(REQUEST, domain_id=None, new_domain_name="new.example.com")
WRITES = ("create_domain", "create_campaign", "create_stream")


@pytest.fixture
def keitaro() -> FakeKeitaro:
    return FakeKeitaro()


@pytest.fixture
def storage() -> Storage:
    return create_memory_storage()


@pytest.fixture
def creator(keitaro: FakeKeitaro, storage: Storage) -> CreatorService:
    return CreatorService(
        keitaro,
        CatalogService(keitaro),
        storage,
        name_prefix=PREFIX,
        clock=lambda: NOW,
        new_alias=lambda: "alias001",
    )


async def rejected(creator: CreatorService, request: NewCampaignRequest) -> dict[str, str]:
    with pytest.raises(ValidationError) as caught:
        await creator.create(request)
    return caught.value.fields


def wrote_nothing(keitaro: FakeKeitaro) -> bool:
    return not any(keitaro.calls[method] for method in WRITES)


@pytest.mark.parametrize("name", ["au_flexacil", "test_bulygin_", "  test_bulygin_  ", ""])
async def test_name_must_carry_the_prefix_and_something_after_it(
    creator: CreatorService, keitaro: FakeKeitaro, name: str
) -> None:
    """R-CR-01."""
    fields = await rejected(creator, replace(REQUEST, name=name))

    assert list(fields) == ["name"]
    assert wrote_nothing(keitaro)


async def test_unknown_country_is_rejected(creator: CreatorService, keitaro: FakeKeitaro) -> None:
    """R-CR-02."""
    fields = await rejected(creator, replace(REQUEST, country="zz"))

    assert list(fields) == ["country"]
    assert wrote_nothing(keitaro)


async def test_missing_references_are_reported_together(
    creator: CreatorService, keitaro: FakeKeitaro
) -> None:
    """R-CR-03: every wrong field is named in one answer."""
    request = replace(REQUEST, offer_id=1, group_id=2, traffic_source_id=3, domain_id=4)

    fields = await rejected(creator, request)

    assert set(fields) == {"offerId", "groupId", "trafficSourceId", "domainId"}
    assert wrote_nothing(keitaro)


@pytest.mark.parametrize(
    "request_",
    [replace(REQUEST, domain_id=None), replace(REQUEST, new_domain_name="new.example.com")],
    ids=["neither", "both"],
)
async def test_exactly_one_way_to_name_the_domain(
    creator: CreatorService, request_: NewCampaignRequest
) -> None:
    """R-CR-03, R-CR-10."""
    assert list(await rejected(creator, request_)) == ["domainId"]


async def test_campaign_gets_the_chosen_domain_group_and_source(
    creator: CreatorService, keitaro: FakeKeitaro
) -> None:
    """R-CR-04."""
    created = await creator.create(REQUEST)

    in_tracker = keitaro.campaigns[created.keitaro_id]
    assert in_tracker.name == "test_bulygin_au_flexacil"
    assert in_tracker.alias == "alias001"
    assert (in_tracker.domain_id, in_tracker.group_id, in_tracker.traffic_source_id) == (
        1813,
        10332,
        836,
    )


async def test_first_stream_sends_the_country_to_google(
    creator: CreatorService, keitaro: FakeKeitaro
) -> None:
    """R-CR-05, R-CR-02: the code travels in upper case."""
    created = await creator.create(REQUEST)

    assert keitaro.stream_requests[0] == NewStream(
        campaign_id=created.keitaro_id,
        name="Flow 1",
        position=1,
        kind="redirect",
        action_type="http",
        action_payload="https://google.com",
        filters=(StreamFilter(name="country", mode="accept", payload=("AU",)),),
    )


async def test_second_stream_sends_everyone_else_to_the_offer(
    creator: CreatorService, keitaro: FakeKeitaro
) -> None:
    """R-CR-06."""
    created = await creator.create(REQUEST)

    assert keitaro.stream_requests[1] == NewStream(
        campaign_id=created.keitaro_id,
        name="Flow 2",
        position=2,
        kind="landings",
        offers=(StreamOffer(offer_id=A, share=100),),
    )
    assert len(keitaro.stream_requests) == 2


class SecondStreamFails(FakeKeitaro):
    async def create_stream(self, stream: NewStream) -> Stream:
        if stream.position == 2:
            self.fail_on.add("create_stream")
        return await super().create_stream(stream)


@pytest.mark.parametrize("tracker", [FakeKeitaro(fail_on={"create_stream"}), SecondStreamFails()])
async def test_failed_stream_removes_the_campaign(tracker: FakeKeitaro, storage: Storage) -> None:
    """R-CR-07: no half-built campaign stays in the tracker or in our storage."""
    creator = CreatorService(tracker, CatalogService(tracker), storage, name_prefix=PREFIX)

    with pytest.raises(CampaignCreationError):
        await creator.create(REQUEST)

    assert tracker.calls["delete_campaign"] == 1
    assert tracker.campaigns == {}
    assert tracker.streams == {}
    assert await storage.campaigns.list_recent() == []


async def test_failed_cleanup_names_the_campaign_left_behind(storage: Storage) -> None:
    """R-CR-07: when even the removal fails, the user is told what to remove by hand."""
    tracker = FakeKeitaro(fail_on={"create_stream", "delete_campaign"})
    creator = CreatorService(tracker, CatalogService(tracker), storage, name_prefix=PREFIX)

    with pytest.raises(CampaignCreationError) as caught:
        await creator.create(REQUEST)

    (left_behind,) = tracker.campaigns
    assert str(left_behind) in str(caught.value)


async def test_created_campaign_and_streams_are_stored(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-CR-08."""
    created = await creator.create(REQUEST)

    assert await storage.campaigns.get(created.id) == created
    assert (created.name, created.alias, created.country) == (REQUEST.name, "alias001", "AU")
    assert (created.domain_id, created.group_id, created.traffic_source_id) == (1813, 10332, 836)
    assert created.created_at == NOW
    first, second = await storage.streams.list_by_campaign(created.id)
    tracker_first, tracker_second = await keitaro.list_campaign_streams(created.keitaro_id)
    assert (first.keitaro_id, first.name, first.kind, first.offers) == (
        tracker_first.id,
        "Flow 1",
        "redirect",
        (),
    )
    assert (second.keitaro_id, second.name, second.kind) == (
        tracker_second.id,
        "Flow 2",
        "landings",
    )
    assert second.offers == (OfferLink(A, "Offer A", 100, published=Published(100)),)
    assert second.dirty is False


async def test_success_is_written_to_the_journal(creator: CreatorService, storage: Storage) -> None:
    """R-CR-09."""
    created = await creator.create(REQUEST)

    (entry,) = await storage.audit.list_recent()
    assert (entry.action, entry.campaign_id, entry.created_at) == (
        "campaign.created",
        created.id,
        NOW,
    )
    assert entry.details["keitaro_id"] == created.keitaro_id
    assert entry.details["domain_created"] is False


async def test_failure_is_written_to_the_journal(storage: Storage) -> None:
    """R-CR-09."""
    tracker = FakeKeitaro(fail_on={"create_stream"})
    creator = CreatorService(tracker, CatalogService(tracker), storage, name_prefix=PREFIX)

    with pytest.raises(CampaignCreationError):
        await creator.create(REQUEST)

    (entry,) = await storage.audit.list_recent()
    assert entry.action == "campaign.create_failed"
    assert entry.details["name"] == REQUEST.name
    assert entry.details["rolled_back"] is True


async def test_new_domain_is_created_before_the_campaign(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-CR-10."""
    created = await creator.create(NEW_DOMAIN)

    new_domain = keitaro.domains[-1]
    assert new_domain.name == "new.example.com"
    assert keitaro.campaigns[created.keitaro_id].domain_id == new_domain.id
    assert created.domain_id == new_domain.id
    (entry,) = await storage.audit.list_recent()
    assert entry.details["domain_created"] is True


@pytest.mark.parametrize(
    "name",
    ["https://new.example.com", "new.example.com/path", "new example.com", "localhost", "-a.com"],
)
async def test_new_domain_must_be_a_bare_host_name(
    creator: CreatorService, keitaro: FakeKeitaro, name: str
) -> None:
    """R-CR-11."""
    fields = await rejected(creator, replace(NEW_DOMAIN, new_domain_name=name))

    assert list(fields) == ["newDomainName"]
    assert wrote_nothing(keitaro)


async def test_existing_domain_name_is_reused_in_any_case(
    creator: CreatorService, keitaro: FakeKeitaro
) -> None:
    """R-CR-11."""
    request = replace(NEW_DOMAIN, new_domain_name=" Tracker.Example.COM ")

    created = await creator.create(request)

    assert keitaro.calls["create_domain"] == 0
    assert created.domain_id == 1813


async def test_failed_domain_stops_before_the_campaign(storage: Storage) -> None:
    """R-CR-12."""
    tracker = FakeKeitaro(fail_on={"create_domain"})
    creator = CreatorService(tracker, CatalogService(tracker), storage, name_prefix=PREFIX)

    with pytest.raises(KeitaroError) as caught:
        await creator.create(NEW_DOMAIN)

    assert tracker.calls["create_campaign"] == 0
    assert getattr(caught.value, "created_domain", None) is None


async def test_created_domain_survives_a_failed_campaign(storage: Storage) -> None:
    """R-CR-12: the domain stays and the error says so."""
    tracker = FakeKeitaro(fail_on={"create_campaign"})
    creator = CreatorService(tracker, CatalogService(tracker), storage, name_prefix=PREFIX)

    with pytest.raises(CampaignCreationError) as caught:
        await creator.create(NEW_DOMAIN)

    assert caught.value.created_domain == tracker.domains[-1]
    assert tracker.domains[-1].name == "new.example.com"
    assert "new.example.com" in str(caught.value)


async def test_reused_domain_is_not_reported_as_created(storage: Storage) -> None:
    """R-CR-12 speaks only about a domain this operation created."""
    tracker = FakeKeitaro(fail_on={"create_campaign"})
    creator = CreatorService(tracker, CatalogService(tracker), storage, name_prefix=PREFIX)

    with pytest.raises(CampaignCreationError) as caught:
        await creator.create(REQUEST)

    assert caught.value.created_domain is None
