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
    _next_id: int = 1000

    def _enter(self, method: str) -> None:
        self.calls[method] += 1
        if method in self.fail_on:
            message = f"Keitaro: {method} failed"
            raise KeitaroError(message, 500)

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
        return created

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
        return created

    async def list_campaign_streams(self, campaign_id: int) -> list[Stream]:
        self._enter("list_campaign_streams")
        found = [stream for stream in self.streams.values() if stream.campaign_id == campaign_id]
        return sorted(found, key=lambda stream: stream.position)

    async def replace_stream_offers(self, stream_id: int, offers: Sequence[StreamOffer]) -> Stream:
        self._enter("replace_stream_offers")
        updated = self.streams[stream_id].model_copy(update={"offers": tuple(offers)})
        self.streams[stream_id] = updated
        return updated
