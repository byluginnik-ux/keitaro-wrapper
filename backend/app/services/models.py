from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.services.shares import OfferState

type Scalar = str | int | bool | None
type Details = dict[str, Scalar | list[dict[str, Scalar]]]


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
