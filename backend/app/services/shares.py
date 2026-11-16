from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from app.services.errors import ShareOverflowError

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
    active = [offer for offer in offers if offer.state is OfferState.ACTIVE]
    pinned_total = sum(offer.share for offer in active if offer.pinned)
    free_count = sum(1 for offer in active if not offer.pinned)
    rest = TOTAL - pinned_total

    all_pinned_but_not_total = free_count == 0 and bool(active) and rest != 0
    if rest < free_count or all_pinned_but_not_total:
        raise ShareOverflowError(pinned_total, free_count)

    base, extra = divmod(rest, free_count) if free_count else (0, 0)
    result: list[OfferShare] = []
    free_seen = 0
    for offer in offers:
        if offer.state is OfferState.REMOVED:
            result.append(replace(offer, share=0, pinned=False))
        elif offer.pinned:
            result.append(offer)
        else:
            result.append(replace(offer, share=base + (1 if free_seen < extra else 0)))
            free_seen += 1
    return result
