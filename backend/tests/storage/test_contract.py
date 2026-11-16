from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.services.models import AuditEntry, Campaign, OfferLink, Published, Stream
from app.services.shares import OfferState
from app.storage.ports import Storage
from tests.fakes import A, B, C

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)


def campaign(keitaro_id: int = 93212, *, minutes: int = 0) -> Campaign:
    return Campaign(
        id=uuid4(),
        keitaro_id=keitaro_id,
        name=f"test_bulygin_{keitaro_id}",
        alias=f"alias{keitaro_id}",
        created_at=NOW + timedelta(minutes=minutes),
        country="AU",
        domain_id=1813,
        group_id=10332,
        traffic_source_id=836,
    )


def offers_stream(campaign_id: UUID, keitaro_id: int = 564221, position: int = 2) -> Stream:
    return Stream(
        id=uuid4(),
        campaign_id=campaign_id,
        keitaro_id=keitaro_id,
        name="Flow 2",
        position=position,
        kind="landings",
        offers=(
            OfferLink(A, "Offer A", 34, published=Published(34)),
            OfferLink(B, "Offer B", 33, pinned=True, published=Published(33, pinned=True)),
            OfferLink(C, "Offer C", 33),
        ),
    )


async def test_campaign_is_found_by_both_ids(storage: Storage) -> None:
    """R-CR-08."""
    saved = campaign()
    await storage.campaigns.add(saved)

    assert await storage.campaigns.get(saved.id) == saved
    assert await storage.campaigns.get_by_keitaro_id(93212) == saved


async def test_unknown_campaign_is_none(storage: Storage) -> None:
    assert await storage.campaigns.get(uuid4()) is None
    assert await storage.campaigns.get_by_keitaro_id(1) is None


async def test_campaigns_are_listed_newest_first(storage: Storage) -> None:
    old, new = campaign(1, minutes=0), campaign(2, minutes=5)
    await storage.campaigns.add(old)
    await storage.campaigns.add(new)

    assert await storage.campaigns.list_recent() == [new, old]


async def test_stream_round_trips_with_offers_in_order(storage: Storage) -> None:
    """R-ED-03, R-SH-05: order, pins and published snapshots survive."""
    owner = campaign()
    await storage.campaigns.add(owner)
    stream = offers_stream(owner.id)

    await storage.streams.save(stream)

    assert await storage.streams.get(stream.id) == stream


async def test_unpublished_offer_keeps_having_no_snapshot(storage: Storage) -> None:
    """R-ED-14 depends on telling never-published offers apart."""
    owner = campaign()
    await storage.campaigns.add(owner)
    stream = offers_stream(owner.id)
    await storage.streams.save(stream)

    loaded = await storage.streams.get(stream.id)

    assert loaded is not None
    assert loaded.offers[2].published is None
    assert loaded.dirty is True


async def test_saving_again_replaces_the_offers(storage: Storage) -> None:
    """R-ST-05: a stream is stored as a whole."""
    owner = campaign()
    await storage.campaigns.add(owner)
    stream = offers_stream(owner.id)
    await storage.streams.save(stream)
    removed = replace(stream.offers[0], share=0, state=OfferState.REMOVED)
    changed = replace(stream, name="Flow 2 renamed", offers=(removed, stream.offers[1]))

    await storage.streams.save(changed)

    assert await storage.streams.get(stream.id) == changed


async def test_streams_of_a_campaign_come_by_position(storage: Storage) -> None:
    """R-ED-01."""
    owner, other = campaign(1), campaign(2)
    await storage.campaigns.add(owner)
    await storage.campaigns.add(other)
    second = offers_stream(owner.id, keitaro_id=20, position=2)
    first = Stream(uuid4(), owner.id, 10, "Flow 1", 1, "redirect")
    foreign = offers_stream(other.id, keitaro_id=30)

    await storage.streams.save_all([second, first, foreign])

    assert await storage.streams.list_by_campaign(owner.id) == [first, second]


async def test_stream_without_offers_is_kept(storage: Storage) -> None:
    """R-ED-02."""
    owner = campaign()
    await storage.campaigns.add(owner)
    redirect = Stream(uuid4(), owner.id, 564220, "Flow 1", 1, "redirect")

    await storage.streams.save(redirect)

    assert await storage.streams.get(redirect.id) == redirect


async def test_save_all_is_all_or_nothing(storage: Storage) -> None:
    """R-ST-05: a stream of an unknown campaign rejects the whole batch."""
    owner = campaign()
    await storage.campaigns.add(owner)
    good = offers_stream(owner.id)
    orphan = offers_stream(uuid4(), keitaro_id=999)

    with pytest.raises(LookupError):
        await storage.streams.save_all([good, orphan])

    assert await storage.streams.list_by_campaign(owner.id) == []


async def test_deleted_stream_is_gone_with_its_offers(storage: Storage) -> None:
    """R-ED-08."""
    owner = campaign()
    await storage.campaigns.add(owner)
    kept = Stream(uuid4(), owner.id, 564220, "Flow 1", 1, "redirect")
    gone = offers_stream(owner.id)
    await storage.streams.save_all([kept, gone])

    await storage.streams.delete(gone.id)
    await storage.streams.delete(uuid4())

    assert await storage.streams.get(gone.id) is None
    assert await storage.streams.list_by_campaign(owner.id) == [kept]
    await storage.streams.save(gone)
    assert await storage.streams.get(gone.id) == gone


async def test_unknown_stream_is_none(storage: Storage) -> None:
    assert await storage.streams.get(uuid4()) is None


async def test_audit_entries_come_newest_first_with_details(storage: Storage) -> None:
    """R-CR-09, R-ED-24."""
    owner = campaign()
    await storage.campaigns.add(owner)
    created = AuditEntry(uuid4(), "campaign.created", NOW, owner.id, None, {"keitaro_id": 93212})
    pushed = AuditEntry(
        uuid4(),
        "stream.pushed",
        NOW + timedelta(minutes=1),
        owner.id,
        None,
        {"after": [{"offer_id": A, "share": 100}], "ok": True, "note": None},
    )
    await storage.audit.record(created)
    await storage.audit.record(pushed)

    assert await storage.audit.list_recent() == [pushed, created]
    assert await storage.audit.list_recent(limit=1) == [pushed]
