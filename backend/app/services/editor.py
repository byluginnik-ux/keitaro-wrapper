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
    KeitaroError,
    OfferAlreadyInStreamError,
    OfferNotFoundError,
    StreamNotFoundError,
    ValidationError,
)
from app.services.models import AuditEntry, Campaign, Details, OfferLink, Published, Stream
from app.services.shares import TOTAL, OfferShare, OfferState, recalculate
from app.storage.ports import Storage

ACTIVE = "active"
OFFERS_KIND = "landings"
MIN_PINNED = 1


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
        """Load the streams of a campaign from the tracker and reconcile them with ours."""
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
        if adopted is not None:
            await self._storage.campaigns.add(adopted)
        await self._storage.streams.save_all(merged)
        kept = {stream.id for stream in merged}
        for stream in ours:
            if stream.id not in kept:
                await self._storage.streams.delete(stream.id)
        await self._record(
            "streams.fetched", campaign, {"keitaro_id": campaign.keitaro_id, "streams": len(merged)}
        )
        return FetchedStreams(campaign, sorted(merged, key=lambda stream: stream.position))

    async def add_offer(self, stream_id: UUID, offer_id: int) -> Stream:
        """Put an offer into the draft; a removed one comes back (R-ED-10, 11)."""
        stream = await self._stream(stream_id)
        if stream.kind != OFFERS_KIND:
            raise ValidationError(
                {"streamId": "В этот поток офферы не добавляются: он не ведёт на офферы"}
            )
        known = _find(stream, offer_id)
        if known is not None:
            return await self.bring_back(stream_id, offer_id)
        offer = await self._catalog.get_offer(offer_id)
        if offer is None:
            message = f"В Keitaro нет активного оффера {offer_id}"
            raise OfferNotFoundError(message)
        return await self._save(stream, [*stream.offers, OfferLink(offer.id, offer.name, 0)])

    async def remove_offer(self, stream_id: UUID, offer_id: int) -> Stream:
        """Take an offer out of the draft, keeping it for bringing back (R-ED-12)."""
        stream = await self._stream(stream_id)
        target = _active(stream, offer_id)
        removed = replace(target, share=0, pinned=False, state=OfferState.REMOVED)
        links = [
            removed if link is target else link
            for link in stream.offers
            if link is not target or target.published is not None
        ]
        return await self._save(stream, links)

    async def bring_back(self, stream_id: UUID, offer_id: int) -> Stream:
        """Make a removed offer active again (R-ED-13)."""
        stream = await self._stream(stream_id)
        target = _find(stream, offer_id)
        if target is None:
            message = f"В потоке нет оффера {offer_id}"
            raise OfferNotFoundError(message)
        if target.state is OfferState.ACTIVE:
            raise OfferAlreadyInStreamError(target.name)
        return await self._save(stream, _swap(stream, replace(target, state=OfferState.ACTIVE)))

    async def pin_share(self, stream_id: UUID, offer_id: int, share: int) -> Stream:
        """Set a share by hand and keep it through recalculation (R-SH-06)."""
        stream = await self._stream(stream_id)
        if not MIN_PINNED <= share <= TOTAL:
            raise ValidationError({"share": f"Доля — целое число от {MIN_PINNED} до {TOTAL}"})
        target = _active(stream, offer_id)
        return await self._save(stream, _swap(stream, replace(target, share=share, pinned=True)))

    async def unpin_share(self, stream_id: UUID, offer_id: int) -> Stream:
        """Let the offer take part in recalculation again (R-SH-07)."""
        stream = await self._stream(stream_id)
        target = _active(stream, offer_id)
        return await self._save(stream, _swap(stream, replace(target, pinned=False)))

    async def cancel(self, stream_id: UUID) -> Stream:
        """Return the stream to its published snapshot (R-ED-14)."""
        stream = await self._stream(stream_id)
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
        await self._storage.streams.save(restored)
        return restored

    async def _stream(self, stream_id: UUID) -> Stream:
        stream = await self._storage.streams.get(stream_id)
        if stream is None:
            raise StreamNotFoundError
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
        updated = replace(stream, offers=offers)
        await self._storage.streams.save(updated)
        return updated

    def _adopt(self, theirs: tracker.Campaign) -> Campaign:
        """Describe a campaign made outside this service (R-ED-07)."""
        return Campaign(
            id=uuid4(),
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
            id=ours.id if ours else uuid4(),
            campaign_id=campaign_id,
            keitaro_id=theirs.id,
            name=theirs.name,
            position=theirs.position,
            kind=theirs.kind,
            offers=tuple(links),
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

    async def _record(self, action: str, campaign: Campaign, details: Details) -> None:
        await self._storage.audit.record(
            AuditEntry(
                id=uuid4(),
                action=action,
                created_at=self._clock(),
                campaign_id=campaign.id,
                details=details,
            )
        )
