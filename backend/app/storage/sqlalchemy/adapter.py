from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.services.models import AuditEntry, Campaign, OfferLink, Published, Stream
from app.services.shares import OfferState
from app.storage.ports import Storage
from app.storage.sqlalchemy.tables import AuditRow, CampaignRow, StreamOfferRow, StreamRow

type Sessions = async_sessionmaker[AsyncSession]


def _campaign(row: CampaignRow) -> Campaign:
    return Campaign(
        id=row.id,
        keitaro_id=row.keitaro_id,
        name=row.name,
        alias=row.alias,
        created_at=row.created_at,
        country=row.country,
        domain_id=row.domain_id,
        group_id=row.group_id,
        traffic_source_id=row.traffic_source_id,
    )


def _offer(row: StreamOfferRow) -> OfferLink:
    published = None
    if row.published_share is not None:
        published = Published(
            share=row.published_share,
            state=OfferState(row.published_state or OfferState.ACTIVE),
            pinned=bool(row.published_pinned),
        )
    return OfferLink(
        offer_id=row.offer_id,
        name=row.name,
        share=row.share,
        pinned=row.pinned,
        state=OfferState(row.state),
        published=published,
    )


def _stream(row: StreamRow) -> Stream:
    return Stream(
        id=row.id,
        campaign_id=row.campaign_id,
        keitaro_id=row.keitaro_id,
        name=row.name,
        position=row.position,
        kind=row.kind,
        offers=tuple(_offer(offer) for offer in row.offers),
    )


def _offer_row(stream_id: UUID, position: int, link: OfferLink) -> StreamOfferRow:
    published = link.published
    return StreamOfferRow(
        stream_id=stream_id,
        offer_id=link.offer_id,
        position=position,
        name=link.name,
        share=link.share,
        pinned=link.pinned,
        state=link.state.value,
        published_share=published.share if published else None,
        published_state=published.state.value if published else None,
        published_pinned=published.pinned if published else None,
    )


class SqlCampaigns:
    def __init__(self, sessions: Sessions) -> None:
        self._sessions = sessions

    async def add(self, campaign: Campaign) -> None:
        async with self._sessions.begin() as session:
            session.add(
                CampaignRow(
                    id=campaign.id,
                    keitaro_id=campaign.keitaro_id,
                    name=campaign.name,
                    alias=campaign.alias,
                    created_at=campaign.created_at,
                    country=campaign.country,
                    domain_id=campaign.domain_id,
                    group_id=campaign.group_id,
                    traffic_source_id=campaign.traffic_source_id,
                )
            )

    async def get(self, campaign_id: UUID) -> Campaign | None:
        async with self._sessions() as session:
            row = await session.get(CampaignRow, campaign_id)
            return _campaign(row) if row else None

    async def get_by_keitaro_id(self, keitaro_id: int) -> Campaign | None:
        async with self._sessions() as session:
            query = select(CampaignRow).where(CampaignRow.keitaro_id == keitaro_id)
            row = await session.scalar(query)
            return _campaign(row) if row else None

    async def list_recent(self) -> list[Campaign]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(CampaignRow).order_by(CampaignRow.created_at.desc())
            )
            return [_campaign(row) for row in rows]


class SqlStreams:
    def __init__(self, sessions: Sessions) -> None:
        self._sessions = sessions

    async def get(self, stream_id: UUID) -> Stream | None:
        async with self._sessions() as session:
            row = await session.get(StreamRow, stream_id)
            return _stream(row) if row else None

    async def list_by_campaign(self, campaign_id: UUID) -> list[Stream]:
        async with self._sessions() as session:
            query = (
                select(StreamRow)
                .where(StreamRow.campaign_id == campaign_id)
                .order_by(StreamRow.position)
            )
            return [_stream(row) for row in await session.scalars(query)]

    async def save(self, stream: Stream) -> None:
        await self.save_all([stream])

    async def save_all(self, streams: Sequence[Stream]) -> None:
        """Write every stream in one transaction; a missing campaign rolls all of it back."""
        try:
            async with self._sessions.begin() as session:
                for stream in streams:
                    row = await session.get(StreamRow, stream.id)
                    if row is None:
                        row = StreamRow(id=stream.id)
                        session.add(row)
                    row.campaign_id = stream.campaign_id
                    row.keitaro_id = stream.keitaro_id
                    row.name = stream.name
                    row.position = stream.position
                    row.kind = stream.kind
                    row.offers = [
                        _offer_row(stream.id, position, link)
                        for position, link in enumerate(stream.offers)
                    ]
                    await session.flush()
        except IntegrityError as error:
            message = "a stream refers to a campaign that is not stored"
            raise LookupError(message) from error

    async def delete(self, stream_id: UUID) -> None:
        async with self._sessions.begin() as session:
            row = await session.get(StreamRow, stream_id)
            if row is not None:
                await session.delete(row)


class SqlAudit:
    def __init__(self, sessions: Sessions) -> None:
        self._sessions = sessions

    async def record(self, entry: AuditEntry) -> None:
        async with self._sessions.begin() as session:
            session.add(
                AuditRow(
                    id=entry.id,
                    action=entry.action,
                    created_at=entry.created_at,
                    campaign_id=entry.campaign_id,
                    stream_id=entry.stream_id,
                    details=dict(entry.details),
                )
            )

    async def list_recent(self, limit: int = 50) -> list[AuditEntry]:
        async with self._sessions() as session:
            query = select(AuditRow).order_by(AuditRow.created_at.desc()).limit(limit)
            return [
                AuditEntry(
                    id=row.id,
                    action=row.action,
                    created_at=row.created_at,
                    campaign_id=row.campaign_id,
                    stream_id=row.stream_id,
                    details=row.details,
                )
                for row in await session.scalars(query)
            ]


def create_sqlalchemy_storage(engine: AsyncEngine) -> Storage:
    """Persist through SQLAlchemy; the schema is owned by Alembic migrations (R-ST-02)."""
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return Storage(
        campaigns=SqlCampaigns(sessions), streams=SqlStreams(sessions), audit=SqlAudit(sessions)
    )
