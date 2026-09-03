"""Make a cycle fail on purpose, deterministically, on the roll's own path (#1251).

**Why this exists.** Every verification-set prediction about the correction loop — which
role a failure routes to, whether a repair is retested, whether a round is refunded — fires
only when a roll happens to break in the right way. A green roll leaves the prediction
unexercised, and three consecutive lines carried the remedy as plan text without filing it:
the 1.6.5 plan's fault-injection arm, the 1.6.6 and 1.7.1 plans' "still the owner's" lines,
and the 1.7.1 plan's promise of "one fault-injected diagnostic per item". At
pre-registration time those diagnostics became in-container replays of the deployed
evaluators against stored artifacts — honest, and named as such, but a replay of a function
proves the function and says nothing about whether the cycle reaches it. 1.7.1's R7
diagnostic passed that way while the live path had never delivered a row (#1256).

**What a fault is.** A *named shape*, not a policy: one pure transform over one emission,
declared on the cycle and applied in the producing agent's container, so the entire
downstream path — typed checks, ownership attribution, routing, repair, verification,
retest, refund — runs exactly as it would on a real defect. The transforms name real
shapes real rolls produced, and each carries the roll it came from.

**Applied once, without state.** A fault applies only to a task's FIRST attempt: the
executor sets ``inputs["emission_retry_feedback"]`` when it re-dispatches after an emission
failure (#566), and a repair task's own id carries its attempt index. So "once" is read off
the inputs rather than remembered, and the retry or repair that follows runs clean — which
is the point, because what the diagnostic is watching is the loop *recovering*.

**Non-counting by construction.** A cycle that declares a fault is a diagnostic. The
verification-set driver refuses to count a roll whose set config declares one, and a record
that carries one names it beside every readout, so an injected red can never be read as a
real one.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

#: The ``execution_overrides`` key a cycle declares faults under. One key, so a cycle that
#: carries a fault is recognisable from its stored overrides alone — which is what lets the
#: driver refuse to count it without knowing anything about the individual faults.
DECLARATION_KEY = "fault_injection"

_FENCE_OPEN = re.compile(r"^(\s{0,3}```)([^\s`]*)$", re.M)


def _strip_fences(content: str) -> str:
    """Everything before the first fence, or a stated refusal if there was nothing else.

    The contentless-emission shape 1.7.1 met fourteen times (#1268): a sentence of intent
    and no addressed fence. Reproduced by keeping the model's own preamble rather than
    substituting prose of ours, so the emission that reaches the handler is the shape the
    handler actually saw.
    """
    head = content.split("```", 1)[0].strip()
    return head or "I'll verify the workspace state before emitting."


def _prefix_paths_with_path_segment(content: str) -> str:
    """Address every fence at ``path/<real path>`` — the #1272 shape.

    React roll 5: the fence template's placeholder ``path/to/file`` was copied literally,
    so a correct suite landed at a path nothing expected and a whole round was spent.
    """

    def repl(match: re.Match[str]) -> str:
        fence, info = match.group(1), match.group(2)
        if ":" not in info:
            return match.group(0)
        tag, _, target = info.partition(":")
        return f"{fence}{tag}:path/{target}"

    return _FENCE_OPEN.sub(repl, content)


def _vitest_own_frame_type_error(content: str) -> str:
    """Import ``userEvent`` from the package that does not export it — the #1270 shape.

    React roll 4: the suite imported ``userEvent`` from ``@testing-library/react`` instead
    of ``@testing-library/user-event``, so three cases died at the suite's own call site
    with ``TypeError: default.click is not a function``. The transform is the one-line
    import edit that produced it, applied to whatever the model emitted.
    """
    swapped = content.replace("@testing-library/user-event", "@testing-library/react")
    if swapped != content:
        return swapped
    # No such import to break: append a call to a name the module never binds, which is
    # the same class of failure (raised at the suite's own frame, `is not a function`).
    return content


@dataclass(frozen=True)
class Fault:
    """One named emission shape, and the task whose first attempt takes it."""

    #: Suffix of the task id the fault applies to — the capability, as the executor names
    #: it (``task-run_x-m006-qa.test`` ends with ``qa.test``).
    task: str
    transform: Callable[[str], str]
    #: The roll that produced this shape, so a diagnostic's own record can cite it.
    found_in: str
    #: The prediction the fault exists to exercise.
    exercises: str


#: Every declared fault. Adding one is a declaration, not a policy change: the transform
#: reproduces a shape a real roll produced, and ``found_in`` says which.
FAULTS: dict[str, Fault] = {
    "qa_suite_absent": Fault(
        task="qa.test",
        transform=_strip_fences,
        found_in="#1268 — 14 attempts across the 1.7.1 counted rolls",
        exercises="L2 (#1269): a repair that supplies the suite an emission failure lacked "
        "is retested",
    ),
    "qa_suite_at_path_prefix": Fault(
        task="qa.test",
        transform=_prefix_paths_with_path_segment,
        found_in="#1272 — React roll 5 (cyc_ca02bed7fbb4)",
        exercises="L8 (#1272): no emission lands under a literal `path/` prefix",
    ),
    "qa_suite_vitest_own_frame_type_error": Fault(
        task="qa.test",
        transform=_vitest_own_frame_type_error,
        found_in="#1270 — React roll 4 (cyc_de4b2dea73a0), R2 falsified",
        exercises="L7 (#1270): an own-frame failure in a qa-owned file routes to `qa.test_repair`",
    ),
    "repair_prose_only": Fault(
        task="qa.test_repair",
        transform=_strip_fences,
        found_in="#1273 — Next.js roll 1 (cyc_9be98128f0e9)",
        exercises="L4 (#1273): a prose-only repair is refunded rather than verified",
    ),
}


class UnknownFault(ValueError):
    """A cycle declares a fault the framework does not define."""


class UnreachableFault(ValueError):
    """A declared fault names a task whose emission seam does not call the injector."""


def declared_faults(resolved_config: Mapping[str, Any] | None) -> tuple[str, ...]:
    """The fault names a cycle declares, in declaration order. Empty for a normal cycle."""
    if not resolved_config:
        return ()
    declared = resolved_config.get(DECLARATION_KEY)
    if not declared:
        return ()
    if isinstance(declared, str):
        return (declared,)
    return tuple(str(name) for name in declared)


def validate_declaration(resolved_config: Mapping[str, Any] | None) -> tuple[str, ...]:
    """The declared faults, refused loudly if any is unknown or cannot be reached.

    **Refused, not ignored.** A diagnostic whose fault silently never fires reports a green
    cycle and reads as evidence that the loop handled the fault — the opposite of what
    happened. So an unknown name, or a known one whose seam does not call the injector, is
    a cycle-create failure.
    """
    names = declared_faults(resolved_config)
    unknown = [name for name in names if name not in FAULTS]
    if unknown:
        raise UnknownFault(
            f"unknown fault(s) {sorted(unknown)}; declared faults are {sorted(FAULTS)}"
        )
    unreachable = sorted({FAULTS[name].task for name in names} - INJECTED_TASKS)
    if unreachable:
        raise UnreachableFault(
            f"fault(s) declared for task(s) {unreachable}, whose emission seam does not "
            f"call inject(); wired tasks are {sorted(INJECTED_TASKS)}"
        )
    return names


#: The capabilities whose emission seam calls ``inject``. Held to the call sites by
#: ``test_every_declared_fault_is_reachable_from_a_wired_seam`` — the list is what makes
#: an unreachable declaration a refusal instead of a silent no-op.
INJECTED_TASKS: frozenset[str] = frozenset({"qa.test", "qa.test_repair", "development.develop"})


def _is_first_attempt(task_id: str, inputs: Mapping[str, Any] | None) -> bool:
    """Whether this emission is the task's first — read off the inputs, never remembered.

    Two markers, because the loop re-runs a task in two different ways: the executor's
    emission retry carries ``emission_retry_feedback`` (#566) under the same task id, and a
    repair round gets a new task id whose attempt index is in it
    (``repair-run_x-01-qa.test_repair``).
    """
    if (inputs or {}).get("emission_retry_feedback"):
        return False
    attempt = re.search(r"-(\d{2})-", task_id)
    return attempt is None or attempt.group(1) == "00"


def inject(
    content: object,
    *,
    handler_name: str,
    task_id: str,
    resolved_config: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None = None,
) -> object:
    """The emission a declared fault turns this one into, or the emission unchanged.

    Called at the emission seam, before the shape is logged, so every readout downstream
    reads one consistent emission. The injection logs itself with the before/after size:
    an injected red that is not obvious in the log is one a record can mistake for real.
    """
    if not isinstance(content, str):
        return content
    names = declared_faults(resolved_config)
    if not names:
        return content
    for name in names:
        fault = FAULTS.get(name)
        if fault is None or not task_id.endswith(fault.task):
            continue
        if not _is_first_attempt(task_id, inputs):
            logger.info(
                "fault_injection: %s declared for %s but this is not the first attempt — "
                "not applied (the recovery path is what the diagnostic observes)",
                name,
                task_id,
            )
            continue
        faulted = fault.transform(content)
        logger.warning(
            "fault_injection: APPLIED %s to task=%s handler=%s chars %d -> %d "
            "(found_in=%s exercises=%s) — this cycle is a DIAGNOSTIC and must not be counted",
            name,
            task_id,
            handler_name,
            len(content),
            len(faulted),
            fault.found_in,
            fault.exercises,
        )
        return faulted
    return content
