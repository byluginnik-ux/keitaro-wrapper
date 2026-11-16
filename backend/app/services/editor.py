from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from http import HTTPStatus
from uuid import UUID, uuid4

from app.keitaro import models as tracker
from app.keitaro.gateway import KeitaroGateway
from app.services.catalog import CatalogService
from app.services.creator import utc_now
from app.services.errors import CampaignNotFoundError, DraftNotPublishedError, KeitaroError
from app.services.models import AuditEntry, Campaign, Details, OfferLink, Published, Stream
from app.services.shares import OfferState
from app.storage.ports import Storage

ACTIVE = "active"


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
        raise NotImplementedError

    async def remove_offer(self, stream_id: UUID, offer_id: int) -> Stream:
        """Take an offer out of the draft, keeping it for bringing back (R-ED-12)."""
        raise NotImplementedError

    async def bring_back(self, stream_id: UUID, offer_id: int) -> Stream:
        """Make a removed offer active again (R-ED-13)."""
        raise NotImplementedError

    async def pin_share(self, stream_id: UUID, offer_id: int, share: int) -> Stream:
        """Set a share by hand and keep it through recalculation (R-SH-06)."""
        raise NotImplementedError

    async def unpin_share(self, stream_id: UUID, offer_id: int) -> Stream:
        """Let the offer take part in recalculation again (R-SH-07)."""
        raise NotImplementedError

    async def cancel(self, stream_id: UUID) -> Stream:
        """Return the stream to its published snapshot (R-ED-14)."""
        raise NotImplementedError

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
