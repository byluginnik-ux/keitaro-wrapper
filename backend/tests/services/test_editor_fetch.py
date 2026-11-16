from dataclasses import replace

import pytest

from app.keitaro.models import Stream as TrackerStream
from app.services.catalog import CatalogService
from app.services.editor import EditorService
from app.services.errors import CampaignNotFoundError, DraftNotPublishedError, KeitaroError
from app.services.models import OfferLink, Published, Stream
from app.services.shares import OfferState
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from tests.fakes import (
    CAMPAIGN_ID,
    OFFERS_STREAM_ID,
    REDIRECT_STREAM_ID,
    A,
    B,
    C,
    D,
    FakeKeitaro,
    shares,
    tracker_with_campaign,
)
from tests.graphql.support import NOW

pytestmark = pytest.mark.anyio

REMOVED = Published(0, OfferState.REMOVED)


@pytest.fixture
def keitaro() -> FakeKeitaro:
    return tracker_with_campaign()


@pytest.fixture
def storage() -> Storage:
    return create_memory_storage()


@pytest.fixture
def editor(keitaro: FakeKeitaro, storage: Storage) -> EditorService:
    return EditorService(keitaro, CatalogService(keitaro), storage, clock=lambda: NOW)


def set_offers(keitaro: FakeKeitaro, *pairs: tuple[int, int]) -> None:
    """Change the stream behind our back, as an operator would in the tracker's admin."""
    current = keitaro.streams[OFFERS_STREAM_ID]
    keitaro.streams[OFFERS_STREAM_ID] = current.model_copy(update={"offers": shares(*pairs)})


def summary(stream: Stream) -> list[tuple[int, int, OfferState]]:
    return [(link.offer_id, link.share, link.state) for link in stream.offers]


async def offers_stream(editor: EditorService) -> Stream:
    fetched = await editor.fetch(CAMPAIGN_ID)
    return fetched.streams[1]


async def test_s1_both_streams_are_loaded_clean(editor: EditorService) -> None:
    """S1, R-ED-02, R-ED-03."""
    fetched = await editor.fetch(CAMPAIGN_ID)

    first, second = fetched.streams
    assert (first.keitaro_id, first.name, first.kind, first.offers) == (
        REDIRECT_STREAM_ID,
        "Flow 1",
        "redirect",
        (),
    )
    assert (second.keitaro_id, second.name, second.kind) == (OFFERS_STREAM_ID, "Flow 2", "landings")
    assert second.offers == (
        OfferLink(A, "Offer A", 34, published=Published(34)),
        OfferLink(B, "Offer B", 33, published=Published(33)),
        OfferLink(C, "Offer C", 33, published=Published(33)),
    )
    assert not first.dirty
    assert not second.dirty


async def test_loaded_streams_are_stored(editor: EditorService, storage: Storage) -> None:
    """R-ED-01."""
    fetched = await editor.fetch(CAMPAIGN_ID)

    assert await storage.streams.list_by_campaign(fetched.campaign.id) == fetched.streams
    assert await editor.streams(fetched.campaign.id) == fetched.streams
    assert await editor.campaign(fetched.campaign.id) == fetched.campaign
    assert await editor.campaigns() == [fetched.campaign]


async def test_campaign_made_elsewhere_is_adopted_once(
    editor: EditorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-ED-07."""
    first = await editor.fetch(CAMPAIGN_ID)
    second = await editor.fetch(CAMPAIGN_ID)

    assert (first.campaign.keitaro_id, first.campaign.name, first.campaign.alias) == (
        CAMPAIGN_ID,
        "test_bulygin_sample",
        "sample",
    )
    assert first.campaign.created_at == NOW
    assert second.campaign == first.campaign
    assert await storage.campaigns.list_recent() == [first.campaign]
    assert [stream.id for stream in second.streams] == [stream.id for stream in first.streams]
    assert keitaro.calls["get_campaign"] == 1


async def test_unknown_campaign_is_refused(editor: EditorService, storage: Storage) -> None:
    """R-ED-07."""
    with pytest.raises(CampaignNotFoundError):
        await editor.fetch(404404)

    assert await storage.campaigns.list_recent() == []


async def test_campaign_deleted_in_the_tracker_is_reported_as_missing(
    editor: EditorService, keitaro: FakeKeitaro
) -> None:
    """R-ED-07: the tracker answers 404 for the streams of a deleted campaign."""
    await editor.fetch(CAMPAIGN_ID)

    async def missing(_campaign_id: int) -> list[TrackerStream]:
        message = "Keitaro ответил 404"
        raise KeitaroError(message, 404)

    keitaro.list_campaign_streams = missing  # type: ignore[method-assign]

    with pytest.raises(CampaignNotFoundError):
        await editor.fetch(CAMPAIGN_ID)


async def test_other_tracker_failures_stay_tracker_failures(storage: Storage) -> None:
    """R-KT-02."""
    keitaro = tracker_with_campaign()
    keitaro.fail_on.add("list_campaign_streams")
    editor = EditorService(keitaro, CatalogService(keitaro), storage)

    with pytest.raises(KeitaroError) as caught:
        await editor.fetch(CAMPAIGN_ID)

    assert not isinstance(caught.value, CampaignNotFoundError)


async def test_shares_that_do_not_sum_to_100_are_taken_as_they_are(storage: Storage) -> None:
    """R-KT-05."""
    keitaro = tracker_with_campaign((A, 50), (B, 20))
    editor = EditorService(keitaro, CatalogService(keitaro), storage)

    stream = await offers_stream(editor)

    assert summary(stream) == [(A, 50, OfferState.ACTIVE), (B, 20, OfferState.ACTIVE)]
    assert not stream.dirty


async def test_s6_offers_removed_in_the_tracker_become_removed(storage: Storage) -> None:
    """S6, R-ED-04."""
    keitaro = tracker_with_campaign((A, 25), (B, 25), (C, 25), (D, 25))
    editor = EditorService(keitaro, CatalogService(keitaro), storage)
    await editor.fetch(CAMPAIGN_ID)
    set_offers(keitaro, (A, 50), (B, 50))

    stream = await offers_stream(editor)

    assert stream.offers == (
        OfferLink(A, "Offer A", 50, published=Published(50)),
        OfferLink(B, "Offer B", 50, published=Published(50)),
        OfferLink(C, "Offer C", 0, state=OfferState.REMOVED, published=REMOVED),
        OfferLink(D, "Offer D", 0, state=OfferState.REMOVED, published=REMOVED),
    )
    assert not stream.dirty


async def test_offer_added_in_the_tracker_appears_with_its_name(
    editor: EditorService, keitaro: FakeKeitaro
) -> None:
    """R-ED-03."""
    await editor.fetch(CAMPAIGN_ID)
    set_offers(keitaro, (A, 25), (B, 25), (C, 25), (D, 25))

    stream = await offers_stream(editor)

    assert stream.offers[3] == OfferLink(D, "Offer D", 25, published=Published(25))


async def test_offer_missing_from_the_catalog_still_gets_a_label(storage: Storage) -> None:
    """R-ED-03: an archived offer may still sit in a stream."""
    keitaro = tracker_with_campaign((A, 60), (999, 40))
    editor = EditorService(keitaro, CatalogService(keitaro), storage)

    stream = await offers_stream(editor)

    assert stream.offers[1].name == "Оффер 999"


async def pinned_b(editor: EditorService, storage: Storage) -> Stream:
    """Pin B at its published 33%, as a publish would leave it."""
    stream = await offers_stream(editor)
    a, b, c = stream.offers
    pinned = replace(b, pinned=True, published=Published(33, pinned=True))
    saved = replace(stream, offers=(a, pinned, c))
    await storage.streams.save(saved)
    return saved


async def test_pin_survives_when_the_tracker_share_is_the_same(
    editor: EditorService, storage: Storage
) -> None:
    """R-ED-05."""
    before = await pinned_b(editor, storage)

    stream = await offers_stream(editor)

    assert stream == before
    assert stream.offers[1].pinned


async def test_pin_is_dropped_when_the_tracker_share_differs(
    editor: EditorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-ED-05."""
    await pinned_b(editor, storage)
    set_offers(keitaro, (A, 30), (B, 40), (C, 30))

    stream = await offers_stream(editor)

    assert stream.offers[1] == OfferLink(B, "Offer B", 40, published=Published(40))
    assert not stream.dirty


async def test_fetch_is_refused_while_a_draft_exists(
    editor: EditorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-ED-06."""
    stream = await offers_stream(editor)
    draft = replace(stream, offers=(*stream.offers, OfferLink(D, "Offer D", 25)))
    await storage.streams.save(draft)
    calls_before = keitaro.calls["list_campaign_streams"]

    with pytest.raises(DraftNotPublishedError, match="Flow 2"):
        await editor.fetch(CAMPAIGN_ID)

    assert keitaro.calls["list_campaign_streams"] == calls_before
    assert await storage.streams.get(stream.id) == draft


async def test_stream_gone_from_the_tracker_is_forgotten(
    editor: EditorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-ED-08."""
    first = await editor.fetch(CAMPAIGN_ID)
    del keitaro.streams[REDIRECT_STREAM_ID]

    second = await editor.fetch(CAMPAIGN_ID)

    assert [stream.keitaro_id for stream in second.streams] == [OFFERS_STREAM_ID]
    assert await storage.streams.get(first.streams[0].id) is None


async def test_stream_added_in_the_tracker_is_adopted(
    editor: EditorService, keitaro: FakeKeitaro
) -> None:
    """R-ED-01."""
    await editor.fetch(CAMPAIGN_ID)
    keitaro.streams[7] = keitaro.streams[OFFERS_STREAM_ID].model_copy(
        update={"id": 7, "name": "Flow 3", "position": 3, "offers": shares((D, 100))}
    )

    fetched = await editor.fetch(CAMPAIGN_ID)

    assert [stream.name for stream in fetched.streams] == ["Flow 1", "Flow 2", "Flow 3"]
    assert summary(fetched.streams[2]) == [(D, 100, OfferState.ACTIVE)]


async def test_renamed_stream_keeps_its_identity(
    editor: EditorService, keitaro: FakeKeitaro
) -> None:
    """R-ED-01."""
    before = await offers_stream(editor)
    keitaro.streams[OFFERS_STREAM_ID] = keitaro.streams[OFFERS_STREAM_ID].model_copy(
        update={"name": "Offers"}
    )

    after = await offers_stream(editor)

    assert (after.id, after.name) == (before.id, "Offers")


async def test_fetch_is_written_to_the_journal(editor: EditorService, storage: Storage) -> None:
    """R-ED-24 speaks of pushes; a fetch is journaled the same way."""
    fetched = await editor.fetch(CAMPAIGN_ID)

    (entry,) = await storage.audit.list_recent()
    assert (entry.action, entry.campaign_id) == ("streams.fetched", fetched.campaign.id)
    assert entry.details["streams"] == 2
