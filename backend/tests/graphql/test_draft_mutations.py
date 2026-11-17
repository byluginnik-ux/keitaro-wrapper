from typing import Any

import pytest

from app.graphql.context import Context
from app.graphql.schema import schema
from tests.fakes import CAMPAIGN_ID, A, B, D, tracker_with_campaign
from tests.graphql.support import context_for

pytestmark = pytest.mark.anyio

RESULT = """
  __typename
  ... on Stream { id dirty offers { offerId share pinned state changed } }
  ... on ValidationFailed { message fields { field } }
  ... on StreamNotFound { message }
  ... on OfferNotFound { message }
  ... on OfferAlreadyInStream { message }
  ... on ShareOverflow { message }
  ... on KeitaroFailure { message }
"""
FETCH = """
mutation($id: Int!) {
  fetchStreams(campaignKeitaroId: $id) { ... on StreamsFetched { streams { id } } }
}
"""


def mutation(name: str, input_type: str = "StreamOfferInput") -> str:
    return f"mutation($input: {input_type}!) {{ result: {name}(input: $input) {{ {RESULT} }} }}"


CANCEL = f"mutation($id: ID!) {{ result: cancelDraft(streamId: $id) {{ {RESULT} }} }}"


async def run(context: Context, document: str, **variables: object) -> dict[str, Any]:
    result = await schema.execute(document, variable_values=variables, context_value=context)
    assert result.errors is None
    assert result.data is not None
    return result.data


@pytest.fixture
def context() -> Context:
    return context_for(tracker_with_campaign())


@pytest.fixture
async def stream_id(context: Context) -> str:
    fetched = await run(context, FETCH, id=CAMPAIGN_ID)
    return fetched["fetchStreams"]["streams"][1]["id"]


def shares(answer: dict[str, Any]) -> list[int]:
    return [offer["share"] for offer in answer["offers"]]


async def act(context: Context, name: str, stream_id: str, offer_id: int) -> dict[str, Any]:
    variables = {"streamId": stream_id, "offerId": offer_id}
    return (await run(context, mutation(name), input=variables))["result"]


async def test_draft_is_edited_step_by_step(context: Context, stream_id: str) -> None:
    """S2, S4, S5 through the API."""
    added = await act(context, "addOffer", stream_id, D)
    assert (added["__typename"], added["dirty"], shares(added)) == (
        "Stream",
        True,
        [25, 25, 25, 25],
    )
    assert added["offers"][3] == {
        "offerId": D,
        "share": 25,
        "pinned": False,
        "state": "ACTIVE",
        "changed": True,
    }

    removed = await act(context, "removeOffer", stream_id, B)
    assert shares(removed) == [34, 0, 33, 33]
    assert removed["offers"][1]["state"] == "REMOVED"

    back = await act(context, "bringBackOffer", stream_id, B)
    assert shares(back) == [25, 25, 25, 25]

    cancelled = (await run(context, CANCEL, id=stream_id))["result"]
    assert (cancelled["dirty"], shares(cancelled)) == (False, [34, 33, 33])


async def test_share_is_pinned_and_unpinned(context: Context, stream_id: str) -> None:
    """R-SH-06, R-SH-07."""
    pin = {"streamId": stream_id, "offerId": A, "share": 60}

    pinned = (await run(context, mutation("pinShare", "PinShareInput"), input=pin))["result"]
    unpinned = await act(context, "unpinShare", stream_id, A)

    assert (shares(pinned), pinned["offers"][0]["pinned"]) == ([60, 20, 20], True)
    assert (shares(unpinned), unpinned["offers"][0]["pinned"]) == ([34, 33, 33], False)


async def test_refusals_are_typed(context: Context, stream_id: str) -> None:
    """R-ED-11, R-SH-06, R-SH-08: the client switches on the type, not on text."""
    pin = mutation("pinShare", "PinShareInput")
    await run(context, pin, input={"streamId": stream_id, "offerId": A, "share": 60})

    answers = [
        await act(context, "addOffer", stream_id, A),
        await act(context, "addOffer", stream_id, 999),
        await act(context, "addOffer", "not-an-id", A),
        (await run(context, pin, input={"streamId": stream_id, "offerId": B, "share": 50}))[
            "result"
        ],
        (await run(context, pin, input={"streamId": stream_id, "offerId": B, "share": 0}))[
            "result"
        ],
    ]

    assert [answer["__typename"] for answer in answers] == [
        "OfferAlreadyInStream",
        "OfferNotFound",
        "StreamNotFound",
        "ShareOverflow",
        "ValidationFailed",
    ]
    assert all(answer["message"] for answer in answers)
    assert answers[4]["fields"] == [{"field": "share"}]


async def test_tracker_failure_while_looking_the_offer_up() -> None:
    """R-KT-02."""
    keitaro = tracker_with_campaign()
    context = context_for(keitaro, offers_ttl=0)
    fetched = await run(context, FETCH, id=CAMPAIGN_ID)
    keitaro.fail_on.add("list_offers")

    answer = await act(context, "addOffer", fetched["fetchStreams"]["streams"][1]["id"], D)

    assert answer["__typename"] == "KeitaroFailure"


CONFLICT = """
  __typename
  ... on Stream { version }
  ... on StreamConflict { message stream { id version dirty offers { offerId share state } } }
"""
VERSION = "query($id: ID!) { streams(campaignId: $id) { id version } }"
FETCH_VERSIONS = """
mutation($id: Int!) {
  fetchStreams(campaignKeitaroId: $id) {
    ... on StreamsFetched { streams { id version } }
  }
}
"""


def versioned(name: str, arguments: str, declared: str) -> str:
    return f"mutation({declared}) {{ result: {name}({arguments}) {{ {CONFLICT} }} }}"


ADD_SEEN = versioned("addOffer", "input: $input", "$input: StreamOfferInput!")
CANCEL_SEEN = versioned(
    "cancelDraft", "streamId: $id, expectedVersion: $seen", "$id: ID!, $seen: Int"
)


async def test_stream_tells_its_version_and_actions_raise_it(context: Context) -> None:
    """R-CC-01, R-CC-06."""
    fetched = await run(context, FETCH_VERSIONS, id=CAMPAIGN_ID)
    stream = fetched["fetchStreams"]["streams"][1]

    added = await run(
        context,
        ADD_SEEN,
        input={"streamId": stream["id"], "offerId": D, "expectedVersion": stream["version"]},
    )

    assert added["result"] == {"__typename": "Stream", "version": stream["version"] + 1}


async def test_outdated_action_answers_with_the_current_stream(
    context: Context, stream_id: str
) -> None:
    """R-CC-06: the first window still shows version 1 after the second one removed B."""
    seen = 1
    await act(context, "removeOffer", stream_id, B)
    stale = {"streamId": stream_id, "offerId": D, "expectedVersion": seen}

    answers = [
        (await run(context, ADD_SEEN, input=stale))["result"],
        (await run(context, CANCEL_SEEN, id=stream_id, seen=seen))["result"],
    ]

    for answer in answers:
        assert answer["__typename"] == "StreamConflict"
        assert "изменён" in answer["message"]
        assert answer["stream"]["version"] == seen + 1
        assert answer["stream"]["dirty"] is True
        assert [offer["share"] for offer in answer["stream"]["offers"]] == [50, 0, 50]
