"""Translate what services return into the types of the contract."""

from keitaro_contracts import types as gql

from app.keitaro import models as keitaro
from app.services import countries


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
