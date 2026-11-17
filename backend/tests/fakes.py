from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

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

A, B, C, D = 11111, 11112, 11113, 11114


def sample_offers() -> list[Offer]:
    return [
        Offer(id=A, name="Offer A"),
        Offer(id=B, name="Offer B"),
        Offer(id=C, name="Offer C"),
        Offer(id=D, name="Offer D"),
    ]


@dataclass
class FakeKeitaro:
    """In-memory tracker: the same contract as the HTTP client, state visible to tests."""

    domains: list[Domain] = field(
        default_factory=lambda: [Domain(id=1813, name="tracker.example.com")]
    )
    groups: list[Group] = field(default_factory=lambda: [Group(id=10332, name="FORTESTS")])
    sources: list[TrafficSource] = field(
        default_factory=lambda: [TrafficSource(id=836, name="FORTESTS")]
    )
    offers: list[Offer] = field(default_factory=sample_offers)
    campaigns: dict[int, Campaign] = field(default_factory=dict[int, Campaign])
    streams: dict[int, Stream] = field(default_factory=dict[int, Stream])
    stream_requests: list[NewStream] = field(default_factory=list[NewStream])
    calls: Counter[str] = field(default_factory=Counter[str])
    fail_on: set[str] = field(default_factory=set[str])
    fail_status: int | None = 500
    """What a failing method answers with; None means there was no answer at all."""
    lose_answer: set[str] = field(default_factory=set[str])
    """Methods that do their work and then lose the answer on its way back."""
    _next_id: int = 1000

    def _enter(self, method: str) -> None:
        self.calls[method] += 1
        if method in self.fail_on:
            message = f"Keitaro: {method} failed"
            raise KeitaroError(message, self.fail_status)

    def _leave(self, method: str) -> None:
        if method in self.lose_answer:
            message = f"Keitaro: no answer to {method}"
            raise KeitaroError(message)

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id

    async def list_domains(self) -> list[Domain]:
        self._enter("list_domains")
        return list(self.domains)

    async def create_domain(self, name: str) -> Domain:
        self._enter("create_domain")
        domain = Domain(id=self._new_id(), name=name)
        self.domains.append(domain)
        self._leave("create_domain")
        return domain

    async def list_groups(self) -> list[Group]:
        self._enter("list_groups")
        return list(self.groups)

    async def list_traffic_sources(self) -> list[TrafficSource]:
        self._enter("list_traffic_sources")
        return list(self.sources)

    async def list_offers(self) -> list[Offer]:
        self._enter("list_offers")
        return list(self.offers)

    async def get_campaign(self, campaign_id: int) -> Campaign:
        self._enter("get_campaign")
        if campaign_id not in self.campaigns:
            message = "Keitaro ответил 404"
            raise KeitaroError(message, 404)
        return self.campaigns[campaign_id]

    async def create_campaign(self, campaign: NewCampaign) -> Campaign:
        self._enter("create_campaign")
        created = Campaign(id=self._new_id(), **campaign.model_dump(exclude={"type"}))
        self.campaigns[created.id] = created
        self._leave("create_campaign")
        return created

    async def find_campaign_by_alias(self, alias: str) -> Campaign | None:
        self._enter("find_campaign_by_alias")
        return next((item for item in self.campaigns.values() if item.alias == alias), None)

    async def delete_campaign(self, campaign_id: int) -> None:
        self._enter("delete_campaign")
        del self.campaigns[campaign_id]
        self.streams = {
            key: stream for key, stream in self.streams.items() if stream.campaign_id != campaign_id
        }

    async def create_stream(self, stream: NewStream) -> Stream:
        self._enter("create_stream")
        self.stream_requests.append(stream)
        created = Stream(
            id=self._new_id(),
            campaign_id=stream.campaign_id,
            name=stream.name,
            position=stream.position,
            type=stream.type,
            schema=stream.kind,
            offers=stream.offers,
        )
        self.streams[created.id] = created
        self._leave("create_stream")
        return created

    async def list_campaign_streams(self, campaign_id: int) -> list[Stream]:
        self._enter("list_campaign_streams")
        found = [stream for stream in self.streams.values() if stream.campaign_id == campaign_id]
        return sorted(found, key=lambda stream: stream.position)

    async def replace_stream_offers(self, stream_id: int, offers: Sequence[StreamOffer]) -> Stream:
        self._enter("replace_stream_offers")
        updated = self.streams[stream_id].model_copy(update={"offers": tuple(offers)})
        self.streams[stream_id] = updated
        self._leave("replace_stream_offers")
        return updated


CAMPAIGN_ID, REDIRECT_STREAM_ID, OFFERS_STREAM_ID = 93212, 564220, 564221


def shares(*pairs: tuple[int, int]) -> tuple[StreamOffer, ...]:
    return tuple(StreamOffer(offer_id=offer_id, share=share) for offer_id, share in pairs)


def tracker_with_campaign(*offers: tuple[int, int]) -> FakeKeitaro:
    """Build the starting point of scenarios S1–S8: a redirect stream and a stream of offers."""
    keitaro = FakeKeitaro()
    keitaro.campaigns[CAMPAIGN_ID] = Campaign(
        id=CAMPAIGN_ID,
        name="test_bulygin_sample",
        alias="sample",
        domain_id=1813,
        group_id=10332,
        traffic_source_id=836,
    )
    keitaro.streams[REDIRECT_STREAM_ID] = Stream(
        id=REDIRECT_STREAM_ID,
        campaign_id=CAMPAIGN_ID,
        name="Flow 1",
        position=1,
        type="regular",
        schema="redirect",
    )
    keitaro.streams[OFFERS_STREAM_ID] = Stream(
        id=OFFERS_STREAM_ID,
        campaign_id=CAMPAIGN_ID,
        name="Flow 2",
        position=2,
        type="regular",
        schema="landings",
        offers=shares(*(offers or ((A, 34), (B, 33), (C, 33)))),
    )
    return keitaro
