"""The authoring replay envelope (SIP-0110 §0.11; #2105): what one authoring task was given,
captured before its first model call, as the replay will read it back."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from squadops.memory.authoring_envelope import (
    AuthoringReplayEnvelope,
    AuthoringSeam,
    capture_envelope,
    envelope_id,
    json_safe,
)

pytestmark = [pytest.mark.domain_memory]


def _capture(**overrides) -> AuthoringReplayEnvelope:
    fields = {
        "seam": AuthoringSeam.PROPOSAL_WRITING,
        "task_type": "strategy.propose_increment",
        "task_id": "task-run_1-m000-strategy.propose_increment",
        "cycle_id": "cyc_1",
        "project_id": "group_run",
        "agent_id": "nat",
        "role": "strat",
        "handler_name": "strategy_propose_increment_handler",
        "captured_at": "2026-10-08T02:00:00+00:00",
        "messages": [("system", "You are the strategy role."), ("user", "Propose the next one.")],
        "chat_kwargs": {"model": "qwen", "temperature": 0.2},
        "inputs": {"prd": "## Tier 1", "resolved_config": {"campaign_proposal": {"version": 1}}},
    }
    fields.update(overrides)
    return capture_envelope(**fields)


def test_an_envelope_survives_the_wire_and_the_store_unchanged():
    """Bug caught: a field the replay reads (the cutoff, the inputs, the settings) lost or
    re-typed between the agent's capture, the task result's JSON and the registry's row."""
    captured = _capture()

    over_the_wire = json.loads(json.dumps(captured.to_dict()))

    assert AuthoringReplayEnvelope.from_dict(over_the_wire) == captured
    assert over_the_wire["inputs"]["resolved_config"] == {"campaign_proposal": {"version": 1}}
    assert over_the_wire["messages"][1] == {"role": "user", "content": "Propose the next one."}


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(
            lambda d: d["messages"][1].update(content="Propose a different one."), id="text"
        ),
        pytest.param(lambda d: d["messages"].reverse(), id="order"),
        pytest.param(lambda d: d["messages"][0].update(role="user"), id="role"),
    ],
)
def test_an_envelope_whose_messages_no_longer_match_their_hash_is_refused(tamper):
    """Bug caught: a replay run against an edited prompt, read as the one the model was sent."""
    data = _capture().to_dict()
    tamper(data)

    with pytest.raises(ValueError, match="do not match their hash"):
        AuthoringReplayEnvelope.from_dict(data)


def test_an_envelope_of_an_unknown_schema_is_refused():
    """Bug caught: a reader replaying fields whose meaning changed under it."""
    data = {**_capture().to_dict(), "schema_version": 99}

    with pytest.raises(ValueError, match="schema 99"):
        AuthoringReplayEnvelope.from_dict(data)


def test_an_input_json_cannot_carry_is_named_never_stringified():
    """Bug caught: a port or a vault handle stored as its repr, so a replay re-authors from a
    string that only looks like the input it was given."""

    class Vault:  # an object the agent may add to a task's inputs
        pass

    safe, dropped = json_safe({"prd": "text", "artifact_vault": Vault(), "refs": [1, Vault()]})

    assert safe == {"prd": "text", "artifact_vault": None, "refs": [1, None]}
    assert dropped == ["artifact_vault", "refs[1]"]
    envelope = _capture(inputs={"artifact_vault": Vault()})
    assert envelope.inputs_not_captured == ("artifact_vault",)


def test_a_duplicate_delivery_is_one_capture_and_a_retry_is_another():
    """Bug caught: a redelivered reply counted twice, or a retried task's new authoring
    overwriting the first one's record."""
    first = _capture().to_dict()
    redelivered = json.loads(json.dumps(first))
    retried = _capture(captured_at="2026-10-08T02:05:00+00:00").to_dict()

    assert envelope_id(first) == envelope_id(redelivered)
    assert envelope_id(first) != envelope_id(retried)


def test_the_migrations_seam_check_is_the_enums_values():
    """Bug caught: a seam added to the enum that the table refuses, so its envelopes are lost at
    the insert while the agent reports capturing them."""
    sql = (
        Path(__file__).resolve().parents[3]
        / "infra"
        / "migrations"
        / "1700_authoring_envelopes.sql"
    ).read_text()
    check = re.search(r"CHECK \(seam IN \(([^)]*)\)\)", sql)

    assert check is not None
    assert sorted(re.findall(r"'([^']+)'", check.group(1))) == sorted(
        s.value for s in AuthoringSeam
    )
