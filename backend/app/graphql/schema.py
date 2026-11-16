import strawberry
from keitaro_contracts import types as gql
from strawberry.types import Info

from app.graphql import mappers
from app.graphql.context import Context
from app.graphql.errors import ErrorCodes
from app.services.countries import search_countries

type AppInfo = Info[Context, None]


@strawberry.type
class Query:
    """Resolvers of the contract's Query; signatures and descriptions repeat schema.graphql."""

    @strawberry.field(description="Домены трекера, на которых можно разместить кампанию")
    async def domains(self, info: AppInfo) -> list[gql.Domain]:
        return [mappers.to_domain(item) for item in await info.context.catalog.domains()]

    @strawberry.field(description="Группы кампаний")
    async def groups(self, info: AppInfo) -> list[gql.Group]:
        return [mappers.to_group(item) for item in await info.context.catalog.groups()]

    @strawberry.field(description="Источники трафика")
    async def traffic_sources(self, info: AppInfo) -> list[gql.TrafficSource]:
        sources = await info.context.catalog.traffic_sources()
        return [mappers.to_traffic_source(item) for item in sources]

    @strawberry.field(description="Активные офферы: поиск по фрагменту названия или началу ID")
    async def offers(self, info: AppInfo, search: str = "", limit: int = 20) -> list[gql.Offer]:
        found = await info.context.catalog.search_offers(search, limit)
        return [mappers.to_offer(item) for item in found]

    @strawberry.field(description="Страны: поиск по названию или началу кода")
    def countries(self, search: str = "") -> list[gql.Country]:
        return [mappers.to_country(item) for item in search_countries(search)]


schema = strawberry.Schema(query=Query, extensions=[ErrorCodes])
