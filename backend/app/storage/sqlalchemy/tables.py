from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, text
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
    version: Mapped[int] = mapped_column(server_default="1")
    publishing_task_id: Mapped[UUID | None]
    offers: Mapped[list["StreamOfferRow"]] = relationship(
        order_by="StreamOfferRow.position", lazy="selectin", viewonly=True
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


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_status_created_at", "status", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    fingerprint: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]]
    attempts: Mapped[int]
    campaign_id: Mapped[UUID | None]
    stream_id: Mapped[UUID | None]
    retry_of: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(index=True)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    refusal: Mapped[dict[str, Any] | None]
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class OutboxRow(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_unsent", "created_at", postgresql_where=text("sent_at IS NULL")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]]
    created_at: Mapped[datetime]
    claimed_until: Mapped[datetime | None]
    sent_at: Mapped[datetime | None]
