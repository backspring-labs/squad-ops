"""Shared typed-acceptance criterion evaluation seam (SIP-0092 M1.3, #419/#420).

One canonical view of a task's acceptance criteria for every consumer:
handler-side output validation (``handlers/cycle/base.py``, used by the dev
and builder seams) and executor-side patch verification (#389).

Criteria cross the A2A wire as plain dicts — ``TaskEnvelope.to_dict()`` uses
``dataclasses.asdict``, which recursively flattens ``TypedCheck`` — and the
agent side never rehydrates them. Any consumer filtering on
``isinstance(TypedCheck)`` alone therefore silently loses its typed contract
after dispatch (#420). ``split_acceptance_criteria`` owns that coercion in
one place so no seam can drift back into the wire-shape trap.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from squadops.cycles.acceptance_check_spec import CONFIG_OFF_SKIP_REASONS
from squadops.cycles.acceptance_checks import CheckOutcome, get_check
from squadops.cycles.implementation_plan import TypedCheck, _parse_acceptance_criteria
from squadops.cycles.verification_integrity import ResultStatus
from squadops.stacks.scaffold import check_stack_for

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SplitCriteria:
    """A mixed acceptance-criteria list, partitioned by evaluability.

    ``typed`` — machine-evaluable ``TypedCheck`` entries, including dict rows
    re-parsed from a deserialized envelope (#420).
    ``prose`` — informational strings; evidence-only, never block.
    ``unparseable`` — rows that are neither prose nor a parseable typed
    criterion. The parser enforces vocabulary at plan-authoring time, so an
    entry landing here indicates a transport-shape bug, not an authored
    contract; consumers decide their own severity (patch verification treats
    any as UNVERIFIABLE, handler validation discloses without blocking).
    """

    typed: tuple[TypedCheck, ...] = ()
    prose: tuple[str, ...] = ()
    unparseable: tuple[Any, ...] = ()


_SERIALIZED_ROW_KEYS = frozenset({"check", "params", "severity", "description", "id"})

# #503: check-stack derivation from the build profile. Live configs carry
# ``build_profile``/``development_profile`` but never a ``stack`` key, so every
# consumer that read ``resolved_config.get("stack")`` fed ``None`` into the
# evaluators and the AST checks (endpoint_defined, field_present, ...) silently
# skipped in every live cycle — while CI passed them via an explicit stack.
# Conservative mapping: only profiles deliberately verified against the check
# implementations; unmapped profiles keep today's skip behavior.
# #S1: sourced from the scaffold's stack registry rather than declared a second time here —
# "which stacks does this system know?" now has one answer. The lookup is still keyed on the
# BUILD PROFILE, which today is the same string as the stack name; a stack whose profile is
# named differently is exactly the assumption stack #2 will test, and it will fail visibly
# (checks skip) rather than silently mapping to the wrong evaluator vocabulary.


def resolve_check_stack(resolved_config: Mapping[str, Any]) -> str | None:
    """The stack passed to typed-check evaluators, derived in ONE place (#503).

    An explicit ``stack`` key wins (operator override / future configs); else the
    ``build_profile`` maps through the scaffold's stack registry; else ``None``
    (checks skip with ``unsupported_stack_or_syntax``, today's behavior).
    """

    explicit = resolved_config.get("stack")
    if explicit:
        return str(explicit)
    profile = resolved_config.get("build_profile")
    if profile:
        return check_stack_for(str(profile))
    return None


def _flatten_serialized_row(item: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a ``dataclasses.asdict``-shaped row to the flat authored shape.

    ``TaskEnvelope.to_dict()`` serializes ``TypedCheck`` with ``params``
    nested (the dataclass field), while the parser speaks the flat authored
    YAML shape (param keys inline, minus reserved keys). No check in
    ``CHECK_SPECS`` has a param literally named ``params`` and the key-set
    guard is exact, so a flat authored row can never be misread as serialized.
    """
    if isinstance(item.get("params"), Mapping) and set(item) <= _SERIALIZED_ROW_KEYS:
        flat = {k: v for k, v in item.items() if k != "params"}
        flat.update(item["params"])
        return flat
    return dict(item)


def split_acceptance_criteria(criteria: Iterable[Any] | None) -> SplitCriteria:
    """Partition a mixed/wire-shape criteria list into ``SplitCriteria``."""
    typed: list[TypedCheck] = []
    prose: list[str] = []
    unparseable: list[Any] = []
    for item in criteria or ():
        if isinstance(item, TypedCheck):
            typed.append(item)
        elif isinstance(item, str):
            prose.append(item)
        elif isinstance(item, Mapping):
            try:
                parsed = _parse_acceptance_criteria([_flatten_serialized_row(item)], task_index=-1)
            except ValueError:
                logger.warning("split_acceptance_criteria: unparseable criterion %r", item)
                unparseable.append(item)
                continue
            typed.extend(c for c in parsed if isinstance(c, TypedCheck))
        else:
            logger.warning(
                "split_acceptance_criteria: unsupported criterion type %s: %r",
                type(item).__name__,
                item,
            )
            unparseable.append(item)
    return SplitCriteria(tuple(typed), tuple(prose), tuple(unparseable))


async def evaluate_criterion(
    criterion: TypedCheck,
    workspace_root: Path,
    *,
    stack: str | None,
    typed_acceptance_enabled: bool,
    command_acceptance_enabled: bool,
) -> CheckOutcome:
    """Dispatch one typed criterion to its registered evaluator, honoring config gates."""
    if not typed_acceptance_enabled:
        return CheckOutcome.skipped(reason="typed_acceptance_disabled")
    if criterion.check == "command_exit_zero" and not command_acceptance_enabled:
        return CheckOutcome.skipped(reason="command_acceptance_checks_disabled")
    try:
        evaluator = get_check(criterion.check)
    except KeyError:
        # Should not happen — the parser already enforces vocabulary — but
        # treat as evaluator-error rather than crashing the cycle.
        return CheckOutcome.error(reason="no_evaluator_registered")
    return await evaluator.evaluate(criterion.params, workspace_root, stack=stack)


def acceptance_check_record(
    criterion: TypedCheck,
    outcome: CheckOutcome,
    check_index: int,
    authored: bool,
    subtask_index: Any,
) -> dict[str, Any]:
    """The evidence row for one evaluated criterion, its evidence-gap flag included (#423).

    ``authored`` says whether the author wrote the criterion, as opposed to the framework
    injecting it; ``subtask_index`` is the task's index in its implementation plan, or None.
    Moved from ``_CycleTaskHandler._evaluate_typed_acceptance`` (#1994).
    """
    # #423: an *authored* error-severity check that the evaluator
    # skipped for any reason other than deliberate config-off is an
    # evidence gap — the author asked for enforcement on a concrete
    # target and the evaluator declared it cannot deliver
    # (unsupported extension/stack, missing tooling). Distinct from
    # the benign classes: config-off skips, and framework-injected
    # checks (which target only files in their own family, #605).
    # A gap must never read `passed: true` — that is the false
    # green #423 measured (7 of 14 evaluations skipped-yet-passed,
    # the whole frontend contract surface unenforced) — but it also
    # must not mission a correction: no code repair can close an
    # evaluator limitation. It surfaces as unverified at the
    # SIP-0096 roll-up instead (see verification_normalize /
    # aggregate_verification).
    evidence_gap = (
        outcome.status == ResultStatus.SKIPPED
        and authored
        and criterion.severity == "error"
        and outcome.reason not in CONFIG_OFF_SKIP_REASONS
    )
    return {
        "check": f"acceptance:{criterion.check}",
        "severity": criterion.severity,
        "params": criterion.params,
        "description": criterion.description,
        "status": outcome.status,
        "actual": outcome.actual,
        "reason": outcome.reason,
        # `passed` flag for compatibility with the legacy
        # all-checks-pass aggregator: severity=error AND blocking
        # status, or an evidence-gap skip (#423), counts as
        # not-passed.
        "passed": not (criterion.severity == "error" and outcome.status in {"failed", "error"})
        and not evidence_gap,
        "evidence_gap": evidence_gap,
        # Issue #114: identity fields for downstream trigger
        # composition and per-cycle evaluation persistence.
        # task_index is None for tasks not driven by an
        # implementation_plan (legacy monolithic flow).
        "task_index": subtask_index,
        "check_index": check_index,
        # SIP-0098 98.3: the contract criterion id when this check was
        # resolved from a bind-mode criteria_ref; None for authored checks.
        "criterion_id": criterion.id or None,
    }


def apply_blocking_matrix(
    criterion: TypedCheck,
    outcome: CheckOutcome,
    missing: list[str],
    typed_error_counts: dict[str, int],
) -> bool:
    """RC-9's blocking matrix for one evaluated criterion, mutating ``missing`` and
    ``typed_error_counts`` in place (RC-9, RC-9a, RC-9b).

    Returns whether an evaluator error is past its second strike: it's counted and not fed
    back, and the caller escalates it. Moved from
    ``_CycleTaskHandler._evaluate_typed_acceptance`` (#1994).
    """
    # RC-9: severity AND status are independent. Only error+blocking missions.
    if criterion.severity != "error":
        return False
    if outcome.status == "failed":
        # RC-9a: app-incompleteness wording.
        label = criterion.description or criterion.check
        missing.append(f"acceptance:{label}")
    elif outcome.status == "error":
        fp = criterion.fingerprint()
        prior = typed_error_counts.get(fp, 0)
        if prior < 2:
            # RC-9a: evaluator-error wording, distinct from app-incomplete.
            missing.append(f"evaluator-error:{criterion.check}: {outcome.reason}")
        typed_error_counts[fp] = prior + 1
        return prior >= 2
    # status in {passed, skipped} never blocks.
    return False
