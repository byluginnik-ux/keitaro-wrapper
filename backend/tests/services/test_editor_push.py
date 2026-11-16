from uuid import uuid4

import pytest

from app.keitaro.models import StreamOffer
from app.services.catalog import CatalogService
from app.services.editor import EditorService
from app.services.errors import EmptyStreamError, KeitaroError, StreamNotFoundError
from app.services.models import AuditEntry, OfferLink, Published, Stream
from app.services.shares import OfferState
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from tests.fakes import (
    CAMPAIGN_ID,
    OFFERS_STREAM_ID,
    A,
    B,
    C,
    D,
    FakeKeitaro,
    tracker_with_campaign,
)
from tests.graphql.support import NOW

pytestmark = pytest.mark.anyio

REMOVED = OfferState.REMOVED


@pytest.fixture
def keitaro() -> FakeKeitaro:
    return tracker_with_campaign()


@pytest.fixture
def storage() -> Storage:
    return create_memory_storage()


@pytest.fixture
def editor(keitaro: FakeKeitaro, storage: Storage) -> EditorService:
    return EditorService(keitaro, CatalogService(keitaro), storage, clock=lambda: NOW)


@pytest.fixture
async def stream(editor: EditorService) -> Stream:
    """Scenario S1: A 34, B 33, C 33, nothing pending."""
    fetched = await editor.fetch(CAMPAIGN_ID)
    return fetched.streams[1]


def in_tracker(keitaro: FakeKeitaro) -> list[tuple[int, int]]:
    return [(offer.offer_id, offer.share) for offer in keitaro.streams[OFFERS_STREAM_ID].offers]


async def last_publication(storage: Storage) -> AuditEntry:
    entries = await storage.audit.list_recent()
    return next(entry for entry in entries if entry.action.startswith("stream."))


async def test_s3_draft_reaches_the_tracker(
    editor: EditorService, keitaro: FakeKeitaro, storage: Storage, stream: Stream
) -> None:
    """S3, R-ED-20, R-ED-21."""
    await editor.add_offer(stream.id, D)

    after = await editor.push(stream.id)

    assert in_tracker(keitaro) == [(A, 25), (B, 25), (C, 25), (D, 25)]
    assert not after.dirty
    assert after.offers[3] == OfferLink(D, "Offer D", 25, published=Published(25))
    assert all(link.published == Published(25) for link in after.offers)
    assert await storage.streams.get(stream.id) == after


async def test_s5_removed_offer_leaves_the_tracker_and_can_return(
    editor: EditorService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """S5, R-ED-20, R-ED-21."""
    await editor.add_offer(stream.id, D)
    await editor.push(stream.id)

    removed = await editor.remove_offer(stream.id, B)
    assert [link.share for link in removed.offers] == [34, 0, 33, 33]
    assert removed.dirty

    published = await editor.push(stream.id)
    assert in_tracker(keitaro) == [(A, 34), (C, 33), (D, 33)]
    assert published.offers[1] == OfferLink(
        B, "Offer B", 0, state=REMOVED, published=Published(0, REMOVED)
    )
    assert not published.dirty

    await editor.bring_back(stream.id, B)
    await editor.push(stream.id)
    assert sorted(in_tracker(keitaro)) == [(A, 25), (B, 25), (C, 25), (D, 25)]


async def test_only_what_the_tracker_needs_is_sent(
    editor: EditorService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """R-ED-20: active offers in our order, each with its share."""
    await editor.remove_offer(stream.id, A)
    await editor.add_offer(stream.id, D)

    await editor.push(stream.id)

    assert keitaro.streams[OFFERS_STREAM_ID].offers == (
        StreamOffer(offer_id=B, share=34),
        StreamOffer(offer_id=C, share=33),
        StreamOffer(offer_id=D, share=33),
    )
    assert keitaro.calls["replace_stream_offers"] == 1


async def test_pin_becomes_part_of_the_published_snapshot(
    editor: EditorService, stream: Stream
) -> None:
    """R-ED-21, R-ED-14: a later cancel keeps the pin that was published."""
    await editor.pin_share(stream.id, C, 25)
    published = await editor.push(stream.id)
    await editor.add_offer(stream.id, D)

    cancelled = await editor.cancel(stream.id)

    assert published.offers[2].published == Published(25, pinned=True)
    assert cancelled == published


async def test_tracker_failure_keeps_the_draft(
    editor: EditorService, keitaro: FakeKeitaro, storage: Storage, stream: Stream
) -> None:
    """R-ED-22."""
    draft = await editor.add_offer(stream.id, D)
    keitaro.fail_on.add("replace_stream_offers")

    with pytest.raises(KeitaroError, match="replace_stream_offers failed"):
        await editor.push(stream.id)

    assert await storage.streams.get(stream.id) == draft
    assert draft.dirty
    assert in_tracker(keitaro) == [(A, 34), (B, 33), (C, 33)]


async def test_stream_without_active_offers_is_not_published(
    editor: EditorService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """R-ED-23."""
    for offer_id in (A, B, C):
        await editor.remove_offer(stream.id, offer_id)

    with pytest.raises(EmptyStreamError, match="Flow 2"):
        await editor.push(stream.id)

    assert keitaro.calls["replace_stream_offers"] == 0


async def test_clean_stream_is_not_sent_again(
    editor: EditorService, keitaro: FakeKeitaro, stream: Stream
) -> None:
    """R-ED-15: nothing differs from the tracker, so there is nothing to publish."""
    after = await editor.push(stream.id)

    assert after == stream
    assert keitaro.calls["replace_stream_offers"] == 0


async def test_publication_is_journaled_with_before_and_after(
    editor: EditorService, storage: Storage, stream: Stream
) -> None:
    """R-ED-24."""
    await editor.remove_offer(stream.id, C)
    await editor.add_offer(stream.id, D)

    await editor.push(stream.id)

    entry = await last_publication(storage)
    assert (entry.action, entry.stream_id, entry.campaign_id) == (
        "stream.pushed",
        stream.id,
        stream.campaign_id,
    )
    assert entry.details["before"] == [
        {"offer_id": A, "share": 34},
        {"offer_id": B, "share": 33},
        {"offer_id": C, "share": 33},
    ]
    assert entry.details["after"] == [
        {"offer_id": A, "share": 34},
        {"offer_id": B, "share": 33},
        {"offer_id": D, "share": 33},
    ]


async def test_failed_publication_is_journaled_too(
    editor: EditorService, keitaro: FakeKeitaro, storage: Storage, stream: Stream
) -> None:
    """R-ED-24."""
    await editor.add_offer(stream.id, D)
    keitaro.fail_on.add("replace_stream_offers")

    with pytest.raises(KeitaroError):
        await editor.push(stream.id)

    entry = await last_publication(storage)
    assert entry.action == "stream.push_failed"
    assert entry.details["error"] == "Keitaro: replace_stream_offers failed"


async def test_unknown_stream_is_refused(editor: EditorService) -> None:
    with pytest.raises(StreamNotFoundError):
        await editor.push(uuid4())
