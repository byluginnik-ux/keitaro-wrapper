from uuid import UUID


class StorageConflictError(Exception):
    """Another writer got there first: read again and decide anew (R-CC-02)."""


class StaleStreamError(StorageConflictError):
    """The stream was changed after it was read."""

    def __init__(self, stream_id: UUID) -> None:
        super().__init__(f"stream {stream_id} was changed by another writer")
        self.stream_id = stream_id


class DuplicateError(StorageConflictError):
    """A record with the same identity is already stored."""


class MissingParentError(LookupError):
    """A stream refers to a campaign that is not stored."""
