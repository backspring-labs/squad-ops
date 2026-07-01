"""Unit tests for the validated-fullstack cycle request profile (#279).

Bug this guards: the profile must COMPOSE both quality levers — `validation`'s
instrumentation AND the stack-aware builder path. If either silently drops (a
missing `dev_capability`, instrumentation flags defaulting off, or the 2-run
sequence collapsing to single-run), the profile degrades to a lean build and the
#279 quality gain — a runnable app with a correction/typed-check trail — is lost.
"""

from __future__ import annotations

import pytest

from squadops.contracts.cycle_request_profiles import list_profiles, load_profile
from squadops.contracts.cycle_request_profiles.schema import CycleRequestProfile

pytestmark = [pytest.mark.domain_contracts]


def test_profile_loads_and_is_listed():
    profile = load_profile("validated-fullstack")
    assert isinstance(profile, CycleRequestProfile)
    assert profile.name == "validated-fullstack"
    assert "validated-fullstack" in list_profiles()


def test_composes_stack_aware_builder_path():
    """Builder + stack lever: fullstack dev capability + builder-routed build."""
    defaults = load_profile("validated-fullstack").defaults
    assert defaults["dev_capability"] == "fullstack_fastapi_react"
    assert defaults["build_profile"] == "fullstack_fastapi_react"
    # build_tasks: true routes through builder.assemble when the squad has a builder
    assert defaults["build_tasks"] is True


def test_composes_validation_instrumentation():
    """Instrumentation lever: the flags `validation` carries — not schema defaults-off."""
    defaults = load_profile("validated-fullstack").defaults
    assert defaults["output_validation"] is True
    assert defaults["typed_acceptance"] is True
    assert defaults["command_acceptance_checks"] is True
    assert defaults["implementation_plan"] is True
    assert defaults["max_self_eval_passes"] == 2
    assert defaults["max_correction_attempts"] == 3


def test_two_run_framing_then_implementation_sequence():
    """2-run sequence with the gate on framing (clean checkpoint + resumability)."""
    defaults = load_profile("validated-fullstack").defaults
    sequence = defaults["workload_sequence"]
    assert [step["type"] for step in sequence] == ["framing", "implementation"]
    assert sequence[0]["gate"] == "progress_plan_review"
    assert sequence[1]["gate"] is None
