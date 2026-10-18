"""Contract 7, read by the runner (SIP-0112 §8.2.1; SIP-0113 §4.1; #2414). The shared fixture's
recorded start declaration is what the runner starts."""

from __future__ import annotations

import pytest

from squadops.scenarios.runner import DeclaredStart, StartUndeclared, declared_start
from tests.fixtures.shared_contract.repository import recorded


def _declaration() -> dict:
    return recorded("development_configuration", "valid")["configuration"]["technical"]["commands"][
        "start"
    ]


def test_the_fixtures_declaration_reads_as_its_own_start():
    """Bug caught: a declared port or readiness path lost, so the runner publishes the wrong
    port or polls a path the product never answers; or the build dropped, so the start runs on
    an unbuilt tree."""
    start = declared_start(_declaration())

    assert start == DeclaredStart(
        start=("python3", "-m", "tally", "serve", "--host", "0.0.0.0", "--port", "18407"),
        port=18407,
        ready_path="/healthz",
        setup=(("python3", "tools/build.py"),),
        working_dir=".",
        ready_timeout_seconds=20.0,
    )
    assert DeclaredStart.from_dict(start.as_dict()) == start


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (None, "declares no start"),
        ({"start": []}, "declares no start"),
        ({"readiness": {"kind": "tcp", "target": "127.0.0.1:18407"}}, "no runner for readiness"),
        ({"readiness": {"kind": "http", "target": "http://127.0.0.1/healthz"}}, "names no port"),
    ],
    ids=["no-declaration", "no-start-argv", "tcp-readiness", "no-port"],
)
def test_a_declaration_the_runner_cannot_start_is_refused_as_undeclared(change, message):
    """Contract 7's missing declaration. Bug caught: a start guessed from a sample app, or a
    readiness the runner can't read treated as ready."""
    declaration = None if change is None else {**_declaration(), **change}

    with pytest.raises(StartUndeclared, match=message):
        declared_start(declaration)
