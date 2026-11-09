"""#2960: a deploy makes Caddy run the checkout's Caddyfile.

Caddy mounts the file singly, so a pulled change never reached the container, and a reload
re-read the old file and reported success.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "caddy_config", Path(__file__).parents[3] / "scripts" / "dev" / "ops" / "caddy_config.py"
)
cc = importlib.util.module_from_spec(_spec)
sys.modules["caddy_config"] = cc
_spec.loader.exec_module(cc)

NEW = b":4040 {\n\theader /x y\n}\n"
OLD = b":4040 {\n}\n"


class Box:
    """Caddy as the deploy reaches it: what it reads now, and what a restart makes it read."""

    def __init__(self, reads, after_restart=None, restart_ok=True):
        self.reads = list(reads)
        self.after_restart = after_restart
        self.restart_ok = restart_ok
        self.restarts = 0

    def read(self):
        return self.reads.pop(0) if self.reads else None

    def restart(self):
        self.restarts += 1
        if self.after_restart is not None:
            self.reads = list(self.after_restart)
        return self.restart_ok


@pytest.mark.parametrize(
    ("running", "state"),
    [(NEW, cc.MATCH), (OLD, cc.DIFFERS), (None, cc.UNREADABLE), (b"", cc.DIFFERS)],
    ids=["same", "older", "unreadable", "empty"],
)
def test_only_the_same_bytes_are_a_match(running, state):
    assert cc.compare(NEW, running) == state


def test_an_older_caddyfile_is_replaced_by_a_restart_not_a_reload():
    """The 11-07 case: after a pull Caddy still read the older file; a restart remounts it."""
    box = Box([OLD], after_restart=[None, NEW])

    assert cc.ensure(NEW, read=box.read, restart=box.restart, sleep=lambda s: None) == 0
    assert box.restarts == 1


def test_a_matching_caddyfile_restarts_nothing():
    box = Box([NEW])

    assert cc.ensure(NEW, read=box.read, restart=box.restart, sleep=lambda s: None) == 0
    assert box.restarts == 0


@pytest.mark.parametrize(
    ("box", "restarts"),
    [
        (Box([None]), 0),
        (Box([OLD], after_restart=[OLD]), 1),
        (Box([OLD], restart_ok=False), 1),
    ],
    ids=["caddy not running", "still old after restart", "restart failed"],
)
def test_a_caddyfile_caddy_doesnt_run_fails_the_deploy(box, restarts):
    """An unreadable file is reported, never taken as a match, and a restart that didn't take fails."""
    assert cc.ensure(NEW, read=box.read, restart=box.restart, sleep=lambda s: None) == 1
    assert box.restarts == restarts
