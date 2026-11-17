"""Translate what services return into the types of the contract."""

from datetime import datetime
from uuid import UUID

import strawberry
from keitaro_contracts import types as gql

from app.keitaro import models as keitaro
from app.services import countries, models
from app.services.creator import NewCampaignRequest
from app.services.editor import FetchedStreams
from app.services.errors import (
    CampaignCreationError,
    DomainError,
    EmptyStreamError,
    KeitaroError,
    OfferAlreadyInStreamError,
    OfferNotFoundError,
    ShareOverflowError,
    StreamBusyError,
    StreamConflictError,
    StreamNotFoundError,
    TaskKeyReusedError,
    TaskNotCancellableError,
    TaskNotFoundError,
    TaskNotRetryableError,
    ValidationError,
)
from app.services.shares import OfferState
from app.services.tasks import QueueSummary


def to_domain(domain: keitaro.Domain) -> gql.Domain:
    return gql.Domain(id=domain.id, name=domain.name)


def to_group(group: keitaro.Group) -> gql.Group:
    return gql.Group(id=group.id, name=group.name)


def to_traffic_source(source: keitaro.TrafficSource) -> gql.TrafficSource:
    return gql.TrafficSource(id=source.id, name=source.name)


def to_offer(offer: keitaro.Offer) -> gql.Offer:
    return gql.Offer(id=offer.id, name=offer.name)


def to_country(country: countries.Country) -> gql.Country:
    return gql.Country(code=country.code, name=country.name)


def to_campaign(campaign: models.Campaign) -> gql.Campaign:
    return gql.Campaign(
        id=strawberry.ID(str(campaign.id)),
        keitaro_id=campaign.keitaro_id,
        name=campaign.name,
        alias=campaign.alias,
        country=campaign.country,
    )


def to_new_campaign_request(data: gql.CreateCampaignInput) -> NewCampaignRequest:
    return NewCampaignRequest(
        name=data.name,
        country=data.country,
        offer_id=data.offer_id,
        group_id=data.group_id,
        traffic_source_id=data.traffic_source_id,
        domain_id=data.domain_id.value if data.domain_id is not None else None,
        new_domain_name=data.new_domain_name.value if data.new_domain_name is not None else None,
    )


def to_validation_failed(error: ValidationError) -> gql.ValidationFailed:
    remarks = [gql.FieldError(field=name, message=text) for name, text in error.fields.items()]
    return gql.ValidationFailed(message=str(error), fields=remarks)


def to_keitaro_failure(error: KeitaroError) -> gql.KeitaroFailure:
    created = error.created_domain if isinstance(error, CampaignCreationError) else None
    return gql.KeitaroFailure(
        message=str(error), created_domain=to_domain(created) if created else None
    )


def to_offer_state(state: OfferState) -> gql.OfferState:
    return gql.OfferState[state.name]


def to_stream_offer(link: models.OfferLink) -> gql.StreamOffer:
    published = link.published
    return gql.StreamOffer(
        offer_id=link.offer_id,
        name=link.name,
        share=link.share,
        pinned=link.pinned,
        state=to_offer_state(link.state),
        published=gql.PublishedOffer(
            share=published.share, state=to_offer_state(published.state), pinned=published.pinned
        )
        if published
        else None,
        changed=link.changed,
    )


def to_stream(stream: models.Stream) -> gql.Stream:
    return gql.Stream(
        id=strawberry.ID(str(stream.id)),
        keitaro_id=stream.keitaro_id,
        campaign_id=strawberry.ID(str(stream.campaign_id)),
        name=stream.name,
        position=stream.position,
        kind=stream.kind,
        dirty=stream.dirty,
        version=stream.version,
        publishing_task_id=strawberry.ID(str(stream.publishing)) if stream.publishing else None,
        offers=[to_stream_offer(link) for link in stream.offers],
    )


def to_streams_fetched(fetched: FetchedStreams) -> gql.StreamsFetched:
    return gql.StreamsFetched(
        campaign=to_campaign(fetched.campaign),
        streams=[to_stream(stream) for stream in fetched.streams],
    )


def optional[T](value: strawberry.Some[T | None] | None) -> T | None:
    """Read an input field that may be left out: absent and null mean the same here."""
    return value.value if value is not None else None


def to_uuid(value: strawberry.ID) -> UUID | None:
    """Read our identifier; anything else simply matches nothing."""
    try:
        return UUID(str(value))
    except ValueError:
        return None


type StreamRefusal = (
    gql.StreamConflict
    | gql.StreamBusy
    | gql.StreamNotFound
    | gql.OfferNotFound
    | gql.OfferAlreadyInStream
    | gql.ShareOverflow
    | gql.ValidationFailed
    | gql.KeitaroFailure
)


MESSAGE_ONLY = {
    StreamBusyError: gql.StreamBusy,
    StreamNotFoundError: gql.StreamNotFound,
    OfferNotFoundError: gql.OfferNotFound,
    OfferAlreadyInStreamError: gql.OfferAlreadyInStream,
    ShareOverflowError: gql.ShareOverflow,
}


def to_stream_refusal(error: DomainError) -> StreamRefusal:
    """Turn a refusal of the editor into its member of StreamResult; anything else is a bug."""
    if isinstance(error, ValidationError):
        return to_validation_failed(error)
    if isinstance(error, KeitaroError):
        return to_keitaro_failure(error)
    if isinstance(error, StreamConflictError) and error.current is not None:
        return gql.StreamConflict(message=str(error), stream=to_stream(error.current))
    for kind, answer in MESSAGE_ONLY.items():
        if isinstance(error, kind):
            return answer(message=str(error))
    raise error


def _time(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def to_task(task: models.Task) -> gql.Task:
    refusal = task.refusal
    domain = refusal.details.get("created_domain") if refusal else None
    return gql.Task(
        id=strawberry.ID(str(task.id)),
        kind=gql.TaskKind[task.kind.name],
        status=gql.TaskStatus[task.status.name],
        attempts=task.attempts,
        created_at=task.created_at.isoformat(),
        started_at=_time(task.started_at),
        finished_at=_time(task.finished_at),
        campaign_id=strawberry.ID(str(task.campaign_id)) if task.campaign_id else None,
        stream_id=strawberry.ID(str(task.stream_id)) if task.stream_id else None,
        retry_of=strawberry.ID(str(task.retry_of)) if task.retry_of else None,
        refusal=gql.TaskRefusal(
            message=refusal.message,
            created_domain=gql.Domain(id=domain["id"], name=domain["name"]) if domain else None,
        )
        if refusal
        else None,
        steps=[
            gql.TaskStep(name=step.name, at=step.at.isoformat(), note=step.note)
            for step in task.steps
        ],
    )


type PublishRefusal = (
    gql.StreamConflict | gql.StreamBusy | gql.StreamNotFound | gql.EmptyStream | gql.TaskKeyReused
)

NOT_QUEUED = {
    StreamBusyError: gql.StreamBusy,
    StreamNotFoundError: gql.StreamNotFound,
    EmptyStreamError: gql.EmptyStream,
    TaskKeyReusedError: gql.TaskKeyReused,
}


def to_publish_refusal(error: DomainError) -> PublishRefusal:
    """Turn the reason a publication was not queued into its member of PublishStreamResult."""
    if isinstance(error, StreamConflictError) and error.current is not None:
        return gql.StreamConflict(message=str(error), stream=to_stream(error.current))
    for kind, answer in NOT_QUEUED.items():
        if isinstance(error, kind):
            return answer(message=str(error))
    raise error


def to_queue_status(summary: QueueSummary) -> gql.QueueStatus:
    return gql.QueueStatus(
        tasks=[
            gql.TaskCount(status=gql.TaskStatus[status.name], count=summary.tasks[status])
            for status in models.TaskStatus
            if summary.tasks.get(status)
        ],
        outbox_waiting=summary.outbox.waiting,
        outbox_oldest=_time(summary.outbox.oldest),
        queues=[
            gql.QueueState(name=queue.name, ready=queue.ready, consumers=queue.consumers)
            for queue in summary.queues
        ],
    )


type TaskRefusalAnswer = (
    gql.TaskNotFound
    | gql.TaskNotRetryable
    | gql.StreamBusy
    | gql.StreamNotFound
    | gql.EmptyStream
    | gql.TaskKeyReused
)

NOT_STEERED = {
    TaskNotFoundError: gql.TaskNotFound,
    TaskNotRetryableError: gql.TaskNotRetryable,
    StreamBusyError: gql.StreamBusy,
    StreamNotFoundError: gql.StreamNotFound,
    EmptyStreamError: gql.EmptyStream,
    TaskKeyReusedError: gql.TaskKeyReused,
}


def to_task_refusal(error: DomainError) -> TaskRefusalAnswer:
    """Turn the reason a task was not repeated into its member of RetryTaskResult."""
    for kind, answer in NOT_STEERED.items():
        if isinstance(error, kind):
            return answer(message=str(error))
    raise error


def to_cancel_refusal(
    error: TaskNotFoundError | TaskNotCancellableError,
) -> gql.TaskNotFound | gql.TaskNotCancellable:
    if isinstance(error, TaskNotFoundError):
        return gql.TaskNotFound(message=str(error))
    return gql.TaskNotCancellable(message=str(error))
