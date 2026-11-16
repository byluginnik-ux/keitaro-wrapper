"""Translate what services return into the types of the contract."""

import strawberry
from keitaro_contracts import types as gql

from app.keitaro import models as keitaro
from app.services import countries, models
from app.services.creator import NewCampaignRequest
from app.services.errors import CampaignCreationError, KeitaroError, ValidationError


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
