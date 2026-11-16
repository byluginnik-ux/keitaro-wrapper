from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

TOTAL = 100


class OfferState(StrEnum):
    """Whether an offer takes traffic in its stream or is kept only for bringing back."""

    ACTIVE = "active"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class OfferShare:
    """Share of one offer inside a stream; `share` is a whole percent."""

    offer_id: int
    share: int
    pinned: bool = False
    state: OfferState = OfferState.ACTIVE


def recalculate(offers: Sequence[OfferShare]) -> list[OfferShare]:
    """Split 100% between the offers of one stream, in the given order (R-SH-01…09)."""
    raise NotImplementedError
