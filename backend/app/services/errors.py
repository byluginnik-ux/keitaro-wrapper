from app.keitaro.models import Domain


class DomainError(Exception):
    """A rule of the domain was violated; `code` is stable and safe to show to clients."""

    code: str = "domain_error"


class ShareOverflowError(DomainError):
    """Pinned shares leave no valid way to split 100% between active offers (R-SH-08, R-SH-09)."""

    code = "share_overflow"

    def __init__(self, pinned_total: int, free_count: int) -> None:
        super().__init__(
            f"Закреплено {pinned_total}%, незакреплённых активных офферов: {free_count} — "
            "распределить 100% невозможно",
        )
        self.pinned_total = pinned_total
        self.free_count = free_count


class KeitaroError(DomainError):
    """Keitaro refused the request, answered with garbage or did not answer at all (R-KT-02)."""

    code = "keitaro_error"

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ValidationError(DomainError):
    """The input breaks the rules; `fields` maps an input field to the remark about it."""

    code = "validation_failed"

    def __init__(self, fields: dict[str, str]) -> None:
        super().__init__("Проверьте поля: " + ", ".join(fields))
        self.fields = fields


class CampaignCreationError(KeitaroError):
    """The tracker failed while a campaign was being assembled (R-CR-07, R-CR-12)."""

    def __init__(
        self, message: str, status: int | None = None, created_domain: Domain | None = None
    ) -> None:
        super().__init__(message, status)
        self.created_domain = created_domain


class CampaignNotFoundError(DomainError):
    """Neither our storage nor the tracker knows the campaign (R-ED-07)."""

    code = "campaign_not_found"

    def __init__(self, keitaro_id: int) -> None:
        super().__init__(f"В Keitaro нет кампании {keitaro_id}")


class DraftNotPublishedError(DomainError):
    """A draft would be lost: publish or cancel it first (R-ED-06)."""

    code = "draft_not_published"

    def __init__(self, stream_names: list[str]) -> None:
        super().__init__(
            "Есть неопубликованные изменения: " + ", ".join(stream_names) + ". "
            "Опубликуйте или отмените их, затем загрузите потоки снова"
        )
