from collections.abc import Iterator

from strawberry.extensions import SchemaExtension

from app.services.errors import DomainError

INTERNAL_ERROR = "Внутренняя ошибка сервера"


class ErrorCodes(SchemaExtension):
    """Give every error a stable code; hide the text of anything that is not a domain error."""

    def on_operation(self) -> Iterator[None]:
        yield
        result = self.execution_context.result
        for error in (result.errors if result else None) or []:
            original = error.original_error
            if isinstance(original, DomainError):
                error.extensions = {"code": original.code}
            elif original is not None:
                error.message = INTERNAL_ERROR
                error.extensions = {"code": "internal_error"}
