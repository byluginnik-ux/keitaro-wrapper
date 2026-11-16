from collections.abc import Sequence

import httpx

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

API_PREFIX = "/admin_api/v1"
READ_ATTEMPTS = 3


def create_http_client(base_url: str, api_key: str, timeout: float = 15.0) -> httpx.AsyncClient:
    """Build the HTTP client the tracker is reached through; the key lives only in its headers."""
    raise NotImplementedError


class KeitaroClient:
    """Typed access to the part of Keitaro Admin API this project uses."""

    def __init__(self, http: httpx.AsyncClient, retry_delay: float = 0.2) -> None:
        self._http = http
        self._retry_delay = retry_delay

    async def list_domains(self) -> list[Domain]:
        raise NotImplementedError

    async def create_domain(self, name: str) -> Domain:
        raise NotImplementedError

    async def list_groups(self) -> list[Group]:
        raise NotImplementedError

    async def list_traffic_sources(self) -> list[TrafficSource]:
        raise NotImplementedError

    async def list_offers(self) -> list[Offer]:
        raise NotImplementedError

    async def create_campaign(self, campaign: NewCampaign) -> Campaign:
        raise NotImplementedError

    async def delete_campaign(self, campaign_id: int) -> None:
        raise NotImplementedError

    async def create_stream(self, stream: NewStream) -> Stream:
        raise NotImplementedError

    async def list_campaign_streams(self, campaign_id: int) -> list[Stream]:
        raise NotImplementedError

    async def replace_stream_offers(self, stream_id: int, offers: Sequence[StreamOffer]) -> Stream:
        raise NotImplementedError
