from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, datetime: DateTime(timezone=True)}  # noqa: RUF012 — SQLAlchemy reads it as class configuration


class CampaignRow(Base):
    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    keitaro_id: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(255))
    alias: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(index=True)
    country: Mapped[str | None] = mapped_column(String(2))
    domain_id: Mapped[int | None]
    group_id: Mapped[int | None]
    traffic_source_id: Mapped[int | None]


class StreamRow(Base):
    __tablename__ = "streams"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    keitaro_id: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int]
    kind: Mapped[str] = mapped_column(String(32))
    offers: Mapped[list["StreamOfferRow"]] = relationship(
        order_by="StreamOfferRow.position", cascade="all, delete-orphan", lazy="selectin"
    )


class StreamOfferRow(Base):
    __tablename__ = "stream_offers"

    stream_id: Mapped[UUID] = mapped_column(
        ForeignKey("streams.id", ondelete="CASCADE"), primary_key=True
    )
    offer_id: Mapped[int] = mapped_column(primary_key=True)
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String(512))
    share: Mapped[int]
    pinned: Mapped[bool]
    state: Mapped[str] = mapped_column(String(16))
    published_share: Mapped[int | None]
    published_state: Mapped[str | None] = mapped_column(String(16))
    published_pinned: Mapped[bool | None]


class AuditRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(index=True)
    campaign_id: Mapped[UUID | None]
    stream_id: Mapped[UUID | None]
    details: Mapped[dict[str, Any]]
