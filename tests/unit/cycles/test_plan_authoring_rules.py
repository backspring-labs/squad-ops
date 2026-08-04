"""#686 — the plan-shape rules the validators enforce reach the plan authors.

shk-1 (cyc_b03d203df3f2) authored the #673 dual-claim shape on its first framing with
the contract, the interface manifest and the typed-acceptance vocabulary all present in
its inputs, because the plan-shape *rules* appeared in no authoring prompt. The gate
caught it; the teaching arrived a framing re-roll late, and one more authoring defect
would have exhausted ``framing_max_rerolls``.

These bind three surfaces that must not drift apart: the validator family, the
classification table, and the managed asset the authors actually read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.plan_authoring_rules import (
    AUTHOR_FACING,
    COVERED_ELSEWHERE,
    NOT_AUTHOR_FACING,
    classified_validators,
    rule_ids,
)

pytestmark = [pytest.mark.domain_contracts]

_TEMPLATES = (
    Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts" / "request_templates"
)
_ASSET = _TEMPLATES / "request.plan_authoring_rules_appendix.md"


def _validator_names() -> set[str]:
    return {n for n in dir(ImplementationPlan) if n.startswith("validate_")}


def test_every_validator_is_classified_exactly_once():
    """The enforcement behind "any future validator lands here the day it ships". A new
    validator with no entry fails here, so shipping one forces a decision about whether
    the authors are told — rather than repeating shk-1, where the rule existed and the
    author never saw it."""
    validators = _validator_names()
    assert validators, "the validator family must be discoverable by name"

    unclassified = validators - classified_validators()
    assert not unclassified, (
        f"new plan validator(s) {sorted(unclassified)} are unclassified — add each to "
        "AUTHOR_FACING (and state its rule in the asset), COVERED_ELSEWHERE, or "
        "NOT_AUTHOR_FACING in squadops.cycles.plan_authoring_rules"
    )
    stale = classified_validators() - validators
    assert not stale, f"classified validator(s) {sorted(stale)} no longer exist"

    tables = [set(AUTHOR_FACING), set(COVERED_ELSEWHERE), set(NOT_AUTHOR_FACING)]
    for i, a in enumerate(tables):
        for b in tables[i + 1 :]:
            assert not (a & b), f"validator classified twice: {sorted(a & b)}"


def test_every_author_facing_rule_is_stated_in_the_asset():
    """A rule id in the table with no prose in the asset is the #686 defect itself —
    the system knows the rule and the author is not told."""
    asset = _ASSET.read_text(encoding="utf-8")
    missing = sorted(rid for rid in rule_ids() if f"**{rid}**" not in asset)
    assert not missing, (
        f"rule id(s) {missing} are classified author-facing but absent from the asset"
    )


def test_the_asset_states_no_rule_the_table_does_not_claim():
    """The reverse drift: prose for a rule no validator enforces teaches authors to obey
    something the system does not check, which is worse than silence — it spends author
    attention and cannot be relied on."""
    import re

    stated = set(re.findall(r"^\*\*([a-z0-9-]+)\*\*", _ASSET.read_text(encoding="utf-8"), re.M))
    assert stated == rule_ids()


def test_covered_elsewhere_names_an_asset_that_exists():
    """A pointer to a nonexistent asset is an unverifiable excuse for omitting a rule."""
    for validator, template_id in COVERED_ELSEWHERE.items():
        assert (_TEMPLATES / f"{template_id}.md").is_file(), (
            f"{validator} is recorded as covered by {template_id}, which does not exist"
        )


def test_the_asset_teaches_the_shk1_defect_and_its_legitimate_alternative():
    """The specific shape that cost shk-1 a re-roll: two tasks claiming one file. Stating
    the ban without the verification-only alternative would push authors toward dropping
    the verification task instead of declaring an empty artifact list."""
    asset = _ASSET.read_text(encoding="utf-8")
    assert "one-file-one-owner" in asset
    assert "expected_artifacts: []" in asset
    assert "verif" in asset.lower()
