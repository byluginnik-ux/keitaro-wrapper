from typing import Any

import pytest

from app.graphql.schema import schema
from app.storage.memory import create_memory_storage
from tests.fakes import A, FakeKeitaro
from tests.graphql.support import context_for

pytestmark = pytest.mark.anyio

CREATE = """
mutation Create($input: CreateCampaignInput!) {
  createCampaign(input: $input) {
    __typename
    ... on Campaign { id keitaroId name alias country }
    ... on ValidationFailed { message fields { field message } }
    ... on KeitaroFailure { message createdDomain { id name } }
  }
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


async def create(keitaro: FakeKeitaro, **changes: object) -> dict[str, Any]:
    variables = {
        "input": {key: value for key, value in (INPUT | changes).items() if value is not None}
    }
    result = await schema.execute(
        CREATE, variable_values=variables, context_value=context_for(keitaro)
    )
    assert result.errors is None
    assert result.data is not None
    return result.data["createCampaign"]


async def test_created_campaign_is_returned_with_both_ids() -> None:
    """R-CR-08."""
    keitaro = FakeKeitaro()
    storage = create_memory_storage()

    result = await schema.execute(
        CREATE, variable_values={"input": INPUT}, context_value=context_for(keitaro, storage)
    )

    assert result.errors is None
    assert result.data is not None
    (stored,) = await storage.campaigns.list_recent()
    assert result.data["createCampaign"] == {
        "__typename": "Campaign",
        "id": str(stored.id),
        "keitaroId": stored.keitaro_id,
        "name": "test_bulygin_au",
        "alias": "alias001",
        "country": "AU",
    }
    assert stored.keitaro_id in keitaro.campaigns


async def test_invalid_input_names_the_fields() -> None:
    """R-CR-01, R-CR-03: a business refusal is data, not a GraphQL error."""
    answer = await create(FakeKeitaro(), name="au", offerId=1)

    assert answer["__typename"] == "ValidationFailed"
    assert [item["field"] for item in answer["fields"]] == ["name", "offerId"]
    assert all(item["message"] for item in answer["fields"])


async def test_new_domain_is_accepted_instead_of_an_existing_one() -> None:
    """R-CR-10."""
    keitaro = FakeKeitaro()

    answer = await create(keitaro, domainId=None, newDomainName="new.example.com")

    assert answer["__typename"] == "Campaign"
    assert keitaro.domains[-1].name == "new.example.com"


async def test_tracker_failure_reports_the_domain_left_behind() -> None:
    """R-CR-07, R-CR-12."""
    keitaro = FakeKeitaro(fail_on={"create_campaign"})

    answer = await create(keitaro, domainId=None, newDomainName="new.example.com")

    assert answer["__typename"] == "KeitaroFailure"
    assert answer["createdDomain"] == {"id": keitaro.domains[-1].id, "name": "new.example.com"}
    assert answer["message"]
