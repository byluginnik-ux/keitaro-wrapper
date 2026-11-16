import secrets
import string
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.keitaro.gateway import KeitaroGateway
from app.services.catalog import CatalogService
from app.services.models import Campaign
from app.storage.ports import Storage

ALIAS_ALPHABET = string.ascii_lowercase + string.digits
ALIAS_LENGTH = 8


def random_alias() -> str:
    """Make the part of the campaign address the tracker requires to be unique."""
    return "".join(secrets.choice(ALIAS_ALPHABET) for _ in range(ALIAS_LENGTH))


def utc_now() -> datetime:
    """Return the current moment; replaced in tests."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class NewCampaignRequest:
    """What the creator form sends; exactly one of `domain_id` and `new_domain_name` is set."""

    name: str
    country: str
    offer_id: int
    group_id: int
    traffic_source_id: int
    domain_id: int | None = None
    new_domain_name: str | None = None


class CreatorService:
    """Assemble a campaign with its two streams in the tracker and remember it (R-CR-01…12)."""

    def __init__(  # noqa: PLR0913 — collaborators are passed explicitly, there is no container
        self,
        keitaro: KeitaroGateway,
        catalog: CatalogService,
        storage: Storage,
        *,
        name_prefix: str,
        clock: Callable[[], datetime] = utc_now,
        new_alias: Callable[[], str] = random_alias,
    ) -> None:
        self._keitaro = keitaro
        self._catalog = catalog
        self._storage = storage
        self._name_prefix = name_prefix
        self._clock = clock
        self._new_alias = new_alias

    async def create(self, request: NewCampaignRequest) -> Campaign:
        raise NotImplementedError
