from collections.abc import Awaitable, Callable
from uuid import UUID

import strawberry
from keitaro_contracts import types as gql
from strawberry.types import Info

from app.graphql import mappers
from app.graphql.context import Context
from app.graphql.errors import ErrorCodes
from app.services import models
from app.services.countries import search_countries
from app.services.errors import (
    CampaignNotFoundError,
    DomainError,
    DraftNotPublishedError,
    KeitaroError,
    ValidationError,
)

type AppInfo = Info[Context, None]

UNKNOWN_STREAM = UUID(int=0)  # an ID that is not ours matches no stream


async def stream_result(
    stream_id: strawberry.ID, action: Callable[[UUID], Awaitable[models.Stream]]
) -> gql.StreamResult:
    """Run one action of the editor and answer with the stream or the typed refusal."""
    try:
        return mappers.to_stream(await action(mappers.to_uuid(stream_id) or UNKNOWN_STREAM))
    except DomainError as error:
        return mappers.to_stream_refusal(error)


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

    @strawberry.field(description="Кампании, известные сервису, сначала новые")
    async def campaigns(self, info: AppInfo) -> list[gql.Campaign]:
        return [mappers.to_campaign(item) for item in await info.context.editor.campaigns()]

    @strawberry.field(description="Кампания по нашему идентификатору; null — такой нет")
    async def campaign(self, info: AppInfo, id: strawberry.ID) -> gql.Campaign | None:  # noqa: A002 — the argument name is fixed by the contract
        campaign_id = mappers.to_uuid(id)
        found = await info.context.editor.campaign(campaign_id) if campaign_id else None
        return mappers.to_campaign(found) if found else None

    @strawberry.field(
        description="Потоки кампании в том виде, в каком они сохранены у нас, по порядку"
    )
    async def streams(self, info: AppInfo, campaign_id: strawberry.ID) -> list[gql.Stream]:
        owner = mappers.to_uuid(campaign_id)
        found = await info.context.editor.streams(owner) if owner else []
        return [mappers.to_stream(item) for item in found]


@strawberry.type
class Mutation:
    """Resolvers of the contract's Mutation; a business refusal is returned, not raised."""

    @strawberry.mutation(
        description="Создать кампанию: поток 1 уводит страну на Google, поток 2 ведёт на оффер"
    )
    async def create_campaign(
        self,
        info: AppInfo,
        input: gql.CreateCampaignInput,  # noqa: A002 — the argument name is fixed by the contract
    ) -> gql.CreateCampaignResult:
        try:
            campaign = await info.context.creator.create(mappers.to_new_campaign_request(input))
        except ValidationError as error:
            return mappers.to_validation_failed(error)
        except KeitaroError as error:
            return mappers.to_keitaro_failure(error)
        return mappers.to_campaign(campaign)

    @strawberry.mutation(
        description=(
            "Загрузить потоки кампании из Keitaro по её ID в трекере и сверить с сохранёнными"
        )
    )
    async def fetch_streams(
        self, info: AppInfo, campaign_keitaro_id: int
    ) -> gql.FetchStreamsResult:
        try:
            fetched = await info.context.editor.fetch(campaign_keitaro_id)
        except DraftNotPublishedError as error:
            return gql.DraftNotPublished(message=str(error))
        except CampaignNotFoundError as error:
            return gql.CampaignNotFound(message=str(error))
        except KeitaroError as error:
            return mappers.to_keitaro_failure(error)
        return mappers.to_streams_fetched(fetched)

    @strawberry.mutation(
        description="Добавить оффер в черновик потока; убранный оффер возвращается"
    )
    async def add_offer(
        self,
        info: AppInfo,
        input: gql.StreamOfferInput,  # noqa: A002 — the argument name is fixed by the contract
    ) -> gql.StreamResult:
        editor = info.context.editor
        return await stream_result(
            input.stream_id, lambda id_: editor.add_offer(id_, input.offer_id)
        )

    @strawberry.mutation(
        description=(
            "Убрать оффер из черновика: он остаётся в потоке со статусом REMOVED и долей 0"
        )
    )
    async def remove_offer(
        self,
        info: AppInfo,
        input: gql.StreamOfferInput,  # noqa: A002 — the argument name is fixed by the contract
    ) -> gql.StreamResult:
        editor = info.context.editor
        return await stream_result(
            input.stream_id, lambda id_: editor.remove_offer(id_, input.offer_id)
        )

    @strawberry.mutation(description="Вернуть убранный оффер")
    async def bring_back_offer(
        self,
        info: AppInfo,
        input: gql.StreamOfferInput,  # noqa: A002 — the argument name is fixed by the contract
    ) -> gql.StreamResult:
        editor = info.context.editor
        return await stream_result(
            input.stream_id, lambda id_: editor.bring_back(id_, input.offer_id)
        )

    @strawberry.mutation(
        description="Задать долю оффера и закрепить её; остальные доли пересчитываются"
    )
    async def pin_share(
        self,
        info: AppInfo,
        input: gql.PinShareInput,  # noqa: A002 — the argument name is fixed by the contract
    ) -> gql.StreamResult:
        editor = info.context.editor
        return await stream_result(
            input.stream_id, lambda id_: editor.pin_share(id_, input.offer_id, input.share)
        )

    @strawberry.mutation(description="Снять закрепление; оффер снова участвует в пересчёте")
    async def unpin_share(
        self,
        info: AppInfo,
        input: gql.StreamOfferInput,  # noqa: A002 — the argument name is fixed by the contract
    ) -> gql.StreamResult:
        editor = info.context.editor
        return await stream_result(
            input.stream_id, lambda id_: editor.unpin_share(id_, input.offer_id)
        )

    @strawberry.mutation(
        description="Отменить черновик: поток возвращается к опубликованному снимку"
    )
    async def cancel_draft(self, info: AppInfo, stream_id: strawberry.ID) -> gql.StreamResult:
        return await stream_result(stream_id, info.context.editor.cancel)


schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=[ErrorCodes])
