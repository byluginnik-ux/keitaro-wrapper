from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest

from app.services.catalog import CatalogService
from app.services.editor import EditorService
from app.services.errors import (
    OfferAlreadyInStreamError,
    OfferNotFoundError,
    ShareOverflowError,
    StreamConflictError,
    StreamNotFoundError,
    ValidationError,
)
from app.services.models import OfferLink, Published, Stream
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
from tests.fakes import shares as tracker_shares
from tests.graphql.support import NOW

pytestmark = pytest.mark.anyio

ACTIVE, REMOVED = OfferState.ACTIVE, OfferState.REMOVED
WRITES = ("replace_stream_offers", "create_stream", "create_campaign", "delete_campaign")


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


def shares(stream: Stream) -> dict[int, int]:
    return {link.offer_id: link.share for link in stream.offers}


def link(stream: Stream, offer_id: int) -> OfferLink:
    return next(item for item in stream.offers if item.offer_id == offer_id)


async def unchanged(storage: Storage, before: Stream) -> bool:
    return await storage.streams.get(before.id) == before


async def test_s2_added_offer_gets_an_equal_share(
    editor: EditorService, keitaro: FakeKeitaro, storage: Storage, stream: Stream
) -> None:
    """S2, R-ED-10."""
    after = await editor.add_offer(stream.id, D)

    assert shares(after) == {A: 25, B: 25, C: 25, D: 25}
    assert link(after, D) == OfferLink(D, "Offer D", 25)
    assert after.dirty
    assert await storage.streams.get(stream.id) == after
    assert len(keitaro.streams[stream.keitaro_id].offers) == 3
    assert not any(keitaro.calls[method] for method in WRITES)


async def test_offer_already_active_is_refused(
    editor: EditorService, storage: Storage, stream: Stream
) -> None:
    """R-ED-11."""
    with pytest.raises(OfferAlreadyInStreamError, match="Offer A"):
        await editor.add_offer(stream.id, A)

    assert await unchanged(storage, stream)


async def test_offer_unknown_to_the_tracker_is_refused(
    editor: EditorService, storage: Storage, stream: Stream
) -> None:
    """R-ED-10: offers are picked from the tracker's own list."""
    with pytest.raises(OfferNotFoundError):
        await editor.add_offer(stream.id, 999)

    assert await unchanged(storage, stream)


async def test_offers_do_not_go_into_a_redirect_stream(editor: EditorService) -> None:
    """R-ED-16."""
    redirect = (await editor.fetch(CAMPAIGN_ID)).streams[0]

    with pytest.raises(ValidationError) as caught:
        await editor.add_offer(redirect.id, A)

    assert list(caught.value.fields) == ["streamId"]


async def test_removed_offer_keeps_its_row_with_zero_share(
    editor: EditorService, stream: Stream
) -> None:
    """S5, R-ED-12, R-SH-02."""
    after = await editor.remove_offer(stream.id, B)

    assert link(after, B) == OfferLink(B, "Offer B", 0, state=REMOVED, published=Published(33))
    assert shares(after) == {A: 50, B: 0, C: 50}
    assert [item.offer_id for item in after.offers] == [A, B, C]
    assert after.dirty


async def test_removing_drops_the_pin(editor: EditorService, stream: Stream) -> None:
    """R-ED-12."""
    await editor.pin_share(stream.id, B, 20)

    after = await editor.remove_offer(stream.id, B)

    assert not link(after, B).pinned
    assert shares(after) == {A: 50, B: 0, C: 50}


async def test_removing_an_unpublished_offer_makes_it_disappear(
    editor: EditorService, stream: Stream
) -> None:
    """R-ED-12, R-ED-15: the draft is back to what is published."""
    await editor.add_offer(stream.id, D)

    after = await editor.remove_offer(stream.id, D)

    assert after == stream
    assert not after.dirty


async def test_removing_what_is_not_active_is_refused(
    editor: EditorService, stream: Stream
) -> None:
    """R-ED-12."""
    await editor.remove_offer(stream.id, B)

    with pytest.raises(OfferNotFoundError):
        await editor.remove_offer(stream.id, B)
    with pytest.raises(OfferNotFoundError):
        await editor.remove_offer(stream.id, D)


async def test_last_offer_can_be_removed(editor: EditorService, stream: Stream) -> None:
    """R-ED-12: an empty draft is allowed; publishing it is not (R-ED-23)."""
    for offer_id in (A, B, C):
        after = await editor.remove_offer(stream.id, offer_id)

    assert shares(after) == {A: 0, B: 0, C: 0}


async def test_brought_back_offer_returns_to_the_published_state(
    editor: EditorService, stream: Stream
) -> None:
    """S5, R-ED-13, R-ED-15."""
    await editor.remove_offer(stream.id, B)

    after = await editor.bring_back(stream.id, B)

    assert after == stream
    assert not after.dirty


async def test_adding_a_removed_offer_brings_it_back(editor: EditorService, stream: Stream) -> None:
    """R-ED-11."""
    await editor.remove_offer(stream.id, B)

    after = await editor.add_offer(stream.id, B)

    assert after == stream


async def test_bringing_back_what_is_not_removed_is_refused(
    editor: EditorService, stream: Stream
) -> None:
    """R-ED-13."""
    with pytest.raises(OfferAlreadyInStreamError):
        await editor.bring_back(stream.id, A)
    with pytest.raises(OfferNotFoundError):
        await editor.bring_back(stream.id, D)


async def test_s4_cancel_returns_to_the_published_snapshot(
    editor: EditorService, storage: Storage, stream: Stream
) -> None:
    """S4, R-ED-14."""
    await editor.add_offer(stream.id, D)
    await editor.remove_offer(stream.id, A)
    await editor.pin_share(stream.id, B, 70)

    after = await editor.cancel(stream.id)

    assert after == stream
    assert not after.dirty
    assert await storage.streams.get(stream.id) == stream


async def test_s7_pinned_share_holds_through_changes(storage: Storage) -> None:
    """S7, R-SH-03, R-SH-04, R-SH-06. Given: A, B, C active and D removed."""
    keitaro = tracker_with_campaign((A, 25), (B, 25), (C, 25), (D, 25))
    editor = EditorService(keitaro, CatalogService(keitaro), storage)
    await editor.fetch(CAMPAIGN_ID)
    current = keitaro.streams[OFFERS_STREAM_ID]
    keitaro.streams[OFFERS_STREAM_ID] = current.model_copy(
        update={"offers": tracker_shares((A, 34), (B, 33), (C, 33))}
    )
    stream = (await editor.fetch(CAMPAIGN_ID)).streams[1]
    assert link(stream, D).state is REMOVED

    pinned = await editor.pin_share(stream.id, C, 25)
    assert shares(pinned) == {A: 38, B: 37, C: 25, D: 0}
    assert link(pinned, C).pinned

    with_d = await editor.bring_back(stream.id, D)
    assert shares(with_d) == {A: 25, B: 25, C: 25, D: 25}

    without_d = await editor.remove_offer(stream.id, D)
    assert shares(without_d) == {A: 38, B: 37, C: 25, D: 0}


async def test_s8_overflow_is_refused_and_changes_nothing(
    editor: EditorService, storage: Storage, stream: Stream
) -> None:
    """S8, R-SH-08."""
    before = await editor.pin_share(stream.id, A, 60)

    with pytest.raises(ShareOverflowError):
        await editor.pin_share(stream.id, B, 50)

    assert await unchanged(storage, before)
    assert shares(before) == {A: 60, B: 20, C: 20}


@pytest.mark.parametrize("share", [0, -5, 101])
async def test_pinned_share_is_between_1_and_100(
    editor: EditorService, storage: Storage, stream: Stream, share: int
) -> None:
    """R-SH-06."""
    with pytest.raises(ValidationError) as caught:
        await editor.pin_share(stream.id, A, share)

    assert list(caught.value.fields) == ["share"]
    assert await unchanged(storage, stream)


async def test_pinning_needs_an_active_offer(editor: EditorService, stream: Stream) -> None:
    """R-SH-06."""
    await editor.remove_offer(stream.id, B)

    with pytest.raises(OfferNotFoundError):
        await editor.pin_share(stream.id, B, 10)


async def test_pinning_the_current_value_does_not_make_a_draft(
    editor: EditorService, stream: Stream
) -> None:
    """R-ED-15: a pin is ours alone, the tracker would get the same shares."""
    after = await editor.pin_share(stream.id, A, 34)

    assert link(after, A).pinned
    assert shares(after) == {A: 34, B: 33, C: 33}
    assert not after.dirty


async def test_unpinning_lets_the_offer_be_recalculated(
    editor: EditorService, stream: Stream
) -> None:
    """R-SH-07."""
    await editor.pin_share(stream.id, A, 60)

    after = await editor.unpin_share(stream.id, A)

    assert after == stream


async def test_unknown_stream_is_refused(editor: EditorService) -> None:
    missing = uuid4()
    actions = [
        lambda: editor.add_offer(missing, A),
        lambda: editor.remove_offer(missing, A),
        lambda: editor.bring_back(missing, A),
        lambda: editor.pin_share(missing, A, 10),
        lambda: editor.unpin_share(missing, A),
        lambda: editor.cancel(missing),
    ]

    for action in actions:
        with pytest.raises(StreamNotFoundError):
            await action()


type Action = Callable[[EditorService, Stream, int], Awaitable[Stream]]

ACTIONS: dict[str, Action] = {
    "add": lambda editor, stream, seen: editor.add_offer(stream.id, D, expected=seen),
    "remove": lambda editor, stream, seen: editor.remove_offer(stream.id, B, expected=seen),
    "pin": lambda editor, stream, seen: editor.pin_share(stream.id, A, 50, expected=seen),
    "cancel": lambda editor, stream, seen: editor.cancel(stream.id, expected=seen),
}


async def test_action_on_the_version_the_user_saw_is_applied(
    editor: EditorService, stream: Stream
) -> None:
    """R-CC-06, R-CC-01."""
    added = await editor.add_offer(stream.id, D, expected=stream.version)
    pinned = await editor.pin_share(stream.id, A, 50, expected=added.version)

    assert (added.version, pinned.version) == (stream.version + 1, stream.version + 2)
    assert shares(pinned) == {A: 50, B: 17, C: 17, D: 16}


@pytest.mark.parametrize("action", sorted(ACTIONS))
async def test_action_on_an_outdated_stream_is_refused_with_the_current_one(
    editor: EditorService, storage: Storage, keitaro: FakeKeitaro, stream: Stream, action: str
) -> None:
    """R-CC-06: another window removed C after this one loaded the stream."""
    current = await editor.remove_offer(stream.id, C)

    with pytest.raises(StreamConflictError) as refusal:
        await ACTIONS[action](editor, stream, stream.version)

    assert refusal.value.current == current
    assert refusal.value.current is not None
    assert refusal.value.current.version == current.version
    assert await unchanged(storage, current)
    assert all(keitaro.calls[write] == 0 for write in WRITES)


async def test_unpin_and_bring_back_check_the_version_too(
    editor: EditorService, stream: Stream
) -> None:
    """R-CC-06."""
    pinned = await editor.pin_share(stream.id, A, 50)
    removed = await editor.remove_offer(stream.id, C)

    with pytest.raises(StreamConflictError):
        await editor.unpin_share(stream.id, A, expected=pinned.version)
    with pytest.raises(StreamConflictError):
        await editor.bring_back(stream.id, C, expected=pinned.version)
    restored = await editor.bring_back(stream.id, C, expected=removed.version)

    assert link(restored, C).state is ACTIVE
