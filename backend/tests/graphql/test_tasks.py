"""Tasks and the queue through the API (R-TK-06…09)."""

from typing import Any
from uuid import uuid4

import pytest

from app.graphql.context import Context
from app.graphql.schema import schema
from app.messaging.ports import Message
from app.services.creator import CREATE_REQUESTED
from app.services.publisher import PUBLISH_REQUESTED
from tests.fakes import CAMPAIGN_ID, D, FakeKeitaro, tracker_with_campaign
from tests.graphql.support import NOW, context_for
from tests.graphql.test_draft_mutations import FETCH, act, run

pytestmark = pytest.mark.anyio

PUBLISH = """
mutation($input: PublishStreamInput!) { publishStream(input: $input) { __typename } }
"""
LIST = """
query($statuses: [TaskStatus!], $kind: TaskKind, $first: Int!) {
  tasks(statuses: $statuses, kind: $kind, first: $first) { id status retryOf }
}
"""
QUEUE = """
{
  queueStatus {
    tasks { status count } outboxWaiting outboxOldest queues { name ready consumers }
  }
}
"""
ANSWER = "__typename ... on Task { id status retryOf } ... on TaskNotFound { message }"
CANCEL = f"""
mutation($id: ID!) {{
  result: cancelTask(id: $id) {{ {ANSWER} ... on TaskNotCancellable {{ message }} }}
}}
"""
RETRY = f"""
mutation($input: RetryTaskInput!) {{
  result: retryTask(input: $input) {{ {ANSWER} ... on TaskNotRetryable {{ message }} }}
}}
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
    stream = fetched["fetchStreams"]["streams"][1]["id"]
    await act(context, "addOffer", stream, D)
    return stream


async def queue(context: Context, stream_id: str) -> str:
    task_id = str(uuid4())
    await run(context, PUBLISH, input={"streamId": stream_id, "taskId": task_id})
    return task_id


async def work(context: Context, task_id: str) -> None:
    await context.publisher.handle(Message(uuid4(), PUBLISH_REQUESTED, {"task_id": task_id}))


async def reject(context: Context, keitaro: FakeKeitaro, stream_id: str) -> str:
    keitaro.fail_on.add("replace_stream_offers")
    keitaro.fail_status = 400
    task_id = await queue(context, stream_id)
    await work(context, task_id)
    keitaro.fail_on.clear()
    return task_id


async def steer(context: Context, document: str, **variables: object) -> dict[str, Any]:
    return (await run(context, document, **variables))["result"]


async def test_tasks_are_listed_filtered_and_counted(
    context: Context, keitaro: FakeKeitaro, stream_id: str
) -> None:
    """R-TK-06, R-TK-07."""
    failed = await reject(context, keitaro, stream_id)
    waiting = await queue(context, stream_id)

    everything = await run(context, LIST, first=50)
    filtered = await run(context, LIST, statuses=["REJECTED"], kind="PUBLISH_STREAM", first=50)
    state = (await run(context, QUEUE))["queueStatus"]

    assert {task["id"] for task in everything["tasks"]} == {failed, waiting}
    assert filtered["tasks"] == [{"id": failed, "status": "REJECTED", "retryOf": None}]
    assert state == {
        "tasks": [{"status": "PENDING", "count": 1}, {"status": "REJECTED", "count": 1}],
        "outboxWaiting": 3,
        "outboxOldest": NOW.isoformat(),
        "queues": [
            {"name": "keitaro.tasks", "ready": 0, "consumers": 0},
            {"name": "keitaro.tasks.dead", "ready": 0, "consumers": 0},
        ],
    }


async def test_waiting_task_is_cancelled_once(context: Context, stream_id: str) -> None:
    """R-TK-08."""
    task_id = await queue(context, stream_id)

    cancelled = await steer(context, CANCEL, id=task_id)
    again = await steer(context, CANCEL, id=task_id)
    unknown = await steer(context, CANCEL, id="not-an-id")
    edited = await act(context, "removeOffer", stream_id, D)

    assert cancelled == {
        "__typename": "Task",
        "id": task_id,
        "status": "CANCELLED",
        "retryOf": None,
    }
    assert (again["__typename"], unknown["__typename"]) == ("TaskNotCancellable", "TaskNotFound")
    assert edited["__typename"] == "Stream"


async def test_rejected_publication_is_repeated(
    context: Context, keitaro: FakeKeitaro, stream_id: str
) -> None:
    """R-TK-09."""
    failed = await reject(context, keitaro, stream_id)
    new_id = str(uuid4())

    again = await steer(context, RETRY, input={"taskId": failed, "newTaskId": new_id})
    not_rejected = await steer(context, RETRY, input={"taskId": new_id, "newTaskId": str(uuid4())})
    unknown = await steer(context, RETRY, input={"taskId": str(uuid4()), "newTaskId": str(uuid4())})
    malformed = await schema.execute(
        RETRY,
        variable_values={"input": {"taskId": failed, "newTaskId": "not-a-uuid"}},
        context_value=context,
    )

    assert again == {"__typename": "Task", "id": new_id, "status": "PENDING", "retryOf": failed}
    assert (not_rejected["__typename"], unknown["__typename"]) == (
        "TaskNotRetryable",
        "TaskNotFound",
    )
    assert malformed.errors is not None
    assert malformed.errors[0].extensions == {"code": "validation_failed"}


async def test_rejected_creation_is_repeated_through_the_api() -> None:
    """R-TK-09."""
    keitaro = FakeKeitaro(fail_on={"create_stream"}, fail_status=400)
    context = context_for(keitaro)
    failed = str(uuid4())
    create = """
    mutation($input: CreateCampaignInput!) { createCampaign(input: $input) { __typename } }
    """
    form = {
        "taskId": failed,
        "name": "test_bulygin_au",
        "country": "AU",
        "offerId": D,
        "groupId": 10332,
        "trafficSourceId": 836,
        "domainId": 1813,
    }
    await run(context, create, input=form)
    await context.creator.handle(Message(uuid4(), CREATE_REQUESTED, {"task_id": failed}))
    keitaro.fail_on.clear()
    retry = RETRY.replace(
        "... on TaskNotRetryable", "... on ValidationFailed { message } ... on TaskNotRetryable"
    )

    again = await steer(context, retry, input={"taskId": failed, "newTaskId": str(uuid4())})
    keitaro.groups.clear()
    refused = await steer(context, retry, input={"taskId": failed, "newTaskId": str(uuid4())})

    assert (again["__typename"], again["status"], again["retryOf"]) == ("Task", "PENDING", failed)
    assert refused["__typename"] == "ValidationFailed"
