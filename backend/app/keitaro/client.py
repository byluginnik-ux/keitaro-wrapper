import asyncio
from collections.abc import Sequence
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

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

API_PREFIX = "/admin_api/v1"
READ_ATTEMPTS = 3
SERVER_ERROR = 500
CLIENT_ERROR = 400

type Json = dict[str, Any] | list[Any]


def create_http_client(base_url: str, api_key: str, timeout: float = 15.0) -> httpx.AsyncClient:
    """Build the HTTP client the tracker is reached through; the key lives only in its headers."""
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/") + API_PREFIX,
        headers={"Api-Key": api_key, "Accept": "application/json"},
        timeout=timeout,
    )


class KeitaroClient:
    """Typed access to the part of Keitaro Admin API this project uses."""

    def __init__(self, http: httpx.AsyncClient, retry_delay: float = 0.2) -> None:
        self._http = http
        self._retry_delay = retry_delay

    async def list_domains(self) -> list[Domain]:
        return _parse(list[Domain], await self._read("/domains"))

    async def create_domain(self, name: str) -> Domain:
        return _parse(Domain, await self._write("POST", "/domains", {"name": name}))

    async def list_groups(self) -> list[Group]:
        return _parse(list[Group], await self._read("/groups", {"type": "campaigns"}))

    async def list_traffic_sources(self) -> list[TrafficSource]:
        return _parse(list[TrafficSource], await self._read("/traffic_sources"))

    async def list_offers(self) -> list[Offer]:
        return _parse(list[Offer], await self._read("/offers"))

    async def get_campaign(self, campaign_id: int) -> Campaign:
        raise NotImplementedError

    async def create_campaign(self, campaign: NewCampaign) -> Campaign:
        return _parse(Campaign, await self._write("POST", "/campaigns", campaign.model_dump()))

    async def delete_campaign(self, campaign_id: int) -> None:
        await self._write("DELETE", f"/campaigns/{campaign_id}")

    async def create_stream(self, stream: NewStream) -> Stream:
        body = stream.model_dump(by_alias=True, mode="json")
        return _parse(Stream, await self._write("POST", "/streams", body))

    async def list_campaign_streams(self, campaign_id: int) -> list[Stream]:
        return _parse(list[Stream], await self._read(f"/campaigns/{campaign_id}/streams"))

    async def replace_stream_offers(self, stream_id: int, offers: Sequence[StreamOffer]) -> Stream:
        body = {"offers": [offer.model_dump() for offer in offers]}
        return _parse(Stream, await self._write("PUT", f"/streams/{stream_id}", body))

    async def _read(self, path: str, params: dict[str, str] | None = None) -> Json:
        """GET with retries: repeating a read is safe (R-KT-03)."""
        for attempt in range(1, READ_ATTEMPTS + 1):
            try:
                return await self._send("GET", path, params=params)
            except KeitaroError as error:
                retryable = error.status is None or error.status >= SERVER_ERROR
                if not retryable or attempt == READ_ATTEMPTS:
                    raise
                await asyncio.sleep(self._retry_delay * attempt)
        raise AssertionError  # pragma: no cover — the loop always returns or raises

    async def _write(self, method: str, path: str, body: Json | None = None) -> Json:
        """Send once: a repeated write could create a duplicate (R-KT-03)."""
        return await self._send(method, path, body=body)

    async def _send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: Json | None = None,
    ) -> Json:
        try:
            response = await self._http.request(method, path, params=params, json=body)
        except httpx.HTTPError as error:
            message = f"Keitaro недоступен: {type(error).__name__}"
            raise KeitaroError(message) from error
        if response.status_code >= CLIENT_ERROR:
            raise KeitaroError(_error_text(response), response.status_code)
        try:
            payload: Json = response.json()
        except ValueError as error:
            message = "Keitaro вернул ответ, который не удалось разобрать"
            raise KeitaroError(message, response.status_code) from error
        return payload


def _error_text(response: httpx.Response) -> str:
    """Take the tracker's own message when it sent JSON; an HTML page carries nothing useful."""
    try:
        payload: Any = response.json()
    except ValueError:
        return f"Keitaro ответил {response.status_code}"
    if isinstance(payload, dict):
        detail: Any = payload.get("error")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType] — arbitrary JSON
        if isinstance(detail, str):
            return f"Keitaro: {detail}"
    return f"Keitaro ответил {response.status_code}"


def _parse[T](model: type[T], payload: Json) -> T:
    try:
        return TypeAdapter(model).validate_python(payload)
    except ValidationError as error:
        message = f"Keitaro вернул неожиданный ответ ({error.error_count()} расхождений со схемой)"
        raise KeitaroError(message) from error
