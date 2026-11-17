"""Translate what services return into the types of the contract."""

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
    StreamNotFoundError,
    ValidationError,
)
from app.services.shares import OfferState


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
    | gql.StreamNotFound
    | gql.OfferNotFound
    | gql.OfferAlreadyInStream
    | gql.ShareOverflow
    | gql.EmptyStream
    | gql.ValidationFailed
    | gql.KeitaroFailure
)


MESSAGE_ONLY = {
    StreamNotFoundError: gql.StreamNotFound,
    OfferNotFoundError: gql.OfferNotFound,
    OfferAlreadyInStreamError: gql.OfferAlreadyInStream,
    ShareOverflowError: gql.ShareOverflow,
    EmptyStreamError: gql.EmptyStream,
}


def to_stream_refusal(error: DomainError) -> StreamRefusal:
    """Turn a refusal of the editor into its member of StreamResult; anything else is a bug."""
    if isinstance(error, ValidationError):
        return to_validation_failed(error)
    if isinstance(error, KeitaroError):
        return to_keitaro_failure(error)
    for kind, answer in MESSAGE_ONLY.items():
        if isinstance(error, kind):
            return answer(message=str(error))
    raise error
