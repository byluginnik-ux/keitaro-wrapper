import asyncio
import hashlib
import json
import re
import secrets
import string
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.keitaro import models as tracker
from app.keitaro.gateway import KeitaroGateway
from app.messaging.ports import Message
from app.services.catalog import CatalogService
from app.services.countries import find_country
from app.services.errors import KeitaroError, TaskKeyReusedError, ValidationError
from app.services.models import (
    AuditEntry,
    Campaign,
    OfferLink,
    OutboxMessage,
    Payload,
    Published,
    Refusal,
    Stream,
    Task,
    TaskKind,
    TaskStatus,
    TaskStep,
    campaign_uuid,
    stream_uuid,
)
from app.storage.errors import DuplicateError, StorageConflictError
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


class _SupersededError(Exception):
    """Another delivery of the same message has moved the task on; this one steps aside."""


def _nothing() -> None:
    return None


def _fingerprint(request: NewCampaignRequest) -> str:
    """Tell whether two requests with one task ID are the same request (R-TK-04)."""
    described = {"kind": TaskKind.CREATE_CAMPAIGN.value, **asdict(request)}
    return hashlib.sha256(json.dumps(described, sort_keys=True).encode()).hexdigest()


def _same(known: Task, fingerprint: str) -> Task:
    if known.fingerprint != fingerprint:
        raise TaskKeyReusedError
    return known


def _described(request: NewCampaignRequest, plan: _Plan, alias: str) -> Payload:
    """Put the checked request into the task, so the worker needs nothing else (R-CR-13)."""
    domain = {"id": plan.domain.id, "name": plan.domain.name} if plan.domain else None
    return {
        # kept as it was sent, so a rejected creation can be queued again (R-TK-09)
        "request": asdict(request),
        "plan": {
            "name": plan.name,
            "country": plan.country,
            "offer": {"id": plan.offer.id, "name": plan.offer.name},
            "group_id": plan.group_id,
            "traffic_source_id": plan.traffic_source_id,
            "domain": domain,
            "new_host": plan.new_host,
        },
        "alias": alias,
        "progress": {},
    }


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

    async def request(
        self, request: NewCampaignRequest, task_id: UUID, *, retry_of: UUID | None = None
    ) -> Task:
        """Check the form and queue the creation; nothing is written to the tracker (R-CR-13)."""
        fingerprint = _fingerprint(request)
        known = await self._storage.tasks.get(task_id)
        if known is not None:
            return _same(known, fingerprint)
        plan = await self._check(request)
        now = self._clock()
        task = Task(
            id=task_id,
            kind=TaskKind.CREATE_CAMPAIGN,
            created_at=now,
            fingerprint=fingerprint,
            payload=_described(request, plan, self._new_alias()),
            steps=(TaskStep("queued", now),),
            retry_of=retry_of,
        )
        try:
            async with self._storage.transaction() as work:
                await work.tasks.add(task)
                await work.outbox.put(
                    OutboxMessage(uuid4(), CREATE_REQUESTED, now, {"task_id": str(task.id)})
                )
        except DuplicateError:
            raced = await self._storage.tasks.get(task_id)
            if raced is None:
                raise
            return _same(raced, fingerprint)
        self._announce()
        return task

    async def handle(self, message: Message) -> None:
        """Carry out a queued creation; a repeat goes on from what is done (R-CR-14).

        Raising asks the bus to deliver the message again later (R-CR-15).
        """
        task = await self._storage.tasks.get(UUID(message.payload["task_id"]))
        if task is None or task.status.final:
            return
        now = self._clock()
        running = replace(
            task,
            status=TaskStatus.RUNNING,
            attempts=task.attempts + 1,
            started_at=task.started_at or now,
            steps=(*task.steps, TaskStep("attempt", now, str(task.attempts + 1))),
        )
        try:
            await self._storage.tasks.save(running, was=task.status)
        except StorageConflictError:
            return  # finished by another delivery in between
        run = _Run(running)
        try:
            created, first, second = await self._assemble(run)
        except _SupersededError:
            return
        except KeitaroError as error:
            transient = error.status is None or error.status >= SERVER_ERROR
            if transient and message.attempt < self._max_attempts:
                raise
            unsure = error.status is None or running.attempts > 1
            await self._reject(run, error, status=error.status, look_up=unsure)
            return
        await self._succeed(run, created, first, second)

    async def bury(self, message: Message) -> None:
        """Close the task of a message nobody managed to handle (R-CR-15)."""
        task = await self._storage.tasks.get(UUID(message.payload["task_id"]))
        if task is None or task.status.final:
            return
        done = task.payload["progress"]
        run = _Run(task)
        run.progress.step = "поток" if "campaign" in done else "кампанию"
        run.progress.campaign_id = done["campaign"]["id"] if "campaign" in done else None
        domain = done.get("domain")
        if domain and domain.get("created"):
            run.progress.created_domain = tracker.Domain(id=domain["id"], name=domain["name"])
        await self._reject(run, "попытки исчерпаны", status=None, look_up=True)

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

    async def _assemble(self, run: _Run) -> tuple[tracker.Campaign, tracker.Stream, tracker.Stream]:
        """Do the steps that are not done yet, marking each one in the task (R-CR-14)."""
        plan = run.task.payload["plan"]
        again = run.task.attempts > 1
        domain = await self._domain(run, again=again)
        created = await self._campaign(run, domain["id"], again=again)
        run.progress.step = "поток"
        existing = (
            {item.position: item for item in await self._keitaro.list_campaign_streams(created.id)}
            if again
            else {}
        )
        first = existing.get(1) or await self._keitaro.create_stream(
            tracker.NewStream(
                campaign_id=created.id,
                name="Flow 1",
                position=1,
                kind="redirect",
                action_payload=REDIRECT_TARGET,
                filters=(
                    tracker.StreamFilter(name="country", mode="accept", payload=(plan["country"],)),
                ),
            )
        )
        second = existing.get(2) or await self._keitaro.create_stream(
            tracker.NewStream(
                campaign_id=created.id,
                name="Flow 2",
                position=2,
                kind="landings",
                offers=(tracker.StreamOffer(offer_id=plan["offer"]["id"], share=100),),
            )
        )
        return created, first, second

    async def _domain(self, run: _Run, *, again: bool) -> Payload:
        """Take the chosen domain or create the new one once (R-CR-10…12)."""
        plan = run.task.payload["plan"]
        domain: Payload | None = run.task.payload["progress"].get("domain") or plan["domain"]
        if domain is None:
            run.progress.step = "домен"
            host = plan["new_host"]
            listed = await self._keitaro.list_domains() if again else []
            # found on a repeat: the tracker created it and the answer was lost
            found = next((item for item in listed if item.name.lower() == host), None)
            made = found or await self._keitaro.create_domain(host)
            domain = {"id": made.id, "name": made.name, "created": True}
            await self._mark(run, "domain", domain)
        if domain.get("created"):
            run.progress.created_domain = tracker.Domain(id=domain["id"], name=domain["name"])
        return domain

    async def _campaign(self, run: _Run, domain_id: int, *, again: bool) -> tracker.Campaign:
        """Create the campaign once; a repeat finds it by its alias (R-CR-04, R-CR-14)."""
        plan = run.task.payload["plan"]
        run.progress.step = "кампанию"
        marked = run.task.payload["progress"].get("campaign")
        if marked is None:
            alias = run.task.payload["alias"]
            found = await self._keitaro.find_campaign_by_alias(alias) if again else None
            made = found or await self._keitaro.create_campaign(
                tracker.NewCampaign(
                    name=plan["name"],
                    alias=alias,
                    domain_id=domain_id,
                    group_id=plan["group_id"],
                    traffic_source_id=plan["traffic_source_id"],
                )
            )
            marked = made.model_dump()
            run.progress.campaign_id = made.id
            await self._mark(run, "campaign", marked)
        created = tracker.Campaign.model_validate(marked)
        run.progress.campaign_id = created.id
        return created

    async def _mark(self, run: _Run, step: str, value: Payload) -> None:
        """Write down a finished step, so a repeat does not do it again."""
        task = run.task
        payload = {**task.payload, "progress": {**task.payload["progress"], step: value}}
        marked = replace(task, payload=payload, steps=(*task.steps, TaskStep(step, self._clock())))
        try:
            await self._storage.tasks.save(marked, was=TaskStatus.RUNNING)
        except StorageConflictError as error:
            raise _SupersededError from error
        run.task = marked

    async def _succeed(
        self, run: _Run, created: tracker.Campaign, first: tracker.Stream, second: tracker.Stream
    ) -> None:
        """Store the campaign and the outcome of the task together (R-CR-08, 09, 15)."""
        task = run.task
        plan = task.payload["plan"]
        now = self._clock()
        campaign = Campaign(
            id=campaign_uuid(created.id),
            keitaro_id=created.id,
            name=created.name,
            alias=created.alias,
            created_at=now,
            country=plan["country"],
            domain_id=created.domain_id,
            group_id=created.group_id,
            traffic_source_id=created.traffic_source_id,
        )
        offer = OfferLink(plan["offer"]["id"], plan["offer"]["name"], 100, published=Published(100))
        streams = [
            Stream(
                stream_uuid(first.id),
                campaign.id,
                first.id,
                first.name,
                first.position,
                first.kind,
            ),
            Stream(
                stream_uuid(second.id),
                campaign.id,
                second.id,
                second.name,
                second.position,
                second.kind,
                (offer,),
            ),
        ]
        done = replace(
            task,
            status=TaskStatus.SUCCEEDED,
            finished_at=now,
            campaign_id=campaign.id,
            steps=(*task.steps, TaskStep("created", now)),
        )
        try:
            async with self._storage.transaction() as work:
                await work.tasks.save(done, was=task.status)
                await work.campaigns.add(campaign)
                await work.streams.save_all(streams)
                await work.audit.record(
                    AuditEntry(
                        id=uuid4(),
                        action="campaign.created",
                        created_at=now,
                        campaign_id=campaign.id,
                        details={
                            "keitaro_id": campaign.keitaro_id,
                            "name": campaign.name,
                            "country": campaign.country,
                            "offer_id": plan["offer"]["id"],
                            "domain_id": campaign.domain_id,
                            "domain_created": run.progress.created_domain is not None,
                        },
                    )
                )
                await work.outbox.put(
                    OutboxMessage(
                        uuid4(),
                        CREATED,
                        now,
                        {"task_id": str(task.id), "campaign_id": str(campaign.id)},
                    )
                )
        except StorageConflictError:
            return  # another delivery of the same message has already written the outcome
        self._announce()

    async def _reject(self, run: _Run, error: object, *, status: int | None, look_up: bool) -> None:
        """Undo what can be undone and close the task with the reason (R-CR-07, 12, 15)."""
        task, progress = run.task, run.progress
        if progress.campaign_id is None and look_up:
            progress.campaign_id = await self._lost_campaign(task.payload["alias"])
        if progress.campaign_id is not None:
            progress.rolled_back = await self._remove(progress.campaign_id)
            progress.left_behind = None if progress.rolled_back else progress.campaign_id
        message = progress.describe(error)
        now = self._clock()
        details: Payload = {"status": status}
        if progress.created_domain is not None:
            details["created_domain"] = {
                "id": progress.created_domain.id,
                "name": progress.created_domain.name,
            }
        done = replace(
            task,
            status=TaskStatus.REJECTED,
            finished_at=now,
            refusal=Refusal("campaign_creation_failed", message, details=details),
            steps=(*task.steps, TaskStep("rejected", now)),
        )
        try:
            async with self._storage.transaction() as work:
                await work.tasks.save(done, was=task.status)
                await work.audit.record(
                    AuditEntry(
                        id=uuid4(),
                        action="campaign.create_failed",
                        created_at=now,
                        details={
                            "name": task.payload["plan"]["name"],
                            "error": message,
                            "rolled_back": progress.rolled_back,
                            "keitaro_id": progress.left_behind,
                            "domain_created": progress.created_domain is not None,
                        },
                    )
                )
                await work.outbox.put(
                    OutboxMessage(uuid4(), CREATE_REJECTED, now, {"task_id": str(task.id)})
                )
        except StorageConflictError:
            return
        self._announce()

    async def _lost_campaign(self, alias: str) -> int | None:
        """Find a campaign the tracker may have created without telling us."""
        try:
            found = await self._keitaro.find_campaign_by_alias(alias)
        except KeitaroError:
            return None
        return found.id if found else None

    async def _remove(self, keitaro_id: int) -> bool:
        try:
            await self._keitaro.delete_campaign(keitaro_id)
        except KeitaroError:
            return False
        return True
