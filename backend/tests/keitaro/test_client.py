import json

import httpx
import pytest
import respx

from app.keitaro.client import KeitaroClient
from app.keitaro.models import NewCampaign, NewStream, StreamFilter, StreamOffer
from app.services.errors import KeitaroError
from tests.keitaro.conftest import API_KEY, fixture_json, fixture_text

pytestmark = pytest.mark.anyio


def sent_json(route: respx.Route) -> object:
    return json.loads(route.calls.last.request.content)


async def test_offers_are_parsed_and_unknown_fields_ignored(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-01."""
    tracker.get("/offers").respond(json=fixture_json("offers.json"))

    offers = await keitaro.list_offers()

    assert [(offer.id, offer.name) for offer in offers] == [
        (11111, "Offer A"),
        (11112, "Offer B"),
        (11113, "Offer C"),
        (11114, "Offer D"),
    ]


async def test_every_request_carries_the_api_key(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    route = tracker.get("/domains").respond(json=fixture_json("domains.json"))

    domains = await keitaro.list_domains()

    assert route.calls.last.request.headers["Api-Key"] == API_KEY
    assert domains[0].name == "tracker.example.com"


async def test_groups_are_requested_for_campaigns(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    route = tracker.get("/groups", params={"type": "campaigns"}).respond(
        json=fixture_json("groups.json")
    )

    groups = await keitaro.list_groups()

    assert route.called
    assert [(group.id, group.name) for group in groups] == [(10332, "FORTESTS")]


async def test_traffic_sources_are_parsed(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    tracker.get("/traffic_sources").respond(json=fixture_json("traffic_sources.json"))

    assert [source.name for source in await keitaro.list_traffic_sources()] == ["FORTESTS"]


async def test_campaign_streams_keep_order_and_offer_shares(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-ED-01…03 rely on this shape."""
    tracker.get("/campaigns/93212/streams").respond(json=fixture_json("campaign_streams.json"))

    redirect, offers = await keitaro.list_campaign_streams(93212)

    assert (redirect.id, redirect.kind, redirect.offers) == (564220, "redirect", ())
    assert offers.kind == "landings"
    assert [(link.offer_id, link.share) for link in offers.offers] == [
        (11111, 34),
        (11112, 33),
        (11113, 33),
    ]


async def test_campaign_is_created_with_domain_group_and_source(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-CR-04."""
    route = tracker.post("/campaigns").respond(json=fixture_json("campaign.json"))

    campaign = await keitaro.create_campaign(
        NewCampaign(
            name="test_bulygin_sample",
            alias="sample",
            domain_id=1813,
            group_id=10332,
            traffic_source_id=836,
        )
    )

    assert sent_json(route) == {
        "name": "test_bulygin_sample",
        "alias": "sample",
        "domain_id": 1813,
        "group_id": 10332,
        "traffic_source_id": 836,
        "type": "position",
    }
    assert campaign.id == 93212


async def test_redirect_stream_is_sent_in_the_shape_the_tracker_expects(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-CR-05: values verified against the live tracker."""
    route = tracker.post("/streams").respond(json=fixture_json("campaign_streams.json")[0])

    stream = await keitaro.create_stream(
        NewStream(
            campaign_id=93212,
            name="Flow 1",
            position=1,
            kind="redirect",
            action_payload="https://google.com",
            filters=(StreamFilter(name="country", mode="accept", payload=("AU",)),),
        )
    )

    assert sent_json(route) == {
        "campaign_id": 93212,
        "name": "Flow 1",
        "position": 1,
        "schema": "redirect",
        "type": "regular",
        "action_type": "http",
        "action_payload": "https://google.com",
        "filters": [{"name": "country", "mode": "accept", "payload": ["AU"]}],
        "offers": [],
    }
    assert stream.id == 564220


async def test_stream_offers_are_replaced_as_a_whole(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-ED-20."""
    route = tracker.put("/streams/564221").respond(json=fixture_json("campaign_streams.json")[1])

    await keitaro.replace_stream_offers(
        564221, [StreamOffer(offer_id=11111, share=50), StreamOffer(offer_id=11112, share=50)]
    )

    assert sent_json(route) == {
        "offers": [
            {"offer_id": 11111, "share": 50, "state": "active"},
            {"offer_id": 11112, "share": 50, "state": "active"},
        ]
    }


async def test_domain_is_created_by_name(tracker: respx.MockRouter, keitaro: KeitaroClient) -> None:
    """R-CR-10."""
    route = tracker.post("/domains").respond(json=fixture_json("domains.json")[0])

    domain = await keitaro.create_domain("tracker.example.com")

    assert sent_json(route) == {"name": "tracker.example.com"}
    assert domain.id == 1813


async def test_campaign_is_deleted(tracker: respx.MockRouter, keitaro: KeitaroClient) -> None:
    """R-CR-07."""
    route = tracker.delete("/campaigns/93212").respond(json=fixture_json("campaign.json"))

    await keitaro.delete_campaign(93212)

    assert route.call_count == 1


async def test_tracker_error_message_is_surfaced(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-02."""
    tracker.get("/offers").respond(401, json=fixture_json("error_invalid_key.json"))

    with pytest.raises(KeitaroError) as raised:
        await keitaro.list_offers()

    assert raised.value.status == 401
    assert "Invalid API key" in str(raised.value)
    assert raised.value.code == "keitaro_error"


async def test_html_404_becomes_a_tracker_error(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-06."""
    tracker.get("/campaigns/1/streams").respond(404, html=fixture_text("error_not_found.html"))

    with pytest.raises(KeitaroError) as raised:
        await keitaro.list_campaign_streams(1)

    assert raised.value.status == 404
    assert "<html>" not in str(raised.value)


async def test_unreadable_success_body_is_a_tracker_error(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-02."""
    tracker.get("/offers").respond(200, text="not json")

    with pytest.raises(KeitaroError):
        await keitaro.list_offers()


async def test_unexpected_shape_is_a_tracker_error(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-02."""
    tracker.get("/offers").respond(200, json=[{"name": "no id"}])

    with pytest.raises(KeitaroError):
        await keitaro.list_offers()


async def test_read_is_retried_after_server_errors(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-03."""
    route = tracker.get("/offers").mock(
        side_effect=[
            httpx.Response(502),
            httpx.ConnectError("boom"),
            httpx.Response(200, json=fixture_json("offers.json")),
        ]
    )

    offers = await keitaro.list_offers()

    assert route.call_count == 3
    assert len(offers) == 4


async def test_read_gives_up_after_three_attempts(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-03."""
    route = tracker.get("/offers").respond(503)

    with pytest.raises(KeitaroError) as raised:
        await keitaro.list_offers()

    assert route.call_count == 3
    assert raised.value.status == 503


async def test_client_errors_are_not_retried(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-03: only network failures and 5xx are worth repeating."""
    route = tracker.get("/offers").respond(401, json=fixture_json("error_invalid_key.json"))

    with pytest.raises(KeitaroError):
        await keitaro.list_offers()

    assert route.call_count == 1


async def test_writes_are_never_retried(tracker: respx.MockRouter, keitaro: KeitaroClient) -> None:
    """R-KT-03: a repeated write could create a second campaign."""
    route = tracker.post("/domains").respond(500)

    with pytest.raises(KeitaroError):
        await keitaro.create_domain("tracker.example.com")

    assert route.call_count == 1


async def test_timeout_is_a_tracker_error(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-02."""
    tracker.post("/domains").mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(KeitaroError) as raised:
        await keitaro.create_domain("tracker.example.com")

    assert raised.value.status is None


async def test_api_key_never_appears_in_errors(
    tracker: respx.MockRouter, keitaro: KeitaroClient
) -> None:
    """R-KT-04."""
    tracker.get("/offers").respond(401, json=fixture_json("error_invalid_key.json"))

    with pytest.raises(KeitaroError) as raised:
        await keitaro.list_offers()

    assert API_KEY not in str(raised.value)
    assert API_KEY not in repr(raised.value)
