"""Creation of a campaign through the API (R-CR-01, 03, 08, 10, 12, 13)."""

from typing import Any
from uuid import uuid4

import pytest

from app.graphql.context import Context
from app.graphql.schema import schema
from app.messaging.ports import Message
from app.services.creator import CREATE_REQUESTED
from app.storage.memory import create_memory_storage
from tests.fakes import A, FakeKeitaro
from tests.graphql.support import context_for

pytestmark = pytest.mark.anyio

CREATE = """
mutation Create($input: CreateCampaignInput!) {
  createCampaign(input: $input) {
    __typename
    ... on Task { id kind status campaignId steps { name } }
    ... on ValidationFailed { message fields { field message } }
    ... on KeitaroFailure { message }
    ... on TaskKeyReused { message }
  }
}
"""
TASK = """
query($id: ID!) {
  task(id: $id) { status campaignId refusal { message createdDomain { id name } } }
}
"""
INPUT: dict[str, Any] = {
    "name": "test_bulygin_au",
    "country": "AU",
    "offerId": A,
    "groupId": 10332,
    "trafficSourceId": 836,
    "domainId": 1813,
}


async def create(context: Context, task_id: str, **changes: object) -> dict[str, Any]:
    fields = {key: value for key, value in (INPUT | changes).items() if value is not None}
    result = await schema.execute(
        CREATE, variable_values={"input": {"taskId": task_id, **fields}}, context_value=context
    )
    assert result.errors is None
    assert result.data is not None
    return result.data["createCampaign"]


async def work(context: Context, task_id: str, attempt: int = 1) -> dict[str, Any]:
    """Do what the worker does when the message arrives and read the task."""
    await context.creator.handle(Message(uuid4(), CREATE_REQUESTED, {"task_id": task_id}, attempt))
    result = await schema.execute(TASK, variable_values={"id": task_id}, context_value=context)
    assert result.data is not None
    return result.data["task"]


async def test_creation_is_queued_and_then_done() -> None:
    """R-CR-08, R-CR-13."""
    keitaro = FakeKeitaro()
    storage = create_memory_storage()
    context = context_for(keitaro, storage)
    task_id = str(uuid4())

    queued = await create(context, task_id)
    nothing_yet = dict(keitaro.campaigns)
    done = await work(context, task_id)

    (stored,) = await storage.campaigns.list_recent()
    assert queued == {
        "__typename": "Task",
        "id": task_id,
        "kind": "CREATE_CAMPAIGN",
        "status": "PENDING",
        "campaignId": None,
        "steps": [{"name": "queued"}],
    }
    assert nothing_yet == {}
    assert done == {"status": "SUCCEEDED", "campaignId": str(stored.id), "refusal": None}
    assert stored.keitaro_id in keitaro.campaigns


async def test_invalid_input_names_the_fields() -> None:
    """R-CR-01, R-CR-03: a business refusal is data, not a GraphQL error."""
    answer = await create(context_for(FakeKeitaro()), str(uuid4()), name="au", offerId=1)

    assert answer["__typename"] == "ValidationFailed"
    assert [item["field"] for item in answer["fields"]] == ["name", "offerId"]
    assert all(item["message"] for item in answer["fields"])


async def test_new_domain_is_accepted_instead_of_an_existing_one() -> None:
    """R-CR-10."""
    keitaro = FakeKeitaro()
    context = context_for(keitaro)
    task_id = str(uuid4())

    answer = await create(context, task_id, domainId=None, newDomainName="new.example.com")
    done = await work(context, task_id)

    assert (answer["__typename"], done["status"]) == ("Task", "SUCCEEDED")
    assert keitaro.domains[-1].name == "new.example.com"


async def test_rejected_task_reports_the_domain_left_behind() -> None:
    """R-CR-07, R-CR-12."""
    keitaro = FakeKeitaro(fail_on={"create_campaign"}, fail_status=400)
    context = context_for(keitaro)
    task_id = str(uuid4())

    await create(context, task_id, domainId=None, newDomainName="new.example.com")
    done = await work(context, task_id)

    assert done["status"] == "REJECTED"
    assert done["refusal"]["createdDomain"] == {
        "id": keitaro.domains[-1].id,
        "name": "new.example.com",
    }
    assert "new.example.com" in done["refusal"]["message"]


async def test_catalog_failure_and_task_id_misuse_are_typed() -> None:
    """R-KT-02, R-TK-04."""
    context = context_for(FakeKeitaro())
    task_id = str(uuid4())
    await create(context, task_id)

    again = await create(context, task_id)
    reused = await create(context, task_id, name="test_bulygin_other")
    broken = await create(context_for(FakeKeitaro(fail_on={"list_groups"})), str(uuid4()))
    malformed = await schema.execute(
        CREATE, variable_values={"input": {"taskId": "nope", **INPUT}}, context_value=context
    )

    assert (again["__typename"], again["id"]) == ("Task", task_id)
    assert reused["__typename"] == "TaskKeyReused"
    assert broken["__typename"] == "KeitaroFailure"
    assert malformed.errors is not None
    assert malformed.errors[0].extensions == {"code": "validation_failed"}
