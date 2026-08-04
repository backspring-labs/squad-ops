"""Which plan validators are author-facing, and where each one is taught (#686).

Every deterministic plan validator encodes a rule, and until this module existed the
authors were never shown the rule — only the rejection. shk-1 measured the cost: its
first framing authored the fay-18 dual-claim shape with the contract, the manifest and
the typed-acceptance vocabulary all in its inputs, because the *plan-shape rules*
appeared in no authoring prompt. #673 caught it at the gate; the teaching arrived one
framing re-roll and 45 minutes late, and one more authoring defect would have exhausted
``framing_max_rerolls`` and hard-failed a cycle whose every mechanism worked. This is the
#629 pattern — the system holds the answer and never shows the author — applied to plan
authoring.

This module is the CLASSIFICATION, which is data. The rule prose lives in the managed
asset ``request.plan_authoring_rules_appendix`` (#448: prose in assets, Python renders
data only). ``tests/unit/cycles/test_plan_authoring_rules.py`` binds the two together:
every ``ImplementationPlan.validate_*`` method must appear in exactly one table here, and
every rule id in ``AUTHOR_FACING`` must appear in the asset. A new validator therefore
cannot ship without a decision about whether authors are told — the "any future validator
lands here the day it ships" requirement, enforced rather than remembered.
"""

from __future__ import annotations

# Validators whose rule is stated in the authoring-rules asset. The value is the rule id
# the asset carries, so the binding is checkable rather than a naming convention.
AUTHOR_FACING: dict[str, str] = {
    "validate_unique_expected_artifacts": "one-file-one-owner",
    "validate_expected_artifact_shapes": "artifacts-are-files",
    "validate_frozen_artifact_ownership": "no-frozen-claims",
    "validate_qa_artifact_ownership": "qa-owns-only-tests",
    "validate_module_existence": "imports-must-exist",
    "validate_criteria_scope": "regex-only-on-documents",
    "validate_command_checks": "commands-must-run-here",
    "validate_against_profile": "roles-must-exist",
}

# Validators an author is already taught by a different managed asset. Restating them
# would put the same rule in two places, free to drift; the value names the owning asset
# so the next reader can find it.
COVERED_ELSEWHERE: dict[str, str] = {
    # SIP-0098 §6.3 "bind, don't author" — rendered per-cycle with the actual criterion
    # ids, which is strictly more useful than a general statement of the rule.
    "validate_criteria_refs": "request.plan_bind_criteria_appendix",
}

# Validators with no author-facing rule: nothing the author writes can trip them, or the
# defect they catch is not expressible in the plan the author is composing.
NOT_AUTHOR_FACING: dict[str, str] = {}


def rule_ids() -> frozenset[str]:
    """Rule ids the authoring-rules asset must carry."""
    return frozenset(AUTHOR_FACING.values())


def classified_validators() -> frozenset[str]:
    """Every validator this module has an opinion about."""
    return frozenset(AUTHOR_FACING) | frozenset(COVERED_ELSEWHERE) | frozenset(NOT_AUTHOR_FACING)
