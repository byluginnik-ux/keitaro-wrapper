import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from app.services.errors import ShareOverflowError
from app.services.shares import OfferShare, OfferState, recalculate

A, B, C, D = 11111, 11112, 11113, 11114


def active(offer_id: int, share: int = 0, *, pinned: bool = False) -> OfferShare:
    return OfferShare(offer_id, share, pinned=pinned)


def removed(offer_id: int, share: int = 0, *, pinned: bool = False) -> OfferShare:
    return OfferShare(offer_id, share, pinned=pinned, state=OfferState.REMOVED)


def shares(offers: list[OfferShare]) -> list[int]:
    return [offer.share for offer in offers]


@pytest.mark.parametrize(
    ("offers", "expected"),
    [
        ([active(A)], [100]),
        ([active(A), active(B)], [50, 50]),
        ([active(A), active(B), active(C)], [34, 33, 33]),
        ([active(A), active(B), active(C), active(D)], [25, 25, 25, 25]),
        ([active(n) for n in range(7)], [15, 15, 14, 14, 14, 14, 14]),
    ],
)
def test_free_offers_split_evenly_and_first_ones_take_the_remainder(
    offers: list[OfferShare], expected: list[int]
) -> None:
    """R-SH-01, R-SH-04, R-SH-05."""
    assert shares(recalculate(offers)) == expected


def test_previous_shares_of_free_offers_do_not_matter() -> None:
    """R-SH-04: the split depends on the composition only."""
    assert shares(recalculate([active(A, 90), active(B, 7), active(C, 3)])) == [34, 33, 33]


def test_removed_offer_gets_zero_and_loses_its_pin() -> None:
    """R-SH-02, R-ED-12."""
    result = recalculate([active(A), removed(B, 33, pinned=True), active(C)])

    assert shares(result) == [50, 0, 50]
    assert result[1].pinned is False
    assert result[1].state is OfferState.REMOVED


def test_pinned_share_is_kept_and_the_rest_is_split() -> None:
    """R-SH-03, R-SH-04, scenario S7: 75 / 2 -> 38, 37."""
    result = recalculate([active(A), active(B), active(C, 25, pinned=True), removed(D)])

    assert shares(result) == [38, 37, 25, 0]


def test_bringing_an_offer_back_respects_the_pin() -> None:
    """Scenario S7: C stays 25, the other three share 75."""
    result = recalculate([active(A), active(B), active(C, 25, pinned=True), active(D)])

    assert shares(result) == [25, 25, 25, 25]
    assert [offer.pinned for offer in result] == [False, False, True, False]


def test_all_pinned_offers_summing_to_100_are_left_alone() -> None:
    """R-SH-03."""
    offers = [active(A, 60, pinned=True), active(B, 40, pinned=True)]

    assert recalculate(offers) == offers


@pytest.mark.parametrize(
    "offers",
    [
        pytest.param(
            [active(A, 60, pinned=True), active(B, 50, pinned=True)], id="pinned>100 (S8)"
        ),
        pytest.param([active(A, 100, pinned=True), active(B)], id="pinned=100 with a free offer"),
        pytest.param(
            [active(A, 60, pinned=True), active(B, 30, pinned=True)], id="all pinned, not 100"
        ),
        pytest.param(
            [active(A, 99, pinned=True), active(B), active(C)], id="rest smaller than free count"
        ),
    ],
)
def test_impossible_split_is_refused(offers: list[OfferShare]) -> None:
    """R-SH-08, R-SH-09."""
    with pytest.raises(ShareOverflowError) as raised:
        recalculate(offers)

    assert raised.value.code == "share_overflow"


def test_stream_without_active_offers_has_only_zeroes() -> None:
    """R-SH-02: nothing to split."""
    assert shares(recalculate([removed(A, 50), removed(B, 50)])) == [0, 0]


def test_empty_stream_stays_empty() -> None:
    assert recalculate([]) == []


def test_input_is_not_modified() -> None:
    """A refusal or a success must leave the caller's state intact."""
    offers = [active(A, 90), active(B, 10)]
    snapshot = list(offers)

    recalculate(offers)

    assert offers == snapshot


offer_lists = st.lists(
    st.builds(
        OfferShare,
        offer_id=st.integers(min_value=1, max_value=10**6),
        share=st.integers(min_value=1, max_value=100),
        pinned=st.booleans(),
        state=st.sampled_from(OfferState),
    ),
    max_size=12,
)


@given(offer_lists)
def test_invariants_hold_for_any_stream(offers: list[OfferShare]) -> None:
    """R-SH-01…05 as properties."""
    try:
        result = recalculate(offers)
    except ShareOverflowError:
        assume(condition=False)
        return

    assert [offer.offer_id for offer in result] == [offer.offer_id for offer in offers]
    actives = [offer for offer in result if offer.state is OfferState.ACTIVE]
    if actives:
        assert sum(offer.share for offer in actives) == 100
        assert all(offer.share >= 1 for offer in actives)
    for before, after in zip(offers, result, strict=True):
        if before.state is OfferState.REMOVED:
            assert (after.share, after.pinned) == (0, False)
        elif before.pinned:
            assert (after.share, after.pinned) == (before.share, True)
    assert recalculate(result) == result
