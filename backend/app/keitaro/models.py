from pydantic import BaseModel, ConfigDict, Field


class KeitaroModel(BaseModel):
    """Base for everything read from Keitaro: unknown fields are ignored (R-KT-01)."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class Domain(KeitaroModel):
    id: int
    name: str
    state: str = "active"


class Group(KeitaroModel):
    id: int
    name: str


class TrafficSource(KeitaroModel):
    id: int
    name: str


class Offer(KeitaroModel):
    id: int
    name: str
    state: str = "active"


class Campaign(KeitaroModel):
    id: int
    name: str
    alias: str
    state: str = "active"
    domain_id: int | None = None
    group_id: int | None = None
    traffic_source_id: int | None = None


class StreamOffer(KeitaroModel):
    offer_id: int
    share: int
    state: str = "active"


class Stream(KeitaroModel):
    id: int
    campaign_id: int
    name: str
    position: int
    type: str
    kind: str = Field(alias="schema")
    state: str = "active"
    offers: tuple[StreamOffer, ...] = ()


class NewCampaign(BaseModel):
    """Body of `POST /campaigns`."""

    model_config = ConfigDict(frozen=True)

    name: str
    alias: str
    domain_id: int
    group_id: int
    traffic_source_id: int
    type: str = "position"


class StreamFilter(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    mode: str
    payload: tuple[str, ...]


class NewStream(BaseModel):
    """Body of `POST /streams`; `kind` travels as `schema`."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    campaign_id: int
    name: str
    position: int
    kind: str = Field(serialization_alias="schema")
    type: str = "regular"
    action_type: str = "http"
    action_payload: str = ""
    filters: tuple[StreamFilter, ...] = ()
    offers: tuple[StreamOffer, ...] = ()
