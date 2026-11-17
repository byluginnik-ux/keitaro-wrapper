from dataclasses import replace

from scripts.load import Done, Evidence, judge, percentile, summary

CREATED = Done("t-1", "create_campaign", "succeeded", 0.4, campaign_name="test_bulygin_load_1")
PUBLISHED = Done("t-2", "publish_stream", "succeeded", 1.2, stream=7, offer=11114)
CLEAN = Evidence(
    queued=2,
    tasks_added=2,
    unfinished=0,
    outbox_waiting=0,
    done=[CREATED, PUBLISHED],
    campaigns=["test_bulygin_load_1"],
    shares={7: [(11111, 25), (11112, 25), (11113, 25), (11114, 25)]},
)


def test_clean_run_breaks_nothing() -> None:
    """R-OPS-06."""
    assert judge(CLEAN) == []


def test_every_broken_promise_is_named() -> None:
    """R-OPS-06."""
    broken = judge(
        replace(
            CLEAN,
            tasks_added=3,
            unfinished=1,
            outbox_waiting=4,
            campaigns=["test_bulygin_load_1", "test_bulygin_load_1"],
            shares={7: [(11111, 50), (11112, 49)]},
        )
    )

    assert broken == [
        "1 tasks never ended",
        "2 task IDs made 3 tasks",
        "4 messages stayed in the outbox",
        "test_bulygin_load_1: succeeded, 2 campaigns in the tracker",
        "stream 7: published without offer 11114",
        "stream 7: shares add up to 99",
    ]


def test_rejected_creation_must_leave_no_campaign() -> None:
    """R-OPS-06: the compensation is part of what the run proves."""
    rejected = replace(CREATED, status="rejected")

    assert judge(replace(CLEAN, done=[rejected], campaigns=[])) == []
    assert judge(replace(CLEAN, done=[rejected])) == [
        "test_bulygin_load_1: rejected, 1 campaigns in the tracker"
    ]


def test_rejected_publication_promises_nothing_about_the_tracker() -> None:
    rejected = replace(PUBLISHED, status="rejected")
    untouched = {7: [(11111, 34), (11112, 33), (11113, 33)]}

    assert judge(replace(CLEAN, done=[CREATED, rejected], shares=untouched)) == []


def test_percentile_is_the_nearest_rank() -> None:
    waited = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 5.0]

    assert (percentile(waited, 50), percentile(waited, 95), percentile(waited, 100)) == (
        0.5,
        5.0,
        5.0,
    )
    assert percentile([], 95) == 0.0
    assert percentile([2.0], 50) == 2.0


def test_summary_counts_tasks_and_their_wait() -> None:
    report = summary(replace(CLEAN, done=[CREATED, replace(PUBLISHED, status="rejected")]), 2.0)

    assert report == {
        "tasks": 2,
        "succeeded": 1,
        "rejected": 1,
        "seconds": 2.0,
        "tasks_per_second": 1.0,
        "p50": 0.4,
        "p95": 1.2,
    }
