"""Strawberry types of the contract.

GENERATED from schema.graphql by scripts/generate.sh — do not edit by hand.
Root operations are left out: the backend writes Query and Mutation itself.
"""

from __future__ import annotations
import strawberry
from enum import Enum
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


@strawberry.enum
class OfferState(Enum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


@strawberry.type(description="Что было в Keitaro для оффера при последней загрузке или публикации")
class PublishedOffer:
    share: int
    state: OfferState
    pinned: bool


@strawberry.type(description="Оффер в потоке: черновик и опубликованный снимок")
class StreamOffer:
    offer_id: int
    name: str
    share: int = strawberry.field(description="Доля в процентах; у убранного оффера 0")
    pinned: bool = strawberry.field(description="Доля закреплена и не меняется при пересчёте")
    state: OfferState
    published: PublishedOffer | None = strawberry.field(
        description="Опубликованный снимок; null — оффер ещё не публиковался"
    )
    changed: bool = strawberry.field(description="Публикация изменит этот оффер в Keitaro")


@strawberry.type(description="Поток кампании")
class Stream:
    id: strawberry.ID = strawberry.field(description="Наш идентификатор")
    keitaro_id: int = strawberry.field(description="Идентификатор потока в Keitaro")
    campaign_id: strawberry.ID
    name: str
    position: int = strawberry.field(description="Порядковый номер в кампании")
    kind: str = strawberry.field(
        description="Схема потока в Keitaro: landings — офферы, redirect — перенаправление"
    )
    dirty: bool = strawberry.field(description="Есть неопубликованные изменения")
    offers: list[StreamOffer] = strawberry.field(
        description="Офферы в порядке добавления; у потока-перенаправления список пуст"
    )


@strawberry.type(description="Потоки загружены из Keitaro и сохранены")
class StreamsFetched:
    campaign: Campaign
    streams: list[Stream]


@strawberry.type(
    description="В кампании есть неопубликованный черновик: его нужно опубликовать или отменить"
)
class DraftNotPublished:
    message: str


@strawberry.type(description="В Keitaro нет кампании с таким ID")
class CampaignNotFound:
    message: str


@strawberry.type(
    description="Keitaro отказал или не ответил; незавершённых кампаний в трекере не оставлено"
)
class KeitaroFailure:
    message: str
    created_domain: Domain | None = strawberry.field(
        description="Домен, который успел создаться до сбоя и остался в трекере"
    )


@strawberry.type(description="У нас нет такого потока")
class StreamNotFound:
    message: str


@strawberry.type(description="Оффера нет в Keitaro или в потоке — смотря что требовалось действию")
class OfferNotFound:
    message: str


@strawberry.type(description="Оффер уже получает трафик в этом потоке")
class OfferAlreadyInStream:
    message: str


@strawberry.type(
    description="Закреплённые доли не дают разделить 100 % между активными офферами; черновик не изменён"
)
class ShareOverflow:
    message: str


@strawberry.type(description="Ввод не прошёл проверку; в Keitaro ничего не изменено")
class ValidationFailed:
    message: str
    fields: list[FieldError]


@strawberry.input(description="Оффер в потоке, над которым выполняется действие")
class StreamOfferInput:
    stream_id: strawberry.ID
    offer_id: int


@strawberry.input(description="Закрепить долю оффера")
class PinShareInput:
    stream_id: strawberry.ID
    offer_id: int
    share: int = strawberry.field(description="Доля от 1 до 100")


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


FetchStreamsResult = Annotated[
    StreamsFetched | DraftNotPublished | CampaignNotFound | KeitaroFailure,
    strawberry.union(name="FetchStreamsResult"),
]

StreamResult = Annotated[
    Stream
    | StreamNotFound
    | OfferNotFound
    | OfferAlreadyInStream
    | ShareOverflow
    | ValidationFailed
    | KeitaroFailure,
    strawberry.union(name="StreamResult"),
]

CreateCampaignResult = Annotated[
    Campaign | ValidationFailed | KeitaroFailure, strawberry.union(name="CreateCampaignResult")
]
