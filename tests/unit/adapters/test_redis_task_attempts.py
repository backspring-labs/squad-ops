"""A dispatched task's delivery record in Redis (#1977).

What bugs would these catch? An attempt count that never expires, or whose expiry is pushed
back by each delivery, so a task's record outlives its TTL forever; a completion mark that never
expires; and the agent's factory reading anything but the config's URL and TTL.
"""

from __future__ import annotations

import pytest

from adapters.comms.redis_task_attempts import RedisTaskAttempts


class _Redis:
    """The four commands the record uses, with each key's TTL as Redis would hold it."""

    def __init__(self) -> None:
        self.values: dict[str, int | str] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = int(self.values.get(key, 0)) + 1
        return int(self.values[key])

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.values[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def exists(self, key: str) -> int:
        return int(key in self.values)


async def test_attempts_count_up_and_expire_from_the_first_delivery():
    redis = _Redis()
    record = RedisTaskAttempts(redis, ttl_seconds=600)

    counts = [await record.begin_attempt("t1") for _ in range(3)]
    redis.ttls["comms:attempts:t1"] = 17  # time passes; a later delivery must not push it back
    await record.begin_attempt("t1")

    assert counts == [1, 2, 3]
    assert redis.ttls["comms:attempts:t1"] == 17


async def test_a_task_is_completed_only_once_marked_and_the_mark_expires():
    redis = _Redis()
    record = RedisTaskAttempts(redis, ttl_seconds=600)

    before = await record.completed("t1")
    await record.mark_completed("t1")

    assert (before, await record.completed("t1"), await record.completed("t2")) == (
        False,
        True,
        False,
    )
    assert redis.ttls["comms:done:t1"] == 600


def test_the_agents_factory_reads_the_configs_url_and_ttl(monkeypatch):
    """Wiring: the agent builds its record through ``create_task_attempts(config.comms)``."""
    from adapters.comms import factory
    from squadops.config.schema import CommsDeliveryConfig

    built: dict = {}
    monkeypatch.setattr(
        RedisTaskAttempts,
        "from_url",
        classmethod(lambda cls, url, ttl: built.update(url=url, ttl=ttl) or "record"),
    )
    comms = type(
        "Comms",
        (),
        {
            "redis": type("R", (), {"url": "redis://redis:6379/0"})(),
            "delivery": CommsDeliveryConfig(marker_ttl_seconds=3600),
        },
    )()

    assert factory.create_task_attempts(comms) == "record"
    assert built == {"url": "redis://redis:6379/0", "ttl": 3600}


@pytest.mark.parametrize("ttl", [59, 0])
def test_a_marker_that_would_expire_within_a_minute_is_refused(ttl):
    from pydantic import ValidationError

    from squadops.config.schema import CommsDeliveryConfig

    with pytest.raises(ValidationError):
        CommsDeliveryConfig(marker_ttl_seconds=ttl)
