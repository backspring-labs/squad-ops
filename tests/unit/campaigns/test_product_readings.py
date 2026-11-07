"""#2938: a product's declared reading of an accepted increment, kept as evidence (SIP-0109 §24dj).

The reading runs in the same real sandbox as ``test_runner_acceptance_sandbox``, and the wiring test
enters at ``evaluate_product_increment``, where a repository-backed increment is judged.

Bugs caught:
- the reading run on the head, not the candidate, so it reports what the increment replaced;
- a reading that crashes, or prints nothing usable, failing the increment it only measures;
- a configuration's readings lost on its way through the stored document;
- a reading kept on the run but never reaching the digest or the gate, where anyone would read it.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from squadops.campaigns.backlog import latest_readings
from squadops.campaigns.evidence import reading_line
from squadops.campaigns.models import ControlLogEntry, ControlOperation, ControlOutcome
from squadops.campaigns.runner_acceptance import SandboxTree
from squadops.execution import product_acceptance
from squadops.projects.development_configuration import (
    Check,
    Commands,
    ConfigurationInvalid,
    Reading,
    _commands,
    _commands_document,
)
from tests.unit.campaigns.test_runner_acceptance_sandbox import (
    HEAD,
    _runs,
    sandbox,  # noqa: F401 - the fixture
)

PY = sys.executable
_SHOW = "import json, pathlib; print('noise'); print(json.dumps({'said': pathlib.Path('said').read_text()}))"
_TREE = SandboxTree({**HEAD, "said": b"head"}, changes={"said": b"candidate"})


async def test_a_reading_reads_the_candidate_and_keeps_its_last_line(sandbox):  # noqa: F811
    record = await _runs(sandbox).read("play", (PY, "-c", _SHOW), _TREE)

    assert record["reading"] == {"said": "candidate"}
    assert record["exit_code"] == 0
    assert "error" not in record


@pytest.mark.parametrize(
    ("code", "exit_code", "error"),
    [
        ("print('not json')", 0, "its last line isn't JSON: not json"),
        ("print('[1, 2]')", 0, "its last line isn't a JSON object"),
        ("pass", 0, "the reading printed nothing"),
        ("import sys; print('{'); sys.exit(3)", 3, "its last line isn't JSON: {"),
    ],
    ids=["prose", "a-list", "silence", "a-crash"],
)
async def test_a_reading_with_no_result_says_why_and_raises_nothing(
    sandbox,  # noqa: F811
    code,
    exit_code,
    error,
):
    record = await _runs(sandbox).read("play", (PY, "-c", code), _TREE)

    assert (record["reading"], record["exit_code"], record["error"]) == (None, exit_code, error)


async def test_a_nonzero_exit_with_a_result_is_still_reported(sandbox):  # noqa: F811
    code = "import sys; print('{\"wins\": 0}'); sys.exit(1)"

    record = await _runs(sandbox).read("play", (PY, "-c", code), _TREE)

    assert (record["reading"], record["exit_code"]) == ({"wins": 0}, 1)


async def test_a_sandbox_that_fails_becomes_the_records_error_and_never_an_exception(sandbox):  # noqa: F811
    runs = _runs(sandbox)
    runs.sandbox.seed_workspace = AsyncMock(side_effect=OSError("disk full"))

    record = await runs.read("play", (PY, "-c", "pass"), _TREE)

    assert record == {
        "id": "play",
        "argv": [PY, "-c", "pass"],
        "reading": None,
        "error": "OSError: disk full",
    }


def _delivery():
    return SimpleNamespace(
        head=SimpleNamespace(files={**HEAD, "said": b"head"}, executable=frozenset()),
        changes={"said": b"candidate"},
        verification=SimpleNamespace(candidate_revision_id=None),
    )


def _cycle():
    return SimpleNamespace(
        cycle_id="cyc_t",
        project_id="prj_t",
        source_context=SimpleNamespace(
            development_baseline_commit="c" * 40, development_configuration_revision=1
        ),
        resolved_config=lambda: {},
    )


async def _evaluated(sandbox, monkeypatch, readings):  # noqa: F811
    """Through ``evaluate_product_increment``: everything before the reading is the increment's
    own business, so its inputs are stubbed and its verdict is a marker the reading can't touch."""
    mod = product_acceptance
    inputs = {
        "increment_id": "inc",
        "increment_criterion_files": [],
        "increment_replaced_criteria": [],
        "increment_retired_criteria": [],
        "increment_frozen_criteria": [],
    }
    monkeypatch.setattr(mod, "approved_change_request", AsyncMock(return_value={}))
    monkeypatch.setattr(mod, "increment_evaluation_inputs", lambda *_a: inputs)
    monkeypatch.setattr(mod, "frozen_bundle_contents", AsyncMock(return_value={}))
    monkeypatch.setattr(mod, "frozen_criteria_from", lambda *_a: [])
    monkeypatch.setattr(mod, "requested_routes", lambda _c: ())
    monkeypatch.setattr(mod, "routes_blocked", lambda *_a: SimpleNamespace(results=(), record=[]))
    monkeypatch.setattr(mod, "evaluate_on_runner", AsyncMock(return_value=("ev", [])))
    monkeypatch.setattr(mod, "evaluation_document", lambda *_a, **_k: {"verdict": "accepted"})
    stored = {}

    class _Vault:
        async def store(self, ref, content):
            stored["document"] = content

    commands = Commands(".", (Check("t", ("true",)),), None, readings=readings)
    await mod.evaluate_product_increment(
        _cycle(),
        "run_t",
        _delivery(),
        vault=_Vault(),
        projects=SimpleNamespace(
            get_development_configuration=AsyncMock(
                return_value=SimpleNamespace(commands=commands)
            ),
        ),
        sandbox=sandbox,
        route_renderer=None,
        read_profile=AsyncMock(return_value=SimpleNamespace(client_routes=())),
    )
    import json

    return json.loads(stored["document"])


async def test_an_increments_evaluation_carries_the_reading_of_its_candidate(
    sandbox,  # noqa: F811
    monkeypatch,
):
    document = await _evaluated(sandbox, monkeypatch, (Reading("play", (PY, "-c", _SHOW)),))

    assert [r["reading"] for r in document["readings"]] == [{"said": "candidate"}]


async def test_a_reading_that_fails_leaves_the_verdict_alone(sandbox, monkeypatch):  # noqa: F811
    document = await _evaluated(sandbox, monkeypatch, (Reading("play", (PY, "-c", "pass")),))

    assert document["verdict"] == "accepted"
    assert document["readings"][0]["error"] == "the reading printed nothing"


async def test_a_product_with_no_reading_writes_the_document_it_always_did(
    sandbox,  # noqa: F811
    monkeypatch,
):
    assert "readings" not in await _evaluated(sandbox, monkeypatch, ())


def test_a_configurations_readings_survive_its_stored_document():
    doc = {
        "checks": [{"id": "t", "argv": ["true"]}],
        "readings": [{"id": "play", "argv": ["node", "play.mjs"]}],
    }

    commands = _commands(doc, "technical.commands")

    assert commands.readings == (Reading("play", ("node", "play.mjs")),)
    assert _commands_document(commands)["readings"] == doc["readings"]


def test_a_configuration_with_no_reading_keeps_its_document_and_so_its_digest():
    commands = _commands({"checks": [{"id": "t", "argv": ["true"]}]}, "technical.commands")

    assert "readings" not in _commands_document(commands)


@pytest.mark.parametrize(
    ("readings", "field"),
    [
        ("play", "technical.commands.readings"),
        ([{"argv": ["x"]}], "technical.commands.readings[0]"),
        ([{"id": "a", "argv": []}], "technical.commands.readings[0].argv"),
        ([{"id": "a", "argv": ["x"]}, {"id": "a", "argv": ["y"]}], "technical.commands.readings"),
        ([{"id": "t", "argv": ["x"]}], "technical.commands.readings"),
    ],
    ids=["not-a-list", "no-id", "no-argv", "a-repeat", "a-checks-id"],
)
def test_a_malformed_reading_is_refused_by_its_field(readings, field):
    doc = {"checks": [{"id": "t", "argv": ["true"]}], "readings": readings}

    with pytest.raises(ConfigurationInvalid) as refused:
        _commands(doc, "technical.commands")

    assert refused.value.field == field


def _promotion(seq, readings=None, outcome=ControlOutcome.APPLIED):
    return ControlLogEntry(
        entry_id=f"ctl_{seq}",
        campaign_id="cmp_t",
        seq=seq,
        operation=ControlOperation.PROMOTE,
        actor="squadops",
        actor_role="completion",
        reason="r",
        target=f"cyc_{seq}",
        idempotency_key=f"promote:{seq}",
        request_hash="h",
        binding={"readings": readings} if readings else {},
        outcome=outcome,
        refusal=None,
        prior_state="building",
        next_state="building",
        committed_at=datetime.now(UTC),
    )


def test_the_gate_reads_the_latest_promotion_that_carries_a_reading():
    first, second = (
        [{"id": "play", "reading": {"wins": 0}}],
        [{"id": "play", "reading": {"wins": 1}}],
    )
    refused = _promotion(4, [{"id": "play", "reading": {"wins": 9}}], ControlOutcome.REFUSED)

    log = [_promotion(1, first), _promotion(2, second), _promotion(3), refused]

    assert latest_readings(log) == second
    assert latest_readings([_promotion(1)]) == []


@pytest.mark.parametrize(
    ("record", "line"),
    [
        ({"reading": {"wins": 0}}, '{"wins": 0}'),
        ({"reading": None, "error": "the reading printed nothing"},
         "no reading (the reading printed nothing)"),
        ({"reading": None}, "no reading (none recorded)"),
    ],
)  # fmt: skip
def test_the_digest_reports_a_reading_as_read_or_says_why_not(record, line):
    assert reading_line(record) == line
