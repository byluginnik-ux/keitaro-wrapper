from typing import Any

import pytest

from app.graphql.context import Context
from app.graphql.schema import schema
from tests.fakes import CAMPAIGN_ID, OFFERS_STREAM_ID, A, tracker_with_campaign
from tests.graphql.support import context_for

pytestmark = pytest.mark.anyio

FETCH = """
mutation Fetch($id: Int!) {
  fetchStreams(campaignKeitaroId: $id) {
    __typename
    ... on StreamsFetched {
      campaign { id keitaroId name }
      streams {
        id keitaroId campaignId name position kind dirty
        offers { offerId name share pinned state changed published { share state pinned } }
      }
    }
    ... on DraftNotPublished { message }
    ... on CampaignNotFound { message }
    ... on KeitaroFailure { message }
  }
}
"""
EDITOR_PAGE = """
query Editor($id: ID!) {
  campaigns { id keitaroId }
  campaign(id: $id) { id name alias country }
  streams(campaignId: $id) { name dirty offers { offerId share } }
}
"""


async def run(context: Context, document: str, **variables: object) -> dict[str, Any]:
    result = await schema.execute(document, variable_values=variables, context_value=context)
    assert result.errors is None
    assert result.data is not None
    return result.data


async def test_fetched_streams_come_with_their_offers() -> None:
    """S1, R-ED-01…03."""
    context = context_for(tracker_with_campaign())

    answer = (await run(context, FETCH, id=CAMPAIGN_ID))["fetchStreams"]

    assert answer["__typename"] == "StreamsFetched"
    assert answer["campaign"]["keitaroId"] == CAMPAIGN_ID
    first, second = answer["streams"]
    assert (first["name"], first["kind"], first["offers"], first["dirty"]) == (
        "Flow 1",
        "redirect",
        [],
        False,
    )
    assert second["keitaroId"] == OFFERS_STREAM_ID
    assert second["campaignId"] == answer["campaign"]["id"]
    assert second["offers"][0] == {
        "offerId": A,
        "name": "Offer A",
        "share": 34,
        "pinned": False,
        "state": "ACTIVE",
        "changed": False,
        "published": {"share": 34, "state": "ACTIVE", "pinned": False},
    }


async def test_editor_page_reads_what_was_stored() -> None:
    """R-ED-01."""
    context = context_for(tracker_with_campaign())
    fetched = (await run(context, FETCH, id=CAMPAIGN_ID))["fetchStreams"]
    campaign_id = fetched["campaign"]["id"]

    page = await run(context, EDITOR_PAGE, id=campaign_id)

    assert page["campaigns"] == [{"id": campaign_id, "keitaroId": CAMPAIGN_ID}]
    assert page["campaign"] == {
        "id": campaign_id,
        "name": "test_bulygin_sample",
        "alias": "sample",
        "country": None,
    }
    assert [stream["name"] for stream in page["streams"]] == ["Flow 1", "Flow 2"]
    assert [offer["share"] for offer in page["streams"][1]["offers"]] == [34, 33, 33]


@pytest.mark.parametrize("campaign_id", ["9f1c2f6e-0000-4000-8000-000000000000", "not-an-id"])
async def test_unknown_campaign_is_null_and_has_no_streams(campaign_id: str) -> None:
    """R-ED-07: an address typed by hand must not break the page."""
    page = await run(context_for(tracker_with_campaign()), EDITOR_PAGE, id=campaign_id)

    assert page["campaign"] is None
    assert page["streams"] == []


async def test_missing_campaign_is_a_typed_refusal() -> None:
    """R-ED-07."""
    answer = (await run(context_for(tracker_with_campaign()), FETCH, id=1))["fetchStreams"]

    assert answer["__typename"] == "CampaignNotFound"
    assert "1" in answer["message"]


async def test_tracker_failure_is_a_typed_refusal() -> None:
    """R-KT-02."""
    keitaro = tracker_with_campaign()
    keitaro.fail_on.add("list_campaign_streams")

    answer = (await run(context_for(keitaro), FETCH, id=CAMPAIGN_ID))["fetchStreams"]

    assert answer == {
        "__typename": "KeitaroFailure",
        "message": "Keitaro: list_campaign_streams failed",
    }
