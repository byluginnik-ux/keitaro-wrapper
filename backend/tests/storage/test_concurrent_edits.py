"""Races of the editor, run on every storage adapter (R-CC-03…05)."""

import asyncio
from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

import pytest

from app.keitaro import models as tracker
from app.services.catalog import CatalogService
from app.services.editor import EditorService
from app.services.errors import DraftNotPublishedError, StreamConflictError
from app.services.models import Stream
from app.services.shares import TOTAL, OfferState
from app.storage.ports import Storage, StreamRepository
from tests.fakes import CAMPAIGN_ID, B, C, D, FakeKeitaro, tracker_with_campaign
from tests.graphql.support import NOW

pytestmark = pytest.mark.anyio

WRITERS = 12


class Pausing:
    """Give way after every read, as a real database does, so writers interleave."""

    def __init__(self, inner: StreamRepository) -> None:
        self._inner = inner

    async def get(self, stream_id: UUID) -> Stream | None:
        found = await self._inner.get(stream_id)
        await asyncio.sleep(0)
        return found

    async def list_by_campaign(self, campaign_id: UUID) -> list[Stream]:
        found = await self._inner.list_by_campaign(campaign_id)
        await asyncio.sleep(0)
        return found

    async def save(self, stream: Stream) -> Stream:
        return await self._inner.save(stream)

    async def save_all(self, streams: Sequence[Stream]) -> list[Stream]:
        return await self._inner.save_all(streams)

    async def delete(self, stream_id: UUID) -> None:
        await self._inner.delete(stream_id)


@pytest.fixture
def keitaro() -> FakeKeitaro:
    return tracker_with_campaign()


@pytest.fixture
def editor(keitaro: FakeKeitaro, storage: Storage) -> EditorService:
    interleaved = replace(storage, streams=Pausing(storage.streams))
    return EditorService(keitaro, CatalogService(keitaro), interleaved, clock=lambda: NOW)


async def test_simultaneous_edits_are_applied_or_refused_never_lost(
    editor: EditorService, storage: Storage
) -> None:
    """R-CC-03: the version counts exactly the edits that were answered with success."""
    stream = (await editor.fetch(CAMPAIGN_ID)).streams[1]
    edits = [
        edit
        for share in range(40, 40 + WRITERS // 3)
        for edit in (
            editor.add_offer(stream.id, D),
            editor.remove_offer(stream.id, B),
            editor.pin_share(stream.id, C, share),
        )
    ]

    results = await asyncio.gather(*edits, return_exceptions=True)

    applied = [item for item in results if isinstance(item, Stream)]
    conflicts = [item for item in results if isinstance(item, StreamConflictError)]
    stored = await storage.streams.get(stream.id)
    assert stored is not None
    assert applied
    assert conflicts
    assert len({item.version for item in applied}) == len(applied)
    assert stored.version == stream.version + len(applied)
    assert stored == max(applied, key=lambda item: item.version)
    active = [link.share for link in stored.offers if link.state is OfferState.ACTIVE]
    assert sum(active) == TOTAL


async def test_simultaneous_loads_agree_on_one_campaign(
    keitaro: FakeKeitaro, storage: Storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """R-CC-04: neither load fails, both name the same campaign and streams."""
    editor = EditorService(keitaro, CatalogService(keitaro), storage, clock=lambda: NOW)
    answer = keitaro.get_campaign

    async def slow(campaign_id: int) -> tracker.Campaign:
        await asyncio.sleep(0.01)
        return await answer(campaign_id)

    monkeypatch.setattr(keitaro, "get_campaign", slow)

    first, second = await asyncio.gather(editor.fetch(CAMPAIGN_ID), editor.fetch(CAMPAIGN_ID))

    assert first.campaign == second.campaign
    assert [stream.id for stream in first.streams] == [stream.id for stream in second.streams]
    assert await storage.campaigns.list_recent() == [first.campaign]
    assert len(await storage.streams.list_by_campaign(first.campaign.id)) == len(first.streams)


async def test_load_does_not_overwrite_a_draft_made_meanwhile(
    editor: EditorService,
    keitaro: FakeKeitaro,
    storage: Storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """R-CC-05: the draft appears after the check and before the write."""
    stream = (await editor.fetch(CAMPAIGN_ID)).streams[1]
    answer = keitaro.list_campaign_streams
    drafts: list[Stream] = []

    async def edited_meanwhile(campaign_id: int) -> list[tracker.Stream]:
        if not drafts:
            drafts.append(await editor.add_offer(stream.id, D))
        return await answer(campaign_id)

    monkeypatch.setattr(keitaro, "list_campaign_streams", edited_meanwhile)

    with pytest.raises(DraftNotPublishedError):
        await editor.fetch(CAMPAIGN_ID)

    assert await storage.streams.get(stream.id) == drafts[0]
