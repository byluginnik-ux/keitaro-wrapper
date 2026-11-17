from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from http import HTTPStatus
from uuid import UUID, uuid4

from app.keitaro import models as tracker
from app.keitaro.gateway import KeitaroGateway
from app.services.catalog import CatalogService
from app.services.creator import utc_now
from app.services.errors import (
    CampaignNotFoundError,
    DraftNotPublishedError,
    EmptyStreamError,
    KeitaroError,
    OfferAlreadyInStreamError,
    OfferNotFoundError,
    StreamConflictError,
    StreamNotFoundError,
    ValidationError,
)
from app.services.models import (
    AuditEntry,
    Campaign,
    Details,
    OfferLink,
    Published,
    Stream,
    campaign_uuid,
    stream_uuid,
)
from app.services.shares import TOTAL, OfferShare, OfferState, recalculate
from app.storage.errors import StorageConflictError
from app.storage.ports import Storage

ACTIVE = "active"
OFFERS_KIND = "landings"
MIN_PINNED = 1
FETCH_ATTEMPTS = 3


def _find(stream: Stream, offer_id: int) -> OfferLink | None:
    return next((link for link in stream.offers if link.offer_id == offer_id), None)


def _active(stream: Stream, offer_id: int) -> OfferLink:
    link = _find(stream, offer_id)
    if link is None or link.state is not OfferState.ACTIVE:
        message = f"В потоке нет активного оффера {offer_id}"
        raise OfferNotFoundError(message)
    return link


def _swap(stream: Stream, changed: OfferLink) -> list[OfferLink]:
    """Put the changed link in place of the one with the same offer."""
    return [changed if link.offer_id == changed.offer_id else link for link in stream.offers]


@dataclass(frozen=True, slots=True)
class FetchedStreams:
    campaign: Campaign
    streams: list[Stream]


class EditorService:
    """Keep a local draft of every stream and reconcile it with the tracker (R-ED-01…24)."""

    def __init__(
        self,
        keitaro: KeitaroGateway,
        catalog: CatalogService,
        storage: Storage,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._keitaro = keitaro
        self._catalog = catalog
        self._storage = storage
        self._clock = clock

    async def campaigns(self) -> list[Campaign]:
        return await self._storage.campaigns.list_recent()

    async def campaign(self, campaign_id: UUID) -> Campaign | None:
        return await self._storage.campaigns.get(campaign_id)

    async def streams(self, campaign_id: UUID) -> list[Stream]:
        return await self._storage.streams.list_by_campaign(campaign_id)

    async def fetch(self, keitaro_campaign_id: int) -> FetchedStreams:
        """Load the streams of a campaign from the tracker and reconcile them with ours.

        Somebody may write the same campaign while the tracker answers. Then the
        load starts over from what is stored now: a second load of the same
        campaign finds the first one's result, a new draft is refused (R-CC-04, 05).
        """
        for _ in range(FETCH_ATTEMPTS):
            try:
                return await self._fetch(keitaro_campaign_id)
            except StorageConflictError:
                continue
        raise StreamConflictError

    async def _fetch(self, keitaro_campaign_id: int) -> FetchedStreams:
        campaign = await self._storage.campaigns.get_by_keitaro_id(keitaro_campaign_id)
        ours = await self.streams(campaign.id) if campaign else []
        drafts = [stream.name for stream in ours if stream.dirty]
        if drafts:
            raise DraftNotPublishedError(drafts)
        try:
            adopted = None
            if campaign is None:
                campaign = adopted = self._adopt(
                    await self._keitaro.get_campaign(keitaro_campaign_id)
                )
            theirs = await self._keitaro.list_campaign_streams(keitaro_campaign_id)
        except KeitaroError as error:
            if error.status == HTTPStatus.NOT_FOUND:
                raise CampaignNotFoundError(keitaro_campaign_id) from error
            raise

        known = {stream.keitaro_id: stream for stream in ours}
        merged = [await self._reconcile(campaign.id, known.get(item.id), item) for item in theirs]
        kept = {stream.id for stream in merged}
        async with self._storage.transaction() as work:
            if adopted is not None:
                await work.campaigns.add(adopted)
            saved = await work.streams.save_all(merged)
            for stream in ours:
                if stream.id not in kept:
                    await work.streams.delete(stream.id)
            await work.audit.record(
                self._entry(
                    "streams.fetched",
                    campaign.id,
                    None,
                    {"keitaro_id": campaign.keitaro_id, "streams": len(merged)},
                )
            )
        return FetchedStreams(campaign, sorted(saved, key=lambda stream: stream.position))

    async def add_offer(
        self, stream_id: UUID, offer_id: int, *, expected: int | None = None
    ) -> Stream:
        """Put an offer into the draft; a removed one comes back (R-ED-10, 11)."""
        stream = await self._stream(stream_id, expected)
        if stream.kind != OFFERS_KIND:
            raise ValidationError(
                {"streamId": "В этот поток офферы не добавляются: он не ведёт на офферы"}
            )
        known = _find(stream, offer_id)
        if known is not None:
            return await self.bring_back(stream_id, offer_id, expected=expected)
        offer = await self._catalog.get_offer(offer_id)
        if offer is None:
            message = f"В Keitaro нет активного оффера {offer_id}"
            raise OfferNotFoundError(message)
        return await self._save(stream, [*stream.offers, OfferLink(offer.id, offer.name, 0)])

    async def remove_offer(
        self, stream_id: UUID, offer_id: int, *, expected: int | None = None
    ) -> Stream:
        """Take an offer out of the draft, keeping it for bringing back (R-ED-12)."""
        stream = await self._stream(stream_id, expected)
        target = _active(stream, offer_id)
        removed = replace(target, share=0, pinned=False, state=OfferState.REMOVED)
        links = [
            removed if link is target else link
            for link in stream.offers
            if link is not target or target.published is not None
        ]
        return await self._save(stream, links)

    async def bring_back(
        self, stream_id: UUID, offer_id: int, *, expected: int | None = None
    ) -> Stream:
        """Make a removed offer active again (R-ED-13)."""
        stream = await self._stream(stream_id, expected)
        target = _find(stream, offer_id)
        if target is None:
            message = f"В потоке нет оффера {offer_id}"
            raise OfferNotFoundError(message)
        if target.state is OfferState.ACTIVE:
            raise OfferAlreadyInStreamError(target.name)
        return await self._save(stream, _swap(stream, replace(target, state=OfferState.ACTIVE)))

    async def pin_share(
        self, stream_id: UUID, offer_id: int, share: int, *, expected: int | None = None
    ) -> Stream:
        """Set a share by hand and keep it through recalculation (R-SH-06)."""
        stream = await self._stream(stream_id, expected)
        if not MIN_PINNED <= share <= TOTAL:
            raise ValidationError({"share": f"Доля — целое число от {MIN_PINNED} до {TOTAL}"})
        target = _active(stream, offer_id)
        return await self._save(stream, _swap(stream, replace(target, share=share, pinned=True)))

    async def unpin_share(
        self, stream_id: UUID, offer_id: int, *, expected: int | None = None
    ) -> Stream:
        """Let the offer take part in recalculation again (R-SH-07)."""
        stream = await self._stream(stream_id, expected)
        target = _active(stream, offer_id)
        return await self._save(stream, _swap(stream, replace(target, pinned=False)))

    async def cancel(self, stream_id: UUID, *, expected: int | None = None) -> Stream:
        """Return the stream to its published snapshot (R-ED-14)."""
        stream = await self._stream(stream_id, expected)
        restored = replace(
            stream,
            offers=tuple(
                replace(
                    link,
                    share=link.published.share,
                    state=link.published.state,
                    pinned=link.published.pinned,
                )
                for link in stream.offers
                if link.published is not None
            ),
        )
        return await self._write(restored)

    async def push(self, stream_id: UUID, *, expected: int | None = None) -> Stream:
        """Publish the draft: send the active offers and their shares to the tracker (R-ED-20)."""
        stream = await self._stream(stream_id, expected)
        active = [link for link in stream.offers if link.state is OfferState.ACTIVE]
        if not active:
            raise EmptyStreamError(stream.name)
        if not stream.dirty:
            return stream
        details: Details = {
            "keitaro_id": stream.keitaro_id,
            "before": [
                {"offer_id": link.offer_id, "share": link.published.share}
                for link in stream.offers
                if link.published is not None and link.published.state is OfferState.ACTIVE
            ],
            "after": [{"offer_id": link.offer_id, "share": link.share} for link in active],
        }
        try:
            await self._keitaro.replace_stream_offers(
                stream.keitaro_id,
                [tracker.StreamOffer(offer_id=link.offer_id, share=link.share) for link in active],
            )
        except KeitaroError as error:
            await self._storage.audit.record(
                self._entry(
                    "stream.push_failed",
                    stream.campaign_id,
                    stream.id,
                    details | {"error": str(error)},
                )
            )
            raise
        published = replace(
            stream,
            offers=tuple(
                replace(link, published=Published(link.share, link.state, link.pinned))
                for link in stream.offers
            ),
        )
        try:
            async with self._storage.transaction() as work:
                saved = await work.streams.save(published)
                await work.audit.record(
                    self._entry("stream.pushed", stream.campaign_id, stream.id, details)
                )
        except StorageConflictError as error:
            raise StreamConflictError(await self._storage.streams.get(stream.id)) from error
        return saved

    async def _stream(self, stream_id: UUID, expected: int | None = None) -> Stream:
        """Read the stream the user acts on; `expected` is the version they saw (R-CC-06)."""
        stream = await self._storage.streams.get(stream_id)
        if stream is None:
            raise StreamNotFoundError
        if expected is not None and stream.version != expected:
            raise StreamConflictError(stream)
        return stream

    async def _save(self, stream: Stream, links: Sequence[OfferLink]) -> Stream:
        """Recalculate the shares and store the stream as a whole (R-SH-01, R-ST-05).

        A refusal of the recalculation leaves the stored stream untouched (R-SH-08).
        """
        split = recalculate(
            [OfferShare(link.offer_id, link.share, link.pinned, link.state) for link in links]
        )
        offers = tuple(
            replace(link, share=part.share, pinned=part.pinned)
            for link, part in zip(links, split, strict=True)
        )
        return await self._write(replace(stream, offers=offers))

    async def _write(self, stream: Stream) -> Stream:
        """Store the stream unless somebody changed it since it was read (R-CC-02, 03)."""
        try:
            return await self._storage.streams.save(stream)
        except StorageConflictError as error:
            raise StreamConflictError(await self._storage.streams.get(stream.id)) from error

    def _adopt(self, theirs: tracker.Campaign) -> Campaign:
        """Describe a campaign made outside this service (R-ED-07)."""
        return Campaign(
            id=campaign_uuid(theirs.id),
            keitaro_id=theirs.id,
            name=theirs.name,
            alias=theirs.alias,
            created_at=self._clock(),
            domain_id=theirs.domain_id,
            group_id=theirs.group_id,
            traffic_source_id=theirs.traffic_source_id,
        )

    async def _reconcile(
        self, campaign_id: UUID, ours: Stream | None, theirs: tracker.Stream
    ) -> Stream:
        """Take the tracker's state as published; keep what it no longer has as removed."""
        before = {link.offer_id: link for link in ours.offers} if ours else {}
        present = [offer for offer in theirs.offers if offer.state == ACTIVE]
        links = [await self._published_link(before.get(offer.offer_id), offer) for offer in present]
        still_there = {offer.offer_id for offer in present}
        links += [
            replace(
                link,
                share=0,
                pinned=False,
                state=OfferState.REMOVED,
                published=Published(0, OfferState.REMOVED),
            )
            for link in before.values()
            if link.offer_id not in still_there
        ]
        return Stream(
            id=ours.id if ours else stream_uuid(theirs.id),
            campaign_id=campaign_id,
            keitaro_id=theirs.id,
            name=theirs.name,
            position=theirs.position,
            kind=theirs.kind,
            offers=tuple(links),
            version=ours.version if ours else 0,
        )

    async def _published_link(
        self, before: OfferLink | None, theirs: tracker.StreamOffer
    ) -> OfferLink:
        """Keep a pin only while the tracker still has the pinned share (R-ED-05)."""
        pinned = before is not None and before.pinned and before.share == theirs.share
        name = before.name if before else await self._offer_name(theirs.offer_id)
        return OfferLink(
            offer_id=theirs.offer_id,
            name=name,
            share=theirs.share,
            pinned=pinned,
            published=Published(theirs.share, pinned=pinned),
        )

    async def _offer_name(self, offer_id: int) -> str:
        offer = await self._catalog.get_offer(offer_id)
        return offer.name if offer else f"Оффер {offer_id}"

    def _entry(
        self, action: str, campaign_id: UUID, stream_id: UUID | None, details: Details
    ) -> AuditEntry:
        """One line of the journal; a publication carries what was and what became (R-ED-24)."""
        return AuditEntry(
            id=uuid4(),
            action=action,
            created_at=self._clock(),
            campaign_id=campaign_id,
            stream_id=stream_id,
            details=details,
        )
