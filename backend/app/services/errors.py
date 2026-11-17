from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.models import Stream


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


class StreamNotFoundError(DomainError):
    """Our storage has no such stream."""

    code = "stream_not_found"

    def __init__(self) -> None:
        super().__init__("Поток не найден: загрузите потоки кампании заново")


class OfferNotFoundError(DomainError):
    """The tracker has no such active offer, or the stream does not hold it."""

    code = "offer_not_found"


class OfferAlreadyInStreamError(DomainError):
    """The offer already takes traffic in the stream (R-ED-11)."""

    code = "offer_already_in_stream"

    def __init__(self, name: str) -> None:
        super().__init__(f"Оффер «{name}» уже есть в потоке")


class EmptyStreamError(DomainError):
    """Nothing to publish: the stream has no active offers (R-ED-23)."""

    code = "empty_stream"

    def __init__(self, name: str) -> None:
        super().__init__(f"В потоке «{name}» нет активных офферов — публиковать нечего")


class StreamBusyError(DomainError):
    """A task is publishing the stream; until it ends the stream stays as it is (R-ED-25)."""

    code = "stream_busy"

    def __init__(self, name: str) -> None:
        super().__init__(f"Поток «{name}» публикуется — дождитесь завершения")


class TaskKeyReusedError(DomainError):
    """The ID of a task was already used for another request (R-TK-04)."""

    code = "task_key_reused"

    def __init__(self) -> None:
        super().__init__("Этот идентификатор задачи уже использован для другого запроса")


class TaskNotFoundError(DomainError):
    code = "task_not_found"

    def __init__(self) -> None:
        super().__init__("Такой задачи нет")


class TaskNotCancellableError(DomainError):
    """Only a task nobody has taken yet can be cancelled (R-TK-08)."""

    code = "task_not_cancellable"

    def __init__(self) -> None:
        super().__init__("Отменить можно только задачу, которая ещё ждёт выполнения")


class TaskNotRetryableError(DomainError):
    """Only a rejected publication can be repeated (R-TK-09)."""

    code = "task_not_retryable"

    def __init__(self) -> None:
        super().__init__("Повторить можно только отклонённую публикацию")


class StreamConflictError(DomainError):
    """Somebody else changed the stream first; nothing of this request was applied (R-CC-03).

    `current` is the stream as it is stored now, when there is one to show (R-CC-06).
    """

    code = "stream_conflict"

    def __init__(self, current: "Stream | None" = None) -> None:
        super().__init__("Поток изменён другим запросом — показано его актуальное состояние")
        self.current = current
