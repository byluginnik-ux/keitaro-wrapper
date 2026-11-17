"""The publication mutation and the task query (R-ED-20…26, R-TK-04, 05)."""

from typing import Any
from uuid import uuid4

import pytest

from app.graphql.context import Context
from app.graphql.schema import schema
from app.messaging.ports import Message
from app.services.publisher import PUBLISH_REQUESTED
from tests.fakes import CAMPAIGN_ID, OFFERS_STREAM_ID, A, D, FakeKeitaro, tracker_with_campaign
from tests.graphql.support import NOW, context_for
from tests.graphql.test_draft_mutations import FETCH, act, run

pytestmark = pytest.mark.anyio

TASK = """
  id kind status attempts createdAt startedAt finishedAt campaignId streamId
  refusal { message createdDomain { id } }
  steps { name at note }
"""
PUBLISH = f"""
mutation($input: PublishStreamInput!) {{
  result: publishStream(input: $input) {{
    __typename
    ... on Task {{ {TASK} }}
    ... on StreamConflict {{ message stream {{ version dirty }} }}
    ... on StreamBusy {{ message }}
    ... on StreamNotFound {{ message }}
    ... on EmptyStream {{ message }}
    ... on TaskKeyReused {{ message }}
  }}
}}
"""
TASK_BY_ID = f"query($id: ID!) {{ task(id: $id) {{ {TASK} }} }}"
STREAMS = """
query($id: ID!) { streams(campaignId: $id) { id dirty version publishingTaskId } }
"""
BUSY = "__typename ... on StreamBusy { message }"
REMOVE_BUSY = f"""
mutation($input: StreamOfferInput!) {{ result: removeOffer(input: $input) {{ {BUSY} }} }}
"""
FETCH_BUSY = f"""
mutation($id: Int!) {{ result: fetchStreams(campaignKeitaroId: $id) {{ {BUSY} }} }}
"""


@pytest.fixture
def keitaro() -> FakeKeitaro:
    return tracker_with_campaign()


@pytest.fixture
def context(keitaro: FakeKeitaro) -> Context:
    return context_for(keitaro)


@pytest.fixture
async def stream_id(context: Context) -> str:
    fetched = await run(context, FETCH, id=CAMPAIGN_ID)
    return fetched["fetchStreams"]["streams"][1]["id"]


async def publish(context: Context, stream_id: str, task_id: str, **more: object) -> dict[str, Any]:
    variables = {"streamId": stream_id, "taskId": task_id, **more}
    return (await run(context, PUBLISH, input=variables))["result"]


async def work(context: Context, task_id: str) -> None:
    """Do what the worker does when the message arrives."""
    await context.publisher.handle(Message(uuid4(), PUBLISH_REQUESTED, {"task_id": task_id}))


async def test_publication_is_queued_and_then_done(
    context: Context, keitaro: FakeKeitaro, stream_id: str
) -> None:
    """S3, R-ED-20, R-ED-21, R-ED-25, R-TK-05."""
    await act(context, "addOffer", stream_id, D)
    task_id = str(uuid4())

    queued = await publish(context, stream_id, task_id)
    campaign_id = queued["campaignId"]
    busy = (await run(context, STREAMS, id=campaign_id))["streams"][1]
    await work(context, task_id)
    done = (await run(context, TASK_BY_ID, id=task_id))["task"]
    free = (await run(context, STREAMS, id=campaign_id))["streams"][1]

    assert queued == {
        "__typename": "Task",
        "id": task_id,
        "kind": "PUBLISH_STREAM",
        "status": "PENDING",
        "attempts": 0,
        "createdAt": NOW.isoformat(),
        "startedAt": None,
        "finishedAt": None,
        "campaignId": campaign_id,
        "streamId": stream_id,
        "refusal": None,
        "steps": [{"name": "queued", "at": NOW.isoformat(), "note": ""}],
    }
    assert (busy["publishingTaskId"], busy["dirty"]) == (task_id, True)
    assert (done["status"], done["attempts"], done["finishedAt"]) == (
        "SUCCEEDED",
        1,
        NOW.isoformat(),
    )
    assert [step["name"] for step in done["steps"]] == ["queued", "attempt", "published"]
    assert (free["publishingTaskId"], free["dirty"]) == (None, False)
    assert [offer.share for offer in keitaro.streams[OFFERS_STREAM_ID].offers] == [25] * 4


async def test_rejected_task_tells_why(
    context: Context, keitaro: FakeKeitaro, stream_id: str
) -> None:
    """R-ED-22, R-TK-05."""
    await act(context, "addOffer", stream_id, D)
    keitaro.fail_on.add("replace_stream_offers")
    keitaro.fail_status = 400
    task_id = str(uuid4())

    await publish(context, stream_id, task_id)
    await work(context, task_id)
    done = (await run(context, TASK_BY_ID, id=task_id))["task"]

    assert done["status"] == "REJECTED"
    assert done["refusal"] == {
        "message": "Keitaro: replace_stream_offers failed",
        "createdDomain": None,
    }


async def test_repeat_with_the_same_task_id_returns_the_same_task(
    context: Context, stream_id: str
) -> None:
    """R-TK-04."""
    await act(context, "addOffer", stream_id, D)
    task_id = str(uuid4())

    first = await publish(context, stream_id, task_id)
    again = await publish(context, stream_id, task_id)
    reused = await publish(context, str(uuid4()), task_id)

    assert again == first
    assert reused["__typename"] == "TaskKeyReused"


async def test_reasons_not_to_queue_are_typed(context: Context, stream_id: str) -> None:
    """R-ED-23, R-ED-25, R-CC-06."""
    await act(context, "addOffer", stream_id, D)
    stale = await publish(context, stream_id, str(uuid4()), expectedVersion=1)
    unknown = await publish(context, "not-an-id", str(uuid4()))
    await publish(context, stream_id, str(uuid4()))
    busy = await publish(context, stream_id, str(uuid4()))

    assert stale["__typename"] == "StreamConflict"
    assert stale["stream"] == {"version": 2, "dirty": True}
    assert (unknown["__typename"], busy["__typename"]) == ("StreamNotFound", "StreamBusy")
    assert "публикуется" in busy["message"]


async def test_empty_stream_is_not_queued() -> None:
    """R-ED-23."""
    context = context_for(tracker_with_campaign((A, 100)))
    stream_id = (await run(context, FETCH, id=CAMPAIGN_ID))["fetchStreams"]["streams"][1]["id"]
    await act(context, "removeOffer", stream_id, A)

    answer = await publish(context, stream_id, str(uuid4()))

    assert answer["__typename"] == "EmptyStream"


async def test_busy_stream_refuses_edits_and_reloading(context: Context, stream_id: str) -> None:
    """R-ED-25."""
    await act(context, "addOffer", stream_id, D)
    await publish(context, stream_id, str(uuid4()))

    edit = await run(
        context,
        REMOVE_BUSY,
        input={"streamId": stream_id, "offerId": A},
    )
    reload = await run(
        context,
        FETCH_BUSY,
        id=CAMPAIGN_ID,
    )

    assert edit["result"]["__typename"] == "StreamBusy"
    assert reload["result"]["__typename"] == "StreamBusy"


async def test_unknown_task_is_null_and_a_malformed_task_id_is_an_error(
    context: Context, stream_id: str
) -> None:
    """R-TK-05."""
    missing = await run(context, TASK_BY_ID, id=str(uuid4()))
    garbage = await run(context, TASK_BY_ID, id="not-an-id")
    malformed = await schema.execute(
        PUBLISH,
        variable_values={"input": {"streamId": stream_id, "taskId": "not-a-uuid"}},
        context_value=context,
    )

    assert (missing["task"], garbage["task"]) == (None, None)
    assert malformed.errors is not None
    assert malformed.errors[0].extensions == {"code": "validation_failed"}
