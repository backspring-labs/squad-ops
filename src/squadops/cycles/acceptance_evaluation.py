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

from squadops.cycles.acceptance_checks import CheckOutcome, get_check
from squadops.cycles.implementation_plan import TypedCheck, _parse_acceptance_criteria

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


_SERIALIZED_ROW_KEYS = frozenset({"check", "params", "severity", "description"})


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
