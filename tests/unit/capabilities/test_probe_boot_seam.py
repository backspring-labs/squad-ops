"""Which app the probe runner boots is the stack's declaration (#822).

`run_probes` took `profile: ExecutionProfile = DEFAULT_PROFILE` as a default argument and
**no caller overrode it**, so every stack was booted with `python -m uvicorn
backend.main:app`. The second stack this release adds is Node/TypeScript.

This is loud rather than silent — a Node app does not start under uvicorn, so boot fails and
`ProbeOutcome.skipped` means not-executed, which SIP-0096 declines to credit — and that is
why it is scope rather than the emergency #818 was. But "boot the wrong thing and read the
failure" is a diagnosis someone has to reconstruct, and a declared refusal is one they are
handed.

Deliberately **not** derived from the sandbox `EnvironmentContract`, which also carries a
`START_APPLICATION` command: that argv runs inside the sandbox container against
`.sandbox-venv`, while probes run in the qa container against a fresh temp dir on
`sys.executable`. Two execution contexts, so the interpreter is context-specific and only
the launcher and entry point are stack-specific.

Bug classes guarded:

- **a second stack's probes booting the first stack's app** — the defect;
- the fix changing behavior for callers that cannot name a stack, which is every caller that
  exists today: this must be inert for them or it is a regression in banked evidence;
- the resolution reaching for the *evaluator* stack vocabulary (`"fastapi"`) instead of the
  scaffold one (`"fullstack_fastapi_react"`) — two names, and S3 still owes the
  reconciliation;
- a config naming an unknown build profile resolving to something rather than nothing;
- **the refusal escalating to an exception.** `qa_test` states probes are "additive evidence
  only … a failed probe surfaces at the run verdict/rollup, not as a task failure here", so
  raising here would convert missing evidence into a dead task;
- a stack registered in one seam and forgotten in another — the S1 failure recurring across
  registries instead of within one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities import scaffold
from squadops.capabilities.handlers import probe_runner as pr
from squadops.capabilities.handlers.probe_runner import (
    DEFAULT_PROFILE,
    ExecutionProfile,
    ProbeOutcome,
    profile_for_stack,
    run_probes,
)
from squadops.capabilities.scaffold import ScaffoldStack, scaffold_stack_for
from squadops.cycles.verification_contract import Probe

pytestmark = [pytest.mark.domain_capabilities]


def _probe(pid: str = "vc-probe-runs") -> Probe:
    return Probe.from_dict(
        {"id": pid, "subject": "backend", "request": {"method": "GET", "path": "/runs"}}
    )


def _register(monkeypatch, *, probe_profile: str) -> None:
    monkeypatch.setitem(
        scaffold._STACKS,
        "node_ts",
        ScaffoldStack(
            name="node_ts",
            expand=lambda m: [],
            fill_slots=lambda m: ("src/routes.ts",),
            criteria_pack="node_ts",
            probe_profile=probe_profile,
        ),
    )


def _capture_boot(monkeypatch) -> list[ExecutionProfile]:
    """Intercept the boot so resolution can be asserted without standing a server up."""
    seen: list[ExecutionProfile] = []

    def _fake(workspace, probes, profile):
        seen.append(profile)
        return [ProbeOutcome(p.id, "passed") for p in probes]

    monkeypatch.setattr(pr, "_run_backend_probes", _fake)
    return seen


# --------------------------------------------------------------------------- #
# The defect
# --------------------------------------------------------------------------- #


def test_a_stack_with_no_probe_profile_reports_not_executed_instead_of_booting_fastapi(
    monkeypatch, tmp_path: Path
):
    """The bug. Before this, `node_ts` probes ran `uvicorn backend.main:app` — against a
    workspace with no Python app in it — and the boot failure was the only clue."""
    _register(monkeypatch, probe_profile="")
    seen = _capture_boot(monkeypatch)

    outcomes = run_probes(tmp_path, [_probe()], stack="node_ts")

    assert [(o.id, o.status) for o in outcomes] == [("vc-probe-runs", "skipped")]
    assert "declares no probe profile" in (outcomes[0].reason or "")
    assert seen == [], "nothing may be booted for a stack that has not said how"


def test_the_refusal_does_not_raise(monkeypatch, tmp_path: Path):
    """`qa_test` treats probes as additive evidence that "surfaces at the run verdict/rollup,
    not as a task failure here". Raising would turn missing evidence into a dead QA task —
    which is why this refuses differently from the emitter's in #818."""
    _register(monkeypatch, probe_profile="")

    outcomes = run_probes(tmp_path, [_probe()], stack="node_ts")

    assert len(outcomes) == 1


def test_a_stack_boots_with_its_own_launcher(monkeypatch, tmp_path: Path):
    """The point of the seam: the launcher and entry point are the stack's, not FastAPI's."""
    _register(monkeypatch, probe_profile="node_server")
    monkeypatch.setitem(
        pr._PROFILES,
        "node_server",
        ExecutionProfile(boot_argv=("node", "dist/server.js", "--port", "{port}")),
    )
    seen = _capture_boot(monkeypatch)

    outcomes = run_probes(tmp_path, [_probe()], stack="node_ts")

    assert seen[0].boot_argv == ("node", "dist/server.js", "--port", "{port}")
    assert "uvicorn" not in " ".join(seen[0].boot_argv)
    assert [o.status for o in outcomes] == ["passed"]


# --------------------------------------------------------------------------- #
# Inertness for everything that exists today
# --------------------------------------------------------------------------- #


def test_a_caller_that_names_no_stack_keeps_the_historical_profile(monkeypatch, tmp_path: Path):
    """Every caller before this change passed no stack. If that path stopped booting, the
    behavioral half of every contract would quietly stop being evidence."""
    seen = _capture_boot(monkeypatch)

    run_probes(tmp_path, [_probe()])

    assert seen == [DEFAULT_PROFILE]


def test_an_explicit_profile_still_wins(monkeypatch, tmp_path: Path):
    """The existing test seam — `test_probe_runner` passes fast-fail and crashing profiles
    to exercise boot handling, and must keep working."""
    _register(monkeypatch, probe_profile="node_server")
    explicit = ExecutionProfile(boot_argv=("true",))
    seen = _capture_boot(monkeypatch)

    run_probes(tmp_path, [_probe()], profile=explicit, stack="node_ts")

    assert seen == [explicit]


def test_the_reference_stack_still_boots_uvicorn():
    """Named rather than assumed: `fullstack_fastapi_react` must keep resolving to the
    interpreter-relative uvicorn boot the qa container's installed packages support."""
    profile = profile_for_stack("fullstack_fastapi_react")

    assert profile is not None
    assert "uvicorn" in profile.boot_argv
    assert "backend.main:app" in profile.boot_argv
    assert profile.boot_argv[0].endswith("python") or "python" in profile.boot_argv[0]


# --------------------------------------------------------------------------- #
# Resolving the stack from config
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({"build_profile": "fullstack_fastapi_react"}, "fullstack_fastapi_react"),
        ({"build_profile": "not_a_stack"}, ""),
        ({"build_profile": ""}, ""),
        ({}, ""),
        (None, ""),
    ],
)
def test_the_scaffold_stack_is_resolved_from_build_profile(config, expected):
    """An unknown profile must resolve to nothing, so the caller falls back to the historical
    default rather than skipping — a config typo should not silently delete probe evidence."""
    assert scaffold_stack_for(config) == expected


def test_the_scaffold_vocabulary_is_not_the_evaluator_vocabulary():
    """`resolve_check_stack` answers `"fastapi"`; boot profiles are keyed on the scaffold
    stack. Collapsing the two would key a lookup on a name the registry does not hold —
    the drift S3 still owes a reconciliation for."""
    from squadops.cycles.acceptance_evaluation import resolve_check_stack

    config = {"build_profile": "fullstack_fastapi_react"}

    assert resolve_check_stack(config) == "fastapi"
    assert scaffold_stack_for(config) == "fullstack_fastapi_react"
    assert profile_for_stack("fastapi") is None


# --------------------------------------------------------------------------- #
# The seams cannot drift apart
# --------------------------------------------------------------------------- #


def test_every_registered_stack_can_be_built_verified_and_booted():
    """S1's real lesson was not "one registry" — it was that forgetting must be an error
    rather than a plausible wrong answer. A stack now appears in three, so this is where
    forgetting any one of them fails, at build time rather than mid-cycle."""
    from squadops.sandbox.environment import get_environment_contract

    for name, stack in scaffold._STACKS.items():
        assert stack.probe_profile, f"stack {name!r} declares no probe_profile"
        assert stack.probe_profile in pr._PROFILES, (
            f"stack {name!r} names probe profile {stack.probe_profile!r}, which is not registered"
        )
        get_environment_contract(name)  # raises if the stack has no environment contract
