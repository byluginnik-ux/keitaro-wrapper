import asyncio
import re
import secrets
import string
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from app.keitaro import models as tracker
from app.keitaro.gateway import KeitaroGateway
from app.messaging.ports import Message
from app.services.catalog import CatalogService
from app.services.countries import find_country
from app.services.errors import ValidationError
from app.services.models import (
    Task,
)
from app.storage.ports import Storage

CREATE_REQUESTED = "campaign.create.requested"
CREATED = "campaign.created"
CREATE_REJECTED = "campaign.create.rejected"

SERVER_ERROR = 500

ALIAS_ALPHABET = string.ascii_lowercase + string.digits
ALIAS_LENGTH = 8
REDIRECT_TARGET = "https://google.com"
HOST_NAME = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}")


def random_alias() -> str:
    """Make the part of the campaign address the tracker requires to be unique."""
    return "".join(secrets.choice(ALIAS_ALPHABET) for _ in range(ALIAS_LENGTH))


def utc_now() -> datetime:
    """Return the current moment; replaced in tests."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class NewCampaignRequest:
    """What the creator form sends; exactly one of `domain_id` and `new_domain_name` is set."""

    name: str
    country: str
    offer_id: int
    group_id: int
    traffic_source_id: int
    domain_id: int | None = None
    new_domain_name: str | None = None


@dataclass(frozen=True, slots=True)
class _Plan:
    """A request that passed every check: nothing here can be refused for its form."""

    name: str
    country: str
    offer: tracker.Offer
    group_id: int
    traffic_source_id: int
    domain: tracker.Domain | None
    new_host: str


@dataclass(slots=True)
class _Progress:
    """How far the writes went; turns a tracker error into an honest message."""

    step: str = "домен"
    created_domain: tracker.Domain | None = None
    campaign_id: int | None = None
    left_behind: int | None = None
    rolled_back: bool | None = None

    def describe(self, error: object) -> str:
        parts = [f"Keitaro не создал {self.step}: {error}."]
        if self.rolled_back:
            parts.append("Кампания удалена.")
        if self.left_behind is not None:
            parts.append(
                f"Кампанию {self.left_behind} удалить не удалось — удалите её в Keitaro вручную."
            )
        if self.created_domain is not None:
            parts.append(f"Домен {self.created_domain.name} создан и остался в трекере.")
        return " ".join(parts)


def _domain_remark(
    request: NewCampaignRequest, domain: tracker.Domain | None, host: str
) -> dict[str, str]:
    """Say what is wrong with the way the domain was named (R-CR-03, 10, 11)."""
    if (request.domain_id is None) == (request.new_domain_name is None):
        return {"domainId": "Выберите домен или задайте имя нового — что-то одно"}
    if request.domain_id is not None and domain is None:
        return {"domainId": "В Keitaro нет такого домена"}
    if request.new_domain_name is not None and not HOST_NAME.fullmatch(host):
        return {"newDomainName": "Имя хоста без схемы и пути, например tracker.example.com"}
    return {}


@dataclass(slots=True)
class _Run:
    """One delivery of a creation task: the task as it is stored now and how far it went."""

    task: Task
    progress: _Progress = field(default_factory=_Progress)


def _nothing() -> None:
    return None


class CreatorService:
    """Assemble a campaign with its two streams as a task and remember it (R-CR-01…15)."""

    def __init__(  # noqa: PLR0913 — collaborators are passed explicitly, there is no container
        self,
        keitaro: KeitaroGateway,
        catalog: CatalogService,
        storage: Storage,
        *,
        name_prefix: str,
        clock: Callable[[], datetime] = utc_now,
        new_alias: Callable[[], str] = random_alias,
        max_attempts: int = 3,
        announce: Callable[[], None] = _nothing,
    ) -> None:
        self._keitaro = keitaro
        self._catalog = catalog
        self._storage = storage
        self._name_prefix = name_prefix
        self._clock = clock
        self._new_alias = new_alias
        self._max_attempts = max_attempts
        self._announce = announce

    async def request(self, request: NewCampaignRequest, task_id: UUID) -> Task:
        """Check the form and queue the creation; nothing is written to the tracker (R-CR-13)."""
        raise NotImplementedError

    async def handle(self, message: Message) -> None:
        """Carry out a queued creation; a repeat goes on from what is done (R-CR-14).

        Raising asks the bus to deliver the message again later (R-CR-15).
        """
        raise NotImplementedError

    async def bury(self, message: Message) -> None:
        """Close the task of a message nobody managed to handle (R-CR-15)."""
        raise NotImplementedError

    async def _check(self, request: NewCampaignRequest) -> _Plan:
        """Collect every remark at once, so the form is fixed in one pass (R-CR-01…03, 11)."""
        offer, groups, sources, domains = await asyncio.gather(
            self._catalog.get_offer(request.offer_id),
            self._keitaro.list_groups(),
            self._keitaro.list_traffic_sources(),
            self._keitaro.list_domains(),
        )
        name = request.name.strip()
        country = find_country(request.country)
        host = (request.new_domain_name or "").strip().lower()
        domain = next((item for item in domains if item.id == request.domain_id), None)
        if request.new_domain_name is not None:
            domain = next((item for item in domains if item.name.lower() == host), None)

        errors: dict[str, str] = {}
        if not (name.startswith(self._name_prefix) and len(name) > len(self._name_prefix)):
            errors["name"] = f"Название начинается с «{self._name_prefix}» и продолжается"
        if country is None:
            errors["country"] = "Нет страны с таким кодом ISO 3166-1 alpha-2"
        if offer is None:
            errors["offerId"] = "В Keitaro нет активного оффера с таким ID"
        if all(group.id != request.group_id for group in groups):
            errors["groupId"] = "В Keitaro нет такой группы"
        if all(source.id != request.traffic_source_id for source in sources):
            errors["trafficSourceId"] = "В Keitaro нет такого источника"
        errors.update(_domain_remark(request, domain, host))
        if errors or country is None or offer is None:
            raise ValidationError(errors)
        return _Plan(
            name=name,
            country=country.code,
            offer=offer,
            group_id=request.group_id,
            traffic_source_id=request.traffic_source_id,
            domain=domain,
            new_host=host,
        )
