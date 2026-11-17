"""Load the stack through the BFF and prove nothing was lost or done twice (R-OPS-06).

Run against the stack of `compose.load.yaml`, never against a real tracker:

    uv run python -m scripts.load --frontend http://127.0.0.1:3000 --tracker http://127.0.0.1:8791
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

FULL = 100
type Shares = list[tuple[int, int]]


@dataclass(frozen=True, slots=True)
class Done:
    """What became of one queued task."""

    task_id: str
    kind: str
    status: str
    seconds: float
    campaign_name: str | None = None
    stream: int | None = None
    offer: int | None = None


@dataclass(frozen=True, slots=True)
class Evidence:
    """Everything the run is judged by, read after the last task ended."""

    queued: int
    tasks_added: int
    unfinished: int
    outbox_waiting: int
    done: Sequence[Done] = ()
    campaigns: Sequence[str] = ()
    shares: dict[int, list[tuple[int, int]]] = field(
        default_factory=dict[int, list[tuple[int, int]]]
    )


def percentile(values: Sequence[float], share: float) -> float:
    """Return the value at most `share` percent of the values exceed (nearest rank)."""
    raise NotImplementedError


def judge(evidence: Evidence) -> list[str]:
    """Name every way the run broke its promises; an empty list is a pass."""
    raise NotImplementedError


def summary(evidence: Evidence, elapsed: float) -> dict[str, float | int]:
    """Count what the run did and how long a task waited for its end."""
    raise NotImplementedError
