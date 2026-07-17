"""Evaluate a verification contract's structural criteria (SIP-0098 §6.2).

Bridges the contract's interface/implementation criteria to the SIP-0092 typed-check
evaluators (``acceptance_checks``): those are structural (AST / safelisted command) and
evaluated here. The behavioral checks (``tests_pass``, ``frontend_build``) exercise
runtime behavior and are run by the gate as subprocesses (pytest / vite), not here.

This module also owns the bare-skeleton classification so the gate and its tests share
one source of truth. Bare-skeleton semantics (SIP §6.2, refined 2026-07-17): a walking
skeleton compiles, builds, and boots by construction, so interface checks *and*
compile/build guards PASS on the bare skeleton. Only checks that exercise BEHAVIOR need
the fill and must NOT pass on the bare skeleton — today just ``tests_pass`` (probes join
in 98.4). Every structural check therefore passes on the bare skeleton; none is a
fill-behavior measure.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from squadops.cycles.acceptance_check_spec import CHECK_SPECS
from squadops.cycles.acceptance_checks import CheckOutcome, get_check

if TYPE_CHECKING:
    from squadops.cycles.verification_contract import VerificationContract

# endpoint_defined gates on ``stack == "fastapi"``; the fullstack backend's structural
# checks evaluate in that context.
FASTAPI_STACK = "fastapi"

# Behavioral checks that exercise runtime behavior — they need the fill and must NOT
# pass on the bare skeleton. Structural checks and the frontend_build guard pass on the
# walking skeleton by design, so they are not listed here.
FILL_BEHAVIOR_MEASURES = frozenset({"tests_pass"})

_RESERVED = frozenset({"check", "id", "requires"})


def is_structural(check_name: str) -> bool:
    """True when a check is evaluated by a SIP-0092 typed-check evaluator (vs a
    behavioral check the gate runs as a subprocess)."""
    return check_name in CHECK_SPECS


def evaluate_structural(
    criterion: dict[str, Any], workspace_root: Path, *, fill_file: str | None = None
) -> CheckOutcome:
    """Evaluate one structural criterion via its registered evaluator.

    Contract criteria omit ``file`` (it is the ``fill_files`` key), so inject it for the
    checks whose spec needs a file target. Drives the async evaluator to completion.
    """
    check_name = criterion["check"]
    if not is_structural(check_name):
        raise ValueError(f"{check_name!r} is not a structural check")
    params = {k: v for k, v in criterion.items() if k not in _RESERVED}
    spec = CHECK_SPECS[check_name]
    if fill_file is not None and ("file" in spec.required_params or "file" in spec.path_params):
        params.setdefault("file", fill_file)
    return asyncio.run(get_check(check_name).evaluate(params, workspace_root, stack=FASTAPI_STACK))


def structural_criteria(
    contract: VerificationContract,
) -> list[tuple[dict[str, Any], str | None]]:
    """``(criterion_dict, fill_file)`` for every structural criterion in the contract,
    in document order. ``fill_file`` is the fill-slot path for ``fill_files`` criteria,
    else ``None`` (behavioral-section structural criteria, of which there are none today).
    """
    out: list[tuple[dict[str, Any], str | None]] = []
    for ff in contract.fill_files:
        for crit in (*ff.interface, *ff.implementation):
            raw = crit.to_dict()
            if is_structural(raw["check"]):
                out.append((raw, ff.path))
    for crit in (*contract.behavioral.build, *contract.behavioral.suite.checks):
        raw = crit.to_dict()
        if is_structural(raw["check"]):
            out.append((raw, None))
    return out
