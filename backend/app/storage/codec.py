"""The parts of a task that both databases keep as plain JSON."""

from datetime import datetime

from app.services.models import Payload, Refusal, TaskStep


def refusal_to_json(refusal: Refusal | None) -> Payload | None:
    """Write a refusal as plain JSON."""
    if refusal is None:
        return None
    return {
        "code": refusal.code,
        "message": refusal.message,
        "fields": dict(refusal.fields),
        "details": dict(refusal.details),
    }


def refusal_from_json(value: Payload | None) -> Refusal | None:
    """Read a refusal back."""
    if value is None:
        return None
    return Refusal(value["code"], value["message"], value["fields"], value["details"])


def steps_to_json(steps: tuple[TaskStep, ...]) -> list[Payload]:
    """Write the steps of a task as plain JSON; time goes as ISO 8601."""
    return [{"name": step.name, "at": step.at.isoformat(), "note": step.note} for step in steps]


def steps_from_json(value: list[Payload]) -> tuple[TaskStep, ...]:
    """Read the steps of a task back."""
    return tuple(
        TaskStep(item["name"], datetime.fromisoformat(item["at"]), item["note"]) for item in value
    )
