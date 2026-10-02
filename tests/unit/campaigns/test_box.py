"""The box's lease and its quietness (SIP-0109 §9.3; #1802).

The engine listings are shaped as the engines report them: Ollama's ``/api/ps`` gives a name and
a digest, a vLLM ``/v1/models`` listing a name only, and the deploy record declares the same
(``deploy_records.models``: ``{model, digest}``, the vLLM entry's digest null).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadops.campaigns.box import (
    BoxLease,
    EngineReading,
    LaunchRefusal,
    LeaseHolder,
    Model,
    box_quietness,
    launch_verdict,
)

NOW = datetime(2026, 10, 2, 15, 0, tzinfo=UTC)
#: dep_99414805cd5c's declared models, as its deploy record holds them.
DECLARED = (
    Model("Qwen/Qwen3.8-27B-FP8", None),
    Model("qwen2.5:7b", "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e"),
    Model("qwen3.8:27b", "22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643"),
)
SQUAD_MODEL = Model(
    "qwen3.8:27b", "22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643"
)
QUIET = box_quietness(DECLARED, [EngineReading("ollama", (SQUAD_MODEL,))])


@pytest.mark.parametrize(
    ("readings", "quiet", "reason"),
    [
        ([EngineReading("ollama", (SQUAD_MODEL,)), EngineReading("vllm", ())], True, None),
        # A vLLM listing carries no digest; the declared name is enough.
        ([EngineReading("vllm", (Model("Qwen/Qwen3.8-27B-FP8"),))], True, None),
        # A crew model left resident.
        (
            [EngineReading("ollama", (SQUAD_MODEL, Model("gpt-oss:120b", "abc123def4567")))],
            False,
            "gpt-oss:120b (abc123def456) loaded, which the deploy record does not declare",
        ),
        # The declared name at another digest is another model: a re-pulled tag.
        (
            [EngineReading("ollama", (Model("qwen3.8:27b", "ffff0000"),))],
            False,
            "qwen3.8:27b (ffff0000) loaded",
        ),
        # An engine that cannot be read fails closed.
        ([EngineReading("ollama", None, "connection refused")], False, "could not be read"),
    ],
    ids=["squad-only", "vllm-by-name", "crew-resident", "other-digest", "unreadable"],
)
def test_the_box_is_quiet_only_when_every_loaded_model_is_declared(readings, quiet, reason):
    """§9.3. Bugs caught: a crew model resident beside the squad's passing the check, a re-pulled
    tag under the declared name passing it, or an engine down reading as empty and so quiet."""
    result = box_quietness(DECLARED, readings)

    assert result.quiet is quiet
    if reason:
        assert any(reason in r for r in result.reasons), result.reasons


def test_every_reason_is_reported_not_the_first():
    result = box_quietness(
        DECLARED,
        [EngineReading("ollama", (Model("a:1"), Model("b:2"))), EngineReading("vllm", None, "503")],
    )
    assert len(result.reasons) == 3


@pytest.mark.parametrize(
    ("lease", "quietness", "refusal"),
    [
        (None, QUIET, None),
        (BoxLease(LeaseHolder.SQUAD, "squadops", NOW - timedelta(hours=1)), QUIET, None),
        (
            BoxLease(LeaseHolder.SUPERVISOR, "crew", NOW, NOW + timedelta(minutes=30), "cmp_1"),
            QUIET,
            LaunchRefusal.SUPERVISOR_HOLDS_THE_BOX,
        ),
        # Expired: the supervisor no longer holds it, but a resident crew model still refuses.
        (
            BoxLease(LeaseHolder.SUPERVISOR, "crew", NOW - timedelta(hours=1), NOW, "cmp_1"),
            box_quietness(DECLARED, [EngineReading("ollama", (Model("gpt-oss:120b"),))]),
            LaunchRefusal.BOX_NOT_QUIET,
        ),
        (
            BoxLease(LeaseHolder.SUPERVISOR, "crew", NOW - timedelta(hours=1), NOW, "cmp_1"),
            QUIET,
            None,
        ),
    ],
    ids=["no-lease", "squad", "supervisor", "expired-not-quiet", "expired-quiet"],
)
def test_a_launch_refuses_while_the_supervisor_holds_the_box_or_it_is_not_quiet(
    lease, quietness, refusal
):
    """§9.3 and §19 criterion 9. Bug caught: an expired lease reverting to the squad while the
    crew's model is still resident — the squad's cycle launching beside it."""
    assert launch_verdict(lease, quietness, NOW).refusal is refusal


@pytest.mark.parametrize(
    ("holder", "expires"),
    [(LeaseHolder.SUPERVISOR, None), (LeaseHolder.SQUAD, NOW)],
    ids=["supervisor-forever", "squad-expiring"],
)
def test_only_a_supervisor_lease_expires_and_it_always_does(holder, expires):
    """Bug caught: a supervisor lease with no expiry — a crashed supervisor holding the box."""
    with pytest.raises(ValueError, match="carries an expiry"):
        BoxLease(holder, "x", NOW, expires)
