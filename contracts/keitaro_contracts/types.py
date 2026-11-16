"""Strawberry types of the contract.

GENERATED from schema.graphql by scripts/generate.sh — do not edit by hand.
Root operations are left out: the backend writes Query and Mutation itself.
"""

from __future__ import annotations
import strawberry


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
