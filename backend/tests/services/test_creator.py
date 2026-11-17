"""Creation of a campaign as a task (R-CR-01…15)."""

from dataclasses import replace
from uuid import uuid4

import pytest

from app.keitaro.models import NewStream, Stream, StreamFilter, StreamOffer
from app.messaging.ports import Message
from app.services.catalog import CatalogService
from app.services.creator import (
    CREATE_REJECTED,
    CREATE_REQUESTED,
    CREATED,
    CreatorService,
    NewCampaignRequest,
)
from app.services.errors import KeitaroError, TaskKeyReusedError, ValidationError
from app.services.models import Campaign, OfferLink, Published, Task, TaskStatus
from app.storage.memory import create_memory_storage
from app.storage.ports import Storage
from tests.fakes import A, FakeKeitaro
from tests.graphql.support import NOW, PREFIX

pytestmark = pytest.mark.anyio

REQUEST = NewCampaignRequest(
    name="test_bulygin_au_flexacil",
    country="au",
    offer_id=A,
    group_id=10332,
    traffic_source_id=836,
    domain_id=1813,
)
NEW_DOMAIN = replace(REQUEST, domain_id=None, new_domain_name="new.example.com")
WRITES = ("create_domain", "create_campaign", "create_stream")
MAX_ATTEMPTS = 3


@pytest.fixture
def keitaro() -> FakeKeitaro:
    return FakeKeitaro()


@pytest.fixture
def storage() -> Storage:
    return create_memory_storage()


def service(keitaro: FakeKeitaro, storage: Storage) -> CreatorService:
    return CreatorService(
        keitaro,
        CatalogService(keitaro),
        storage,
        name_prefix=PREFIX,
        clock=lambda: NOW,
        new_alias=lambda: "alias001",
        max_attempts=MAX_ATTEMPTS,
    )


@pytest.fixture
def creator(keitaro: FakeKeitaro, storage: Storage) -> CreatorService:
    return service(keitaro, storage)


def delivery(task: Task, attempt: int = 1) -> Message:
    return Message(uuid4(), CREATE_REQUESTED, {"task_id": str(task.id)}, attempt)


async def stored(storage: Storage, task: Task) -> Task:
    found = await storage.tasks.get(task.id)
    assert found is not None
    return found


async def run(
    creator: CreatorService, storage: Storage, request: NewCampaignRequest, attempt: int = 1
) -> Task:
    """Queue the creation and let the worker take it once."""
    task = await creator.request(request, uuid4())
    await creator.handle(delivery(task, attempt))
    return await stored(storage, task)


async def create(
    creator: CreatorService, storage: Storage, request: NewCampaignRequest
) -> Campaign:
    task = await run(creator, storage, request)
    assert task.status is TaskStatus.SUCCEEDED
    assert task.campaign_id is not None
    campaign = await storage.campaigns.get(task.campaign_id)
    assert campaign is not None
    return campaign


async def fail(tracker: FakeKeitaro, storage: Storage, request: NewCampaignRequest) -> Task:
    """Run the creation on its last attempt against a tracker that fails."""
    task = await run(service(tracker, storage), storage, request, attempt=MAX_ATTEMPTS)
    assert task.status is TaskStatus.REJECTED
    assert task.refusal is not None
    return task


def reason(task: Task) -> str:
    assert task.refusal is not None
    return task.refusal.message


async def rejected(creator: CreatorService, request: NewCampaignRequest) -> dict[str, str]:
    with pytest.raises(ValidationError) as caught:
        await creator.request(request, uuid4())
    return caught.value.fields


def wrote_nothing(keitaro: FakeKeitaro) -> bool:
    return not any(keitaro.calls[method] for method in WRITES)


async def topics(storage: Storage) -> list[str]:
    waiting = await storage.outbox.claim(limit=50, now=NOW, lease=NOW - NOW)
    return [message.topic for message in waiting]


async def test_request_only_queues_the_task(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-CR-13: the tracker is written by the worker, not by the request."""
    task = await creator.request(NEW_DOMAIN, uuid4())

    assert (task.status, task.attempts, task.campaign_id) == (TaskStatus.PENDING, 0, None)
    assert task.payload["alias"] == "alias001"
    assert task.payload["plan"]["country"] == "AU"
    assert await stored(storage, task) == task
    assert wrote_nothing(keitaro)
    assert await storage.campaigns.list_recent() == []
    assert await topics(storage) == [CREATE_REQUESTED]


async def test_refused_form_queues_nothing(creator: CreatorService, storage: Storage) -> None:
    """R-CR-13."""
    task_id = uuid4()

    with pytest.raises(ValidationError):
        await creator.request(replace(REQUEST, country="zz"), task_id)

    assert await storage.tasks.get(task_id) is None
    assert await topics(storage) == []


async def test_same_task_id_answers_with_the_same_task(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-TK-04."""
    task_id = uuid4()

    first = await creator.request(REQUEST, task_id)
    again = await creator.request(REQUEST, task_id)
    await creator.handle(delivery(first))
    after_the_end = await creator.request(REQUEST, task_id)
    with pytest.raises(TaskKeyReusedError):
        await creator.request(NEW_DOMAIN, task_id)

    assert again == first
    assert after_the_end.status is TaskStatus.SUCCEEDED
    assert len(keitaro.campaigns) == 1
    assert await topics(storage) == [CREATE_REQUESTED, CREATED]


@pytest.mark.parametrize("name", ["au_flexacil", "test_bulygin_", "  test_bulygin_  ", ""])
async def test_name_must_carry_the_prefix_and_something_after_it(
    creator: CreatorService, keitaro: FakeKeitaro, name: str
) -> None:
    """R-CR-01."""
    fields = await rejected(creator, replace(REQUEST, name=name))

    assert list(fields) == ["name"]
    assert wrote_nothing(keitaro)


async def test_unknown_country_is_rejected(creator: CreatorService, keitaro: FakeKeitaro) -> None:
    """R-CR-02."""
    fields = await rejected(creator, replace(REQUEST, country="zz"))

    assert list(fields) == ["country"]
    assert wrote_nothing(keitaro)


async def test_missing_references_are_reported_together(
    creator: CreatorService, keitaro: FakeKeitaro
) -> None:
    """R-CR-03: every wrong field is named in one answer."""
    request = replace(REQUEST, offer_id=1, group_id=2, traffic_source_id=3, domain_id=4)

    fields = await rejected(creator, request)

    assert set(fields) == {"offerId", "groupId", "trafficSourceId", "domainId"}
    assert wrote_nothing(keitaro)


@pytest.mark.parametrize(
    "request_",
    [replace(REQUEST, domain_id=None), replace(REQUEST, new_domain_name="new.example.com")],
    ids=["neither", "both"],
)
async def test_exactly_one_way_to_name_the_domain(
    creator: CreatorService, request_: NewCampaignRequest
) -> None:
    """R-CR-03, R-CR-10."""
    assert list(await rejected(creator, request_)) == ["domainId"]


async def test_campaign_gets_the_chosen_domain_group_and_source(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-CR-04."""
    created = await create(creator, storage, REQUEST)

    in_tracker = keitaro.campaigns[created.keitaro_id]
    assert in_tracker.name == "test_bulygin_au_flexacil"
    assert in_tracker.alias == "alias001"
    assert (in_tracker.domain_id, in_tracker.group_id, in_tracker.traffic_source_id) == (
        1813,
        10332,
        836,
    )


async def test_first_stream_sends_the_country_to_google(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-CR-05, R-CR-02: the code travels in upper case."""
    created = await create(creator, storage, REQUEST)

    assert keitaro.stream_requests[0] == NewStream(
        campaign_id=created.keitaro_id,
        name="Flow 1",
        position=1,
        kind="redirect",
        action_type="http",
        action_payload="https://google.com",
        filters=(StreamFilter(name="country", mode="accept", payload=("AU",)),),
    )


async def test_second_stream_sends_everyone_else_to_the_offer(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-CR-06."""
    created = await create(creator, storage, REQUEST)

    assert keitaro.stream_requests[1] == NewStream(
        campaign_id=created.keitaro_id,
        name="Flow 2",
        position=2,
        kind="landings",
        offers=(StreamOffer(offer_id=A, share=100),),
    )
    assert len(keitaro.stream_requests) == 2


class SecondStreamFails(FakeKeitaro):
    async def create_stream(self, stream: NewStream) -> Stream:
        if stream.position == 2:
            self.fail_on.add("create_stream")
        return await super().create_stream(stream)


@pytest.mark.parametrize("tracker", [FakeKeitaro(fail_on={"create_stream"}), SecondStreamFails()])
async def test_failed_stream_removes_the_campaign(tracker: FakeKeitaro, storage: Storage) -> None:
    """R-CR-07: no half-built campaign stays in the tracker or in our storage."""
    task = await fail(tracker, storage, REQUEST)

    assert "Кампания удалена" in reason(task)
    assert tracker.calls["delete_campaign"] == 1
    assert tracker.campaigns == {}
    assert tracker.streams == {}
    assert await storage.campaigns.list_recent() == []
    assert await topics(storage) == [CREATE_REQUESTED, CREATE_REJECTED]


async def test_failed_cleanup_names_the_campaign_left_behind(storage: Storage) -> None:
    """R-CR-07: when even the removal fails, the user is told what to remove by hand."""
    tracker = FakeKeitaro(fail_on={"create_stream", "delete_campaign"})

    task = await fail(tracker, storage, REQUEST)

    (left_behind,) = tracker.campaigns
    assert str(left_behind) in reason(task)


async def test_created_campaign_and_streams_are_stored(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-CR-08."""
    created = await create(creator, storage, REQUEST)

    assert (created.name, created.alias, created.country) == (REQUEST.name, "alias001", "AU")
    assert (created.domain_id, created.group_id, created.traffic_source_id) == (1813, 10332, 836)
    assert created.created_at == NOW
    first, second = await storage.streams.list_by_campaign(created.id)
    tracker_first, tracker_second = await keitaro.list_campaign_streams(created.keitaro_id)
    assert (first.keitaro_id, first.name, first.kind, first.offers) == (
        tracker_first.id,
        "Flow 1",
        "redirect",
        (),
    )
    assert (second.keitaro_id, second.name, second.kind) == (
        tracker_second.id,
        "Flow 2",
        "landings",
    )
    assert second.offers == (OfferLink(A, "Offer A", 100, published=Published(100)),)
    assert second.dirty is False


async def test_finished_task_tells_its_steps(creator: CreatorService, storage: Storage) -> None:
    """R-CR-14, R-TK-05."""
    task = await run(creator, storage, NEW_DOMAIN)

    assert (task.status, task.attempts, task.finished_at) == (TaskStatus.SUCCEEDED, 1, NOW)
    assert [step.name for step in task.steps] == [
        "queued",
        "attempt",
        "domain",
        "campaign",
        "created",
    ]


async def test_success_is_written_to_the_journal(creator: CreatorService, storage: Storage) -> None:
    """R-CR-09."""
    created = await create(creator, storage, REQUEST)

    (entry,) = await storage.audit.list_recent()
    assert (entry.action, entry.campaign_id, entry.created_at) == (
        "campaign.created",
        created.id,
        NOW,
    )
    assert entry.details["keitaro_id"] == created.keitaro_id
    assert entry.details["domain_created"] is False


async def test_failure_is_written_to_the_journal(storage: Storage) -> None:
    """R-CR-09."""
    await fail(FakeKeitaro(fail_on={"create_stream"}), storage, REQUEST)

    (entry,) = await storage.audit.list_recent()
    assert entry.action == "campaign.create_failed"
    assert entry.details["name"] == REQUEST.name
    assert entry.details["rolled_back"] is True


async def test_new_domain_is_created_before_the_campaign(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-CR-10."""
    created = await create(creator, storage, NEW_DOMAIN)

    new_domain = keitaro.domains[-1]
    assert new_domain.name == "new.example.com"
    assert keitaro.campaigns[created.keitaro_id].domain_id == new_domain.id
    assert created.domain_id == new_domain.id
    (entry,) = await storage.audit.list_recent()
    assert entry.details["domain_created"] is True


@pytest.mark.parametrize(
    "name",
    ["https://new.example.com", "new.example.com/path", "new example.com", "localhost", "-a.com"],
)
async def test_new_domain_must_be_a_bare_host_name(
    creator: CreatorService, keitaro: FakeKeitaro, name: str
) -> None:
    """R-CR-11."""
    fields = await rejected(creator, replace(NEW_DOMAIN, new_domain_name=name))

    assert list(fields) == ["newDomainName"]
    assert wrote_nothing(keitaro)


async def test_existing_domain_name_is_reused_in_any_case(
    creator: CreatorService, keitaro: FakeKeitaro, storage: Storage
) -> None:
    """R-CR-11."""
    request = replace(NEW_DOMAIN, new_domain_name=" Tracker.Example.COM ")

    created = await create(creator, storage, request)

    assert keitaro.calls["create_domain"] == 0
    assert created.domain_id == 1813


async def test_failed_domain_stops_before_the_campaign(storage: Storage) -> None:
    """R-CR-12."""
    tracker = FakeKeitaro(fail_on={"create_domain"}, fail_status=400)

    task = await fail(tracker, storage, NEW_DOMAIN)

    assert tracker.calls["create_campaign"] == 0
    assert tracker.calls["delete_campaign"] == 0
    assert reason(task).startswith("Keitaro не создал домен")
    assert task.refusal is not None
    assert "created_domain" not in task.refusal.details


async def test_created_domain_survives_a_failed_campaign(storage: Storage) -> None:
    """R-CR-12: the domain stays and the reason says so."""
    tracker = FakeKeitaro(fail_on={"create_campaign"}, fail_status=400)

    task = await fail(tracker, storage, NEW_DOMAIN)

    assert task.refusal is not None
    assert task.refusal.details["created_domain"] == {
        "id": tracker.domains[-1].id,
        "name": "new.example.com",
    }
    assert "new.example.com" in reason(task)


async def test_reused_domain_is_not_reported_as_created(storage: Storage) -> None:
    """R-CR-12 speaks only about a domain this operation created."""
    task = await fail(FakeKeitaro(fail_on={"create_campaign"}, fail_status=400), storage, REQUEST)

    assert task.refusal is not None
    assert "created_domain" not in task.refusal.details


async def test_refusal_of_the_tracker_is_final_at_the_first_attempt(storage: Storage) -> None:
    """R-CR-15: a 4xx is not worth another delivery."""
    tracker = FakeKeitaro(fail_on={"create_stream"}, fail_status=422)

    task = await run(service(tracker, storage), storage, REQUEST)

    assert (task.status, task.attempts) == (TaskStatus.REJECTED, 1)
    assert tracker.campaigns == {}
    assert tracker.calls["find_campaign_by_alias"] == 0


@pytest.mark.parametrize("status", [500, None])
async def test_passing_failure_goes_on_from_what_is_done(
    keitaro: FakeKeitaro, creator: CreatorService, storage: Storage, status: int | None
) -> None:
    """R-CR-14, R-CR-15: the second delivery creates only what is missing."""
    task = await creator.request(NEW_DOMAIN, uuid4())
    keitaro.fail_on.add("create_stream")
    keitaro.fail_status = status

    with pytest.raises(KeitaroError):
        await creator.handle(delivery(task, attempt=1))
    waiting = await stored(storage, task)
    keitaro.fail_on.clear()
    await creator.handle(delivery(task, attempt=2))

    done = await stored(storage, task)
    assert (waiting.status, waiting.attempts) == (TaskStatus.RUNNING, 1)
    assert set(waiting.payload["progress"]) == {"domain", "campaign"}
    assert (done.status, done.attempts) == (TaskStatus.SUCCEEDED, 2)
    assert (keitaro.calls["create_domain"], keitaro.calls["create_campaign"]) == (1, 1)
    assert [stream.position for stream in keitaro.streams.values()] == [1, 2]
    assert len(await storage.campaigns.list_recent()) == 1


@pytest.mark.parametrize("lost", WRITES)
async def test_lost_answer_does_not_make_a_duplicate(
    keitaro: FakeKeitaro, creator: CreatorService, storage: Storage, lost: str
) -> None:
    """R-CR-14: the tracker did the step, the answer never came, the message came again."""
    task = await creator.request(NEW_DOMAIN, uuid4())
    keitaro.lose_answer.add(lost)

    with pytest.raises(KeitaroError):
        await creator.handle(delivery(task, attempt=1))
    keitaro.lose_answer.clear()
    await creator.handle(delivery(task, attempt=2))

    done = await stored(storage, task)
    assert done.status is TaskStatus.SUCCEEDED
    assert [domain.name for domain in keitaro.domains] == ["tracker.example.com", "new.example.com"]
    assert len(keitaro.campaigns) == 1
    assert [stream.position for stream in keitaro.streams.values()] == [1, 2]
    (entry,) = await storage.audit.list_recent()
    assert entry.details["domain_created"] is True


async def test_last_attempt_removes_a_campaign_whose_answer_was_lost(storage: Storage) -> None:
    """R-CR-07, R-CR-15: a campaign we never heard about is still found and removed."""
    tracker = FakeKeitaro(lose_answer={"create_campaign"})

    task = await fail(tracker, storage, REQUEST)

    assert tracker.campaigns == {}
    assert "Кампания удалена" in reason(task)


async def test_dead_letter_rejects_the_task_and_cleans_up(
    keitaro: FakeKeitaro, creator: CreatorService, storage: Storage
) -> None:
    """R-CR-15: the task does not hang, the campaign does not stay half-built."""
    task = await creator.request(NEW_DOMAIN, uuid4())
    keitaro.fail_on.add("create_stream")
    with pytest.raises(KeitaroError):
        await creator.handle(delivery(task))

    await creator.bury(delivery(task))
    await creator.bury(delivery(task))

    done = await stored(storage, task)
    assert done.status is TaskStatus.REJECTED
    assert "попытки исчерпаны" in reason(done)
    assert "new.example.com" in reason(done)
    assert keitaro.campaigns == {}
    assert keitaro.calls["delete_campaign"] == 1
    assert await topics(storage) == [CREATE_REQUESTED, CREATE_REJECTED]


async def test_repeated_delivery_of_a_finished_task_does_nothing(
    keitaro: FakeKeitaro, creator: CreatorService, storage: Storage
) -> None:
    """R-EV-07."""
    task = await run(creator, storage, REQUEST)

    await creator.handle(delivery(task, attempt=2))
    await creator.handle(Message(uuid4(), CREATE_REQUESTED, {"task_id": str(uuid4())}))

    assert await stored(storage, task) == task
    assert (keitaro.calls["create_campaign"], keitaro.calls["create_stream"]) == (1, 2)
    assert await topics(storage) == [CREATE_REQUESTED, CREATED]
