from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid5

from app.services.shares import OfferState

type Scalar = str | int | bool | None
type Details = dict[str, Scalar | list[dict[str, Scalar]]]
type Payload = dict[str, Any]
"""Plain JSON: what a task was asked to do or what a message carries."""


_IDS = UUID("6f1c2a54-3b7e-5d21-9c40-8a2f6e1d7b03")


def campaign_uuid(keitaro_id: int) -> UUID:
    """Our ID of a campaign follows from the tracker's, so two loads agree (R-CC-04)."""
    return uuid5(_IDS, f"campaign:{keitaro_id}")


def stream_uuid(keitaro_id: int) -> UUID:
    """Our ID of a stream follows from the tracker's, so two loads agree (R-CC-04)."""
    return uuid5(_IDS, f"stream:{keitaro_id}")


def _no_details() -> Details:
    return {}


@dataclass(frozen=True, slots=True)
class Published:
    """What the tracker held for an offer at the last fetch or push."""

    share: int
    state: OfferState = OfferState.ACTIVE
    pinned: bool = False


@dataclass(frozen=True, slots=True)
class OfferLink:
    """An offer inside a stream: the draft values and the published snapshot behind them."""

    offer_id: int
    name: str
    share: int
    pinned: bool = False
    state: OfferState = OfferState.ACTIVE
    published: Published | None = None

    @property
    def changed(self) -> bool:
        """Whether publishing would change the tracker; a pin alone is not sent anywhere."""
        if self.published is None:
            return True
        return (self.share, self.state) != (self.published.share, self.published.state)


@dataclass(frozen=True, slots=True)
class Stream:
    id: UUID
    campaign_id: UUID
    keitaro_id: int
    name: str
    position: int
    kind: str
    offers: tuple[OfferLink, ...] = ()
    version: int = field(default=0, compare=False)
    """How many times the stream was written; bookkeeping, not part of its value (R-CC-01)."""

    @property
    def dirty(self) -> bool:
        """Derived, never stored: the draft differs from the published snapshot (R-ED-15)."""
        return any(link.changed for link in self.offers)


@dataclass(frozen=True, slots=True)
class Campaign:
    id: UUID
    keitaro_id: int
    name: str
    alias: str
    created_at: datetime
    country: str | None = None
    domain_id: int | None = None
    group_id: int | None = None
    traffic_source_id: int | None = None


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One line of the operation journal (R-CR-09, R-ED-24)."""

    id: UUID
    action: str
    created_at: datetime
    campaign_id: UUID | None = None
    stream_id: UUID | None = None
    details: Details = field(default_factory=_no_details)


class TaskKind(StrEnum):
    PUBLISH_STREAM = "publish_stream"
    CREATE_CAMPAIGN = "create_campaign"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

    @property
    def final(self) -> bool:
        return self in {TaskStatus.SUCCEEDED, TaskStatus.REJECTED, TaskStatus.CANCELLED}


def _no_fields() -> dict[str, str]:
    return {}


def _no_payload() -> Payload:
    return {}


@dataclass(frozen=True, slots=True)
class Refusal:
    """Why a task ended without doing its work: a stable code and words for the user."""

    code: str
    message: str
    fields: dict[str, str] = field(default_factory=_no_fields)
    details: Payload = field(default_factory=_no_payload)


@dataclass(frozen=True, slots=True)
class TaskStep:
    """One thing a task did, in the order it happened."""

    name: str
    at: datetime
    note: str = ""


@dataclass(frozen=True, slots=True)
class Task:
    """A change of the tracker that is carried out apart from the request (R-TK-01)."""

    id: UUID
    kind: TaskKind
    created_at: datetime
    fingerprint: str
    payload: Payload = field(default_factory=_no_payload)
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    campaign_id: UUID | None = None
    stream_id: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    refusal: Refusal | None = None
    steps: tuple[TaskStep, ...] = ()
    retry_of: UUID | None = None


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    """A message that leaves together with the data change it tells about (R-EV-01)."""

    id: UUID
    topic: str
    created_at: datetime
    payload: Payload = field(default_factory=_no_payload)


@dataclass(frozen=True, slots=True)
class OutboxBacklog:
    """How much is waiting to be sent and since when."""

    waiting: int
    oldest: datetime | None
