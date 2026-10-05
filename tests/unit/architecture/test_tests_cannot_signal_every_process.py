"""No test can signal every process, or its own process group (#1983).

On 2026-10-05 a unit test mocked a subprocess, the code's timeout path handed the mock's
``pid`` to ``os.killpg``, and a mock's ``pid`` converts to 1: ``killpg(1)`` is ``kill(-1)``.
Every process of the user running the suite was killed, twice: the SSH session, tmux, the
agent driving the run, and the Keycloak container, whose process runs under the same uid.
``bounded_run.signal_group`` refuses such a target in the code; ``tests/conftest.py`` refuses
it for the whole run, for the next signal site that does not go through that helper. This
asserts the second layer is standing.

Every call here sends signal 0, which delivers nothing and only checks permission. If the guard
were gone, these calls would return quietly and the test would fail; nothing is ever sent.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize(
    ("name", "target"),
    [
        ("killpg", 1),
        ("killpg", MagicMock().pid),
        ("killpg", 0),
        ("kill", -1),
        ("kill", 0),
        ("kill", MagicMock().pid),
    ],
    ids=[
        "killpg-every-process",
        "killpg-mock-pid",
        "killpg-own-group",
        "kill-every-process",
        "kill-own-group",
        "kill-mock-pid",
    ],
)
def test_a_signal_to_every_process_or_the_runs_own_group_is_refused(name, target):
    with pytest.raises(RuntimeError, match="tests/conftest.py refused"):
        getattr(os, name)(target, 0)


def test_a_signal_to_one_real_process_still_goes_through():
    """The guard narrows the target, not the call: a liveness check on a real pid still works."""
    assert os.kill(os.getpid(), 0) is None
