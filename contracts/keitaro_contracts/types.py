"""Strawberry types of the contract.

GENERATED from schema.graphql by scripts/generate.sh — do not edit by hand.
Root operations are left out: the backend writes Query and Mutation itself.
"""

from __future__ import annotations
import strawberry
from typing import Annotated


@strawberry.type(description="Домен трекера, на котором размещается кампания")
class Domain:
    id: int
    name: str


@strawberry.type(description="Группа кампаний")
class Group:
    id: int
    name: str


@strawberry.type(description="Источник трафика")
class TrafficSource:
    id: int
    name: str


@strawberry.type(description="Оффер, заведённый в Keitaro")
class Offer:
    id: int
    name: str


@strawberry.type(description="Страна ISO 3166-1")
class Country:
    code: str = strawberry.field(description="Код alpha-2 в верхнем регистре")
    name: str


@strawberry.type(description="Кампания, которую ведёт сервис")
class Campaign:
    id: strawberry.ID = strawberry.field(description="Наш идентификатор")
    keitaro_id: int = strawberry.field(description="Идентификатор кампании в Keitaro")
    name: str
    alias: str = strawberry.field(description="Псевдоним в адресе кампании")
    country: str | None = strawberry.field(description="Код страны alpha-2, заданный при создании")


@strawberry.input(description="Что создать: кампания с двумя потоками")
class CreateCampaignInput:
    name: str = strawberry.field(description="Название с обязательным префиксом тестовых кампаний")
    country: str = strawberry.field(
        description="Код страны alpha-2: её посетителей первый поток уводит на Google"
    )
    offer_id: int = strawberry.field(description="Оффер второго потока")
    group_id: int
    traffic_source_id: int
    domain_id: strawberry.Maybe[int | None] = strawberry.field(
        description="Существующий домен. Задаётся ровно одно из двух: domainId или newDomainName"
    )
    new_domain_name: strawberry.Maybe[str | None] = strawberry.field(
        description="Имя хоста нового домена: он создаётся в Keitaro перед кампанией"
    )


@strawberry.type(description="Замечание к одному полю ввода")
class FieldError:
    field: str = strawberry.field(description="Имя поля входного типа")
    message: str


@strawberry.type(description="Ввод не прошёл проверку; в Keitaro ничего не изменено")
class ValidationFailed:
    message: str
    fields: list[FieldError]


@strawberry.type(
    description="Keitaro отказал или не ответил; незавершённых кампаний в трекере не оставлено"
)
class KeitaroFailure:
    message: str
    created_domain: Domain | None = strawberry.field(
        description="Домен, который успел создаться до сбоя и остался в трекере"
    )


CreateCampaignResult = Annotated[
    Campaign | ValidationFailed | KeitaroFailure, strawberry.union(name="CreateCampaignResult")
]
