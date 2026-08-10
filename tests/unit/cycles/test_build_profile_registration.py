"""A registered stack must have a build profile, and its absence must be loud (#838).

VS (`cyc_afa934886acd`) found this by its absence. `_seed_skeleton_artifacts` resolves
`get_profile(manifest.stack)`, which raises for a name `BUILD_PROFILES` does not hold — and
the call site wrapped the whole thing in one broad `except Exception` that returned `[]` with
a warning.

`nextjs_ts` was registered in five per-stack registries and absent from this sixth one. So
**a correct `nextjs_ts` manifest would have been silently unscaffolded**, and the wrong
manifest — the one declaring `fullstack_fastapi_react` — was the only one that worked. The
inversion is the point: the failing path was the correct one.

Bug classes guarded:

- **a registered stack missing its build profile**, which is the two registries disagreeing;
- **that disagreement being swallowed.** An unscaffolded cycle has no contract, no fill slots
  and no frozen files — it is not a degraded run, it is a run whose entire verification story
  is absent, and it would report `completed`;
- a registration failure and an expansion failure sharing one diagnosis, which is the
  conflation #827 separated for the probe path;
- **expansion failures becoming fatal.** The tolerant path predates SIP-0099 and is what a
  non-scaffolded run falls back to; making it loud would fail cycles that work today.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadops.capabilities import scaffold
from squadops.capabilities.handlers.build_profiles import BUILD_PROFILES
from squadops.capabilities.scaffold import InterfaceManifest, ScaffoldStack

pytestmark = [pytest.mark.domain_contracts]

_REFERENCE = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
).read_text(encoding="utf-8")


def _manifest(stack: str) -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_REFERENCE.replace("fullstack_fastapi_react", stack))


def _executor():
    from adapters.cycles.dispatched_flow_executor import DispatchedFlowExecutor

    return DispatchedFlowExecutor(artifact_vault=AsyncMock())


# --------------------------------------------------------------------------- #
# The registries must agree
# --------------------------------------------------------------------------- #


def test_every_scaffoldable_stack_has_a_build_profile():
    """The sixth binding. Five registries agreed about `nextjs_ts` and this one did not, which
    is precisely how a plausible wrong answer beat the correct one."""
    for name in scaffold._STACKS:
        assert name in BUILD_PROFILES, (
            f"stack {name!r} is registered as scaffoldable but has no build profile — "
            f"a correct manifest for it would be silently unscaffolded"
        )


def test_every_build_profile_narrative_is_non_empty():
    """`_narrative` raises at import for a missing file, so this asserts the weaker thing that
    can still go wrong: a file that exists and says nothing."""
    for name, profile in BUILD_PROFILES.items():
        assert profile.system_prompt_template.strip(), f"{name} has an empty narrative"


# --------------------------------------------------------------------------- #
# The absence must be loud
# --------------------------------------------------------------------------- #


async def test_a_registered_stack_with_no_build_profile_raises(monkeypatch, caplog):
    """The inversion VS found. Swallowing this left the *correct* manifest as the failing one,
    and an unscaffolded cycle would have gone on to report `completed` with no contract, no
    fill slots and no frozen files."""
    monkeypatch.setitem(
        scaffold._STACKS,
        "unprofiled_stack",
        ScaffoldStack(name="unprofiled_stack", expand=lambda m: [], fill_slots=lambda m: ()),
    )

    with pytest.raises(ValueError, match="Unknown build profile"):
        await _executor()._seed_skeleton_artifacts(
            _manifest("unprofiled_stack"), MagicMock(), "run_x"
        )

    assert any("registries disagree" in r.message for r in caplog.records)


async def test_an_unregistered_stack_is_still_skipped_quietly(monkeypatch):
    """`is_scaffoldable_stack` gates first: a manifest naming a stack this system does not
    know is not a registration error, and the run proceeds unscaffolded as it always has."""
    result = await _executor()._seed_skeleton_artifacts(
        _manifest("some_stack_we_never_registered"), MagicMock(), "run_x"
    )

    assert result == []


async def test_an_expansion_failure_stays_tolerant(monkeypatch):
    """The distinction that matters: a properly registered stack whose expansion raises falls
    back to the non-scaffolded path, which is the pre-SIP-0099 behavior. Making this loud too
    would fail cycles that work today."""

    def _boom(_manifest):
        raise RuntimeError("expander blew up")

    # BuildProfile is frozen and its expander import is function-local, so the seam is the
    # scaffold's `expand` itself — resolved fresh on every call.
    monkeypatch.setattr("squadops.capabilities.scaffold.expand", _boom, raising=True)

    result = await _executor()._seed_skeleton_artifacts(
        _manifest("fullstack_fastapi_react"), MagicMock(), "run_x"
    )

    assert result == []
