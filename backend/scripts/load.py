"""Load the stack through the BFF and prove nothing was lost or done twice (R-OPS-06).

Run against the stack of `compose.load.yaml`, never against a real tracker:

    uv run python -m scripts.load --frontend http://127.0.0.1:3000 --tracker http://127.0.0.1:8791
"""

import argparse
import asyncio
import math
import sys
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

import httpx

FULL = 100
type Shares = list[tuple[int, int]]
FAILING = ("replace_stream_offers", "create_stream")


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
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(math.ceil(share / 100 * len(ordered)), 1) - 1]


def _kept_promise(task: Done, evidence: Evidence) -> str | None:
    """Check one ended task against the tracker."""
    if task.kind == "create_campaign" and task.campaign_name is not None:
        found = list(evidence.campaigns).count(task.campaign_name)
        if found != (1 if task.status == "succeeded" else 0):
            return f"{task.campaign_name}: {task.status}, {found} campaigns in the tracker"
    if task.kind == "publish_stream" and task.status == "succeeded" and task.stream is not None:
        published = dict(evidence.shares.get(task.stream, []))
        if not published.get(task.offer or 0):
            return f"stream {task.stream}: published without offer {task.offer}"
    return None


def judge(evidence: Evidence) -> list[str]:
    """Name every way the run broke its promises; an empty list is a pass."""
    broken: list[str] = []
    if evidence.unfinished:
        broken.append(f"{evidence.unfinished} tasks never ended")
    if evidence.tasks_added != evidence.queued:
        broken.append(f"{evidence.queued} task IDs made {evidence.tasks_added} tasks")
    if evidence.outbox_waiting:
        broken.append(f"{evidence.outbox_waiting} messages stayed in the outbox")
    broken += [said for task in evidence.done if (said := _kept_promise(task, evidence))]
    broken += [
        f"stream {stream}: shares add up to {total}"
        for stream, offers in evidence.shares.items()
        if (total := sum(share for _, share in offers)) != FULL
    ]
    return broken


def summary(evidence: Evidence, elapsed: float) -> dict[str, float | int]:
    """Count what the run did and how long a task waited for its end."""
    waited = [task.seconds for task in evidence.done]
    return {
        "tasks": len(evidence.done),
        "succeeded": sum(task.status == "succeeded" for task in evidence.done),
        "rejected": sum(task.status == "rejected" for task in evidence.done),
        "seconds": round(elapsed, 2),
        "tasks_per_second": round(len(evidence.done) / elapsed, 1) if elapsed else 0,
        "p50": round(percentile(waited, 50), 2),
        "p95": round(percentile(waited, 95), 2),
    }


def _took(task: dict[str, Any]) -> float:
    start, end = (datetime.fromisoformat(task[key]) for key in ("createdAt", "finishedAt"))
    return (end - start).total_seconds()


async def _json(response: httpx.Response) -> Any:  # noqa: ANN401 — whatever the BFF answered
    response.raise_for_status()
    return response.json()


async def _all[T](jobs: Sequence[Callable[[], Awaitable[T]]], at_once: int) -> list[T]:
    gate = asyncio.Semaphore(at_once)

    async def one(job: Callable[[], Awaitable[T]]) -> T:
        async with gate:
            return await job()

    return await asyncio.gather(*(one(job) for job in jobs))


async def _total(front: httpx.AsyncClient) -> tuple[int, int]:
    queue = (await _json(await front.get("/api/tasks")))["queue"]
    return sum(row["count"] for row in queue["tasks"]), queue["outboxWaiting"]


async def run(args: argparse.Namespace) -> tuple[Evidence, float]:  # noqa: C901, PLR0915 — one scenario read top to bottom
    """Carry the scenario out and collect what it is judged by."""
    tag = uuid4().hex[:6]
    async with (
        httpx.AsyncClient(base_url=args.frontend, timeout=60) as front,
        httpx.AsyncClient(base_url=args.tracker, timeout=60) as tracker,
    ):
        options = await _json(await front.get("/api/creator/options"))
        offers = [offer["id"] for offer in await _json(await front.get("/api/offers"))]

        async def prepare() -> tuple[str, int, int]:
            made = await _json(await tracker.post("/__test/campaign", json={}))
            screen = await _json(
                await front.post("/api/campaigns/fetch", json={"keitaroId": made["campaignId"]})
            )
            stream = next(item for item in screen["streams"] if item["acceptsOffers"])
            have = {
                offer
                for offer, _ in await _json(
                    await tracker.get(f"/__test/streams/{stream['keitaroId']}/offers")
                )
            }
            extra = next(offer for offer in offers if offer not in have)
            await _json(
                await front.post(f"/api/streams/{stream['id']}/offers", json={"offerId": extra})
            )
            return stream["id"], stream["keitaroId"], extra

        drafts = await _all([prepare] * args.streams, args.at_once)
        before, _ = await _total(front)

        async def twice(url: str, body: dict[str, Any]) -> str:
            first = await _json(await front.post(url, json=body))
            second = await _json(await front.post(url, json=body))
            if first["id"] != second["id"]:
                message = f"one task ID answered with two tasks: {first['id']}, {second['id']}"
                raise RuntimeError(message)
            return first["id"]

        names: dict[str, str] = {}
        published: dict[str, tuple[int, int]] = {}

        def publication(
            stream_id: str, keitaro_id: int, offer: int
        ) -> Callable[[], Awaitable[str]]:
            async def queue() -> str:
                task_id = str(uuid4())
                published[task_id] = (keitaro_id, offer)
                return await twice(f"/api/streams/{stream_id}/push", {"taskId": task_id})

            return queue

        def creation(number: int) -> Callable[[], Awaitable[str]]:
            async def queue() -> str:
                task_id = str(uuid4())
                names[task_id] = f"{options['namePrefix']}load_{tag}_{number}"
                body = {
                    "taskId": task_id,
                    "name": names[task_id],
                    "country": "AU",
                    "offerId": offers[0],
                    "groupId": options["groups"][0]["id"],
                    "trafficSourceId": options["trafficSources"][0]["id"],
                    "domainId": options["domains"][0]["id"],
                }
                return await twice("/api/campaigns", body)

            return queue

        async def outage() -> None:
            await asyncio.sleep(args.outage_after)
            for method in FAILING:
                await tracker.post("/__test/fail", json={"method": method, "on": True})
            await asyncio.sleep(args.outage)
            for method in FAILING:
                await tracker.post("/__test/fail", json={"method": method, "on": False})

        started = time.monotonic()
        jobs = [publication(*draft) for draft in drafts]
        jobs += [creation(number) for number in range(args.campaigns)]
        task_ids, _ = await asyncio.gather(_all(jobs, args.at_once), outage())

        async def follow(task_id: str) -> dict[str, Any] | None:
            deadline = time.monotonic() + args.patience
            while time.monotonic() < deadline:
                task = await _json(await front.get(f"/api/tasks/{task_id}"))
                if task["finished"]:
                    return task
                await asyncio.sleep(0.2)
            return None

        ended = await _all(
            [lambda task_id=task_id: follow(task_id) for task_id in task_ids], args.at_once
        )
        elapsed = time.monotonic() - started

        after, waiting = await _total(front)
        for _ in range(50):
            if not waiting:
                break
            await asyncio.sleep(0.2)
            after, waiting = await _total(front)

        done = [
            Done(
                task["id"],
                task["kind"],
                task["status"],
                _took(task),
                names.get(task["id"]),
                *published.get(task["id"], (None, None)),
            )
            for task in ended
            if task is not None
        ]
        mine = f"{options['namePrefix']}load_{tag}_"
        campaigns = [
            campaign["name"]
            for campaign in await _json(await tracker.get("/__test/campaigns"))
            if campaign["name"].startswith(mine)
        ]
        shares = {
            keitaro_id: [
                (offer, share)
                for offer, share in await _json(
                    await tracker.get(f"/__test/streams/{keitaro_id}/offers")
                )
            ]
            for _, keitaro_id, _ in drafts
        }
    evidence = Evidence(
        queued=len(set(task_ids)),
        tasks_added=after - before,
        unfinished=ended.count(None),
        outbox_waiting=waiting,
        done=done,
        campaigns=campaigns,
        shares=shares,
    )
    return evidence, elapsed


def main() -> int:
    """Run the scenario, print its numbers and fail if a promise was broken."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--frontend", default="http://127.0.0.1:3000")
    parser.add_argument("--tracker", default="http://127.0.0.1:8791")
    parser.add_argument("--streams", type=int, default=100, help="publications to queue")
    parser.add_argument("--campaigns", type=int, default=50, help="creations to queue")
    parser.add_argument("--at-once", type=int, default=25, help="simultaneous requests")
    parser.add_argument("--outage-after", type=float, default=0.5)
    parser.add_argument("--outage", type=float, default=1.5, help="seconds the tracker fails")
    parser.add_argument("--patience", type=float, default=120.0, help="seconds to wait for a task")
    evidence, elapsed = asyncio.run(run(parser.parse_args()))
    for name, value in summary(evidence, elapsed).items():
        print(f"{name}: {value}")  # noqa: T201 — the report of a command-line script
    broken = judge(evidence)
    for line in broken:
        print(f"BROKEN: {line}", file=sys.stderr)  # noqa: T201
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
