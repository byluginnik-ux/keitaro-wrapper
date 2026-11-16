import asyncio
import re
import secrets
import string
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.keitaro import models as tracker
from app.keitaro.gateway import KeitaroGateway
from app.services.catalog import CatalogService
from app.services.countries import find_country
from app.services.errors import CampaignCreationError, KeitaroError, ValidationError
from app.services.models import AuditEntry, Campaign, Details, OfferLink, Published, Stream
from app.storage.ports import Storage

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
    left_behind: int | None = None
    rolled_back: bool | None = None

    def describe(self, error: KeitaroError) -> str:
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


class CreatorService:
    """Assemble a campaign with its two streams in the tracker and remember it (R-CR-01…12)."""

    def __init__(  # noqa: PLR0913 — collaborators are passed explicitly, there is no container
        self,
        keitaro: KeitaroGateway,
        catalog: CatalogService,
        storage: Storage,
        *,
        name_prefix: str,
        clock: Callable[[], datetime] = utc_now,
        new_alias: Callable[[], str] = random_alias,
    ) -> None:
        self._keitaro = keitaro
        self._catalog = catalog
        self._storage = storage
        self._name_prefix = name_prefix
        self._clock = clock
        self._new_alias = new_alias

    async def create(self, request: NewCampaignRequest) -> Campaign:
        """Create the campaign or leave the tracker as it was (R-CR-07)."""
        plan = await self._check(request)
        progress = _Progress()
        try:
            campaign = await self._assemble(plan, progress)
        except KeitaroError as error:
            failure = CampaignCreationError(
                progress.describe(error), error.status, progress.created_domain
            )
            await self._record(
                "campaign.create_failed",
                None,
                {
                    "name": plan.name,
                    "error": str(failure),
                    "rolled_back": progress.rolled_back,
                    "keitaro_id": progress.left_behind,
                    "domain_created": progress.created_domain is not None,
                },
            )
            raise failure from error
        await self._record(
            "campaign.created",
            campaign,
            {
                "keitaro_id": campaign.keitaro_id,
                "name": campaign.name,
                "country": campaign.country,
                "offer_id": plan.offer.id,
                "domain_id": campaign.domain_id,
                "domain_created": progress.created_domain is not None,
            },
        )
        return campaign

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

    async def _assemble(self, plan: _Plan, progress: _Progress) -> Campaign:
        domain = plan.domain
        if domain is None:
            domain = progress.created_domain = await self._keitaro.create_domain(plan.new_host)
        progress.step = "кампанию"
        created = await self._keitaro.create_campaign(
            tracker.NewCampaign(
                name=plan.name,
                alias=self._new_alias(),
                domain_id=domain.id,
                group_id=plan.group_id,
                traffic_source_id=plan.traffic_source_id,
            )
        )
        progress.step = "поток"
        try:
            return await self._add_streams(plan, created)
        except Exception:
            progress.rolled_back = await self._remove(created.id)
            progress.left_behind = None if progress.rolled_back else created.id
            raise

    async def _add_streams(self, plan: _Plan, created: tracker.Campaign) -> Campaign:
        """Create both streams, then store everything (R-CR-05, 06, 08)."""
        country_filter = tracker.StreamFilter(
            name="country", mode="accept", payload=(plan.country,)
        )
        first = await self._keitaro.create_stream(
            tracker.NewStream(
                campaign_id=created.id,
                name="Flow 1",
                position=1,
                kind="redirect",
                action_payload=REDIRECT_TARGET,
                filters=(country_filter,),
            )
        )
        second = await self._keitaro.create_stream(
            tracker.NewStream(
                campaign_id=created.id,
                name="Flow 2",
                position=2,
                kind="landings",
                offers=(tracker.StreamOffer(offer_id=plan.offer.id, share=100),),
            )
        )
        campaign = Campaign(
            id=uuid4(),
            keitaro_id=created.id,
            name=created.name,
            alias=created.alias,
            created_at=self._clock(),
            country=plan.country,
            domain_id=created.domain_id,
            group_id=created.group_id,
            traffic_source_id=created.traffic_source_id,
        )
        offer = OfferLink(plan.offer.id, plan.offer.name, 100, published=Published(100))
        await self._storage.campaigns.add(campaign)
        await self._storage.streams.save_all(
            [
                Stream(uuid4(), campaign.id, first.id, first.name, first.position, first.kind),
                Stream(
                    uuid4(),
                    campaign.id,
                    second.id,
                    second.name,
                    second.position,
                    second.kind,
                    (offer,),
                ),
            ]
        )
        return campaign

    async def _remove(self, keitaro_id: int) -> bool:
        try:
            await self._keitaro.delete_campaign(keitaro_id)
        except KeitaroError:
            return False
        return True

    async def _record(self, action: str, campaign: Campaign | None, details: Details) -> None:
        """Write one line of the journal (R-CR-09)."""
        await self._storage.audit.record(
            AuditEntry(
                id=uuid4(),
                action=action,
                created_at=self._clock(),
                campaign_id=campaign.id if campaign else None,
                details=details,
            )
        )
