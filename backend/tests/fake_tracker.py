"""A stand-in for Keitaro Admin API over HTTP, for end-to-end tests and for looking at the UI.

Run from `backend/`: `uv run uvicorn tests.fake_tracker:app --port 8799`.
Routes under `/__test` belong to the tests: they build a scenario and change the tracker
behind the service's back, as an operator would in the tracker's admin panel.
"""

from itertools import count
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.keitaro.models import (
    Campaign,
    Domain,
    Group,
    NewCampaign,
    NewStream,
    Offer,
    Stream,
    StreamOffer,
    TrafficSource,
)
from app.services.errors import KeitaroError
from tests.fakes import FakeKeitaro, sample_offers

EXTRA_OFFERS = [
    Offer(id=24800, name="24800 Flexacil [JOINT-PE] [land es -]"),
    Offer(id=25327, name="25327 Flexacil [JOINT-AU] [pl 50%]"),
    Offer(id=26001, name="26001 Cardiolis [HEART-KZ] [land ru -]"),
]

app = FastAPI(title="Fake Keitaro")
api = "/admin_api/v1"
keitaro = FakeKeitaro(offers=[*sample_offers(), *EXTRA_OFFERS])
scenario_ids = count(90000)


class Scenario(BaseModel):
    offers: list[tuple[int, int]] = [(11111, 34), (11112, 33), (11113, 33)]


class Offers(BaseModel):
    offers: list[StreamOffer]


class Failure(BaseModel):
    method: str
    on: bool = True


class NewDomain(BaseModel):
    name: str


@app.exception_handler(KeitaroError)
async def tracker_error(_request: Request, error: KeitaroError) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=error.status or 500)


@app.get(f"{api}/domains")
async def domains() -> list[Domain]:
    return await keitaro.list_domains()


@app.post(f"{api}/domains")
async def create_domain(body: NewDomain) -> Domain:
    return await keitaro.create_domain(body.name)


@app.get(f"{api}/groups")
async def groups() -> list[Group]:
    return await keitaro.list_groups()


@app.get(f"{api}/traffic_sources")
async def traffic_sources() -> list[TrafficSource]:
    return await keitaro.list_traffic_sources()


@app.get(f"{api}/offers")
async def offers() -> list[Offer]:
    return await keitaro.list_offers()


@app.get(f"{api}/campaigns/{{campaign_id}}")
async def campaign(campaign_id: int) -> Campaign:
    return await keitaro.get_campaign(campaign_id)


@app.post(f"{api}/campaigns")
async def create_campaign(body: NewCampaign) -> Campaign:
    return await keitaro.create_campaign(body)


@app.delete(f"{api}/campaigns/{{campaign_id}}")
async def delete_campaign(campaign_id: int) -> dict[str, bool]:
    await keitaro.delete_campaign(campaign_id)
    return {"success": True}


@app.get(f"{api}/campaigns/{{campaign_id}}/streams", response_model_by_alias=True)
async def campaign_streams(campaign_id: int) -> list[Stream]:
    await keitaro.get_campaign(campaign_id)
    return await keitaro.list_campaign_streams(campaign_id)


@app.post(f"{api}/streams", response_model_by_alias=True)
async def create_stream(body: dict[str, Any]) -> Stream:
    # on the wire the kind of a stream is called `schema`
    return await keitaro.create_stream(
        NewStream.model_validate({**body, "kind": body.get("schema")})
    )


@app.put(f"{api}/streams/{{stream_id}}", response_model_by_alias=True)
async def replace_offers(stream_id: int, body: Offers) -> Stream:
    return await keitaro.replace_stream_offers(stream_id, body.offers)


@app.post("/__test/campaign")
async def make_scenario(body: Scenario) -> dict[str, int]:
    """Build the starting point of scenarios S1–S8 under fresh identifiers."""
    campaign_id, redirect_id, offers_id = (next(scenario_ids) for _ in range(3))
    keitaro.campaigns[campaign_id] = Campaign(
        id=campaign_id,
        name=f"test_bulygin_scenario_{campaign_id}",
        alias=f"scenario{campaign_id}",
        domain_id=1813,
        group_id=10332,
        traffic_source_id=836,
    )
    for stream_id, name, position, kind in (
        (redirect_id, "Flow 1", 1, "redirect"),
        (offers_id, "Flow 2", 2, "landings"),
    ):
        keitaro.streams[stream_id] = Stream(
            id=stream_id,
            campaign_id=campaign_id,
            name=name,
            position=position,
            type="regular",
            schema=kind,
        )
    await keitaro.replace_stream_offers(
        offers_id, [StreamOffer(offer_id=offer_id, share=share) for offer_id, share in body.offers]
    )
    keitaro.calls.clear()
    return {"campaignId": campaign_id, "redirectStreamId": redirect_id, "offersStreamId": offers_id}


@app.put("/__test/streams/{stream_id}/offers", response_model_by_alias=True)
async def change_behind_the_back(stream_id: int, body: Scenario) -> Stream:
    return await keitaro.replace_stream_offers(
        stream_id, [StreamOffer(offer_id=offer_id, share=share) for offer_id, share in body.offers]
    )


@app.get("/__test/streams/{stream_id}/offers")
async def stream_offers(stream_id: int) -> list[tuple[int, int]]:
    return [(offer.offer_id, offer.share) for offer in keitaro.streams[stream_id].offers]


@app.get("/__test/campaigns")
async def all_campaigns() -> list[Campaign]:
    return list(keitaro.campaigns.values())


@app.post("/__test/fail")
async def fail(body: Failure) -> set[str]:
    """Make one method of the tracker fail until told otherwise."""
    (keitaro.fail_on.add if body.on else keitaro.fail_on.discard)(body.method)
    return keitaro.fail_on
