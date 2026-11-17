import asyncio

import pytest

from app.cache.ports import Cache

pytestmark = pytest.mark.anyio


class Source:
    """What is slow to read: counts how often it was asked."""

    def __init__(self, delay: float = 0.0) -> None:
        self.asked = 0
        self.delay = delay
        self.broken = False

    async def __call__(self) -> str:
        self.asked += 1
        await asyncio.sleep(self.delay)
        if self.broken:
            raise RuntimeError
        return f"value {self.asked}"


async def test_value_is_loaded_once_and_then_kept(cache: Cache) -> None:
    """R-CH-01."""
    source = Source()

    first = await cache.get_or_load("list", 30, source)
    second = await cache.get_or_load("list", 30, source)

    assert (first, second, source.asked) == ("value 1", "value 1", 1)


async def test_value_is_loaded_anew_after_its_time(cache: Cache) -> None:
    """R-CH-01."""
    source = Source()

    await cache.get_or_load("list", 0.05, source)
    await asyncio.sleep(0.12)

    assert await cache.get_or_load("list", 0.05, source) == "value 2"


async def test_keys_do_not_share_values(cache: Cache) -> None:
    domains, groups = Source(), Source()

    await cache.get_or_load("domains", 30, domains)
    await cache.get_or_load("groups", 30, groups)

    assert (domains.asked, groups.asked) == (1, 1)


async def test_dropped_value_is_loaded_anew(cache: Cache) -> None:
    """R-CH-05."""
    source = Source()
    await cache.get_or_load("list", 30, source)

    await cache.drop("list")
    await cache.drop("never-kept")

    assert await cache.get_or_load("list", 30, source) == "value 2"


async def test_simultaneous_readers_of_an_empty_cache_load_once(cache: Cache) -> None:
    """R-CH-03."""
    source = Source(delay=0.1)

    answers = await asyncio.gather(*(cache.get_or_load("list", 30, source) for _ in range(50)))

    assert source.asked == 1
    assert set(answers) == {"value 1"}


async def test_failed_load_is_raised_and_nothing_is_kept(cache: Cache) -> None:
    """R-CH-03."""
    source = Source()
    source.broken = True

    with pytest.raises(RuntimeError):
        await cache.get_or_load("list", 30, source)
    source.broken = False

    assert await cache.get_or_load("list", 30, source) == "value 2"


async def test_reachable_cache_answers_a_ping(cache: Cache) -> None:
    await cache.ping()
