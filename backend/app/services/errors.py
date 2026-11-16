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
