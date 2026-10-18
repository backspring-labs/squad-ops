"""Contract 7, read by the runner (SIP-0112 §8.2.1; SIP-0113 §4.1; #2414). The shared fixture's
recorded start declaration is what the runner starts, and a declaration that breaks contract 7's
schema is refused as one."""

from __future__ import annotations

import pytest

from squadops.scenarios.evaluation import BlockedReason
from squadops.scenarios.runner import (
    DeclaredStart,
    ReadinessUnsupported,
    StartUndeclared,
    declared_start,
)
from tests.fixtures.shared_contract.repository import recorded


def _declaration(**change) -> dict:
    start = recorded("development_configuration", "valid")["configuration"]["technical"][
        "commands"
    ]["start"]
    return {**start, **change}


def test_the_fixtures_declaration_reads_as_its_own_start_from_its_revision():
    """Bug caught: a declared port, readiness path or timeout lost, so the runner publishes the
    wrong port or polls a path the product never answers; the build dropped, so the start runs on
    an unbuilt tree; or the revision dropped, so the record can't say which one started it."""
    start = declared_start(_declaration(), configuration_revision=1)

    assert start == DeclaredStart(
        start=("python3", "-m", "tally", "serve", "--host", "0.0.0.0", "--port", "18407"),
        port=18407,
        ready_kind="http",
        ready_path="/healthz",
        ready_timeout_seconds=20.0,
        setup=(("python3", "tools/build.py"),),
        working_dir=".",
        configuration_revision=1,
        api_port=18407,
        api_path="",
    )
    assert DeclaredStart.from_dict(start.as_dict()) == start


@pytest.mark.parametrize(
    ("entry_points", "api"),
    [
        ([{"kind": "http_base", "url": "http://127.0.0.1:18410/v1/"}], (18410, "/v1")),
        ([{"kind": "ui_base", "url": "http://127.0.0.1:18407/"}], (None, "")),
    ],
    ids=["an-api-on-another-port-and-path", "a-ui-only-product"],
)
def test_the_http_base_entry_point_is_where_scenarios_reach_the_api(entry_points, api):
    """#2421's entry points. Bug caught: scenarios sent to the readiness port's root, so an API
    on a second port or under a path prefix is lost; or a product with no API given one."""
    start = declared_start(_declaration(entry_points=entry_points), configuration_revision=1)

    assert (start.api_port, start.api_path) == api


@pytest.mark.parametrize("target", ["127.0.0.1:18407", "tcp://127.0.0.1:18407"])
def test_a_tcp_readiness_reads_as_a_connection_to_its_port(target):
    """Contract 7's ``tcp`` kind (blocker 1 of #2450's review). Bug caught: a Project that
    declared a valid readiness told it declared no start."""
    start = declared_start(
        _declaration(readiness={"kind": "tcp", "target": target, "timeout_seconds": 5}),
        configuration_revision=2,
    )

    assert (start.ready_kind, start.port, start.ready_path) == ("tcp", 18407, "")


def test_a_command_readiness_is_no_runner_not_no_declaration():
    """``command`` is a valid kind whose target the contract names as a string, not an argv,
    so this runner doesn't check it. Bug caught: a Project told it declared nothing, the reason
    ``no_start_declaration`` where the gap is the runner's."""
    with pytest.raises(ReadinessUnsupported) as refused:
        declared_start(
            _declaration(readiness={"kind": "command", "target": "probe", "timeout_seconds": 5}),
            configuration_revision=1,
        )

    assert refused.value.reason is BlockedReason.NO_RUNNER


@pytest.mark.parametrize(
    ("declaration", "message"),
    [
        (None, "declares no start"),
        (_declaration(start=[]), "declares no start"),
        (_declaration(start="python3 -m tally"), "never one string"),
        (_declaration(build=["python3", "tools/build.py"]), "never one string"),
        (_declaration(working_directory="../../.."), "inside the repository"),
        (_declaration(working_directory="/srv/app"), "inside the repository"),
        (
            _declaration(readiness={"kind": "http", "target": "http://127.0.0.1:1/h"}),
            "timeout_seconds",
        ),
        (
            _declaration(
                readiness={"kind": "http", "target": "http://127.0.0.1/h", "timeout_seconds": 5}
            ),
            "names no port",
        ),
        (_declaration(readiness={"kind": "grpc", "target": "x:1", "timeout_seconds": 5}), "grpc"),
        (_declaration(entry_points=[]), "at least one"),
        (_declaration(entry_points=[{"kind": "http_base", "url": "http://x/"}]), "names no port"),
    ],
    ids=[
        "no-declaration",
        "no-start-argv",
        "a-shell-string-start",
        "a-flat-build-list",
        "a-directory-up-and-out",
        "an-absolute-directory",
        "no-timeout",
        "no-port",
        "an-unknown-kind",
        "no-entry-points",
        "an-http-base-with-no-port",
    ],
)
def test_a_declaration_that_breaks_contract_7_is_refused_as_undeclared(declaration, message):
    """Contract 7's schema, checked where it is read. Bug caught: a start guessed from a sample
    app; ``"python3 -m tally"`` run as one-letter argvs, or a flat build list as one-letter
    steps; a working directory outside the repository; a timeout defaulted where the contract
    requires one. Each would surface as a failed start, not a refused declaration."""
    with pytest.raises(StartUndeclared, match=message) as refused:
        declared_start(declaration, configuration_revision=1)

    assert refused.value.reason is BlockedReason.NO_START_DECLARATION
