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


#: Inserted into the first case when the import swap has nothing to swap. Named so a reader
#: of a failing suite finds this module rather than hunting a real defect.
_INJECTED_CALL_JS = "  expect.__squadops_injected_fault__();  // #1251 injected fault"
_INJECTED_CALL_PY = "__squadops_injected_fault__()  # #1251 injected fault"

_FIRST_CASE_BODY_JS = re.compile(
    r"^(?P<indent>[ \t]*)(?:it|test)\s*\(\s*(?P<quote>['\"`]).*?(?P=quote)\s*,"
    r"\s*(?:async\s+)?(?:\(\s*\)|[\w$]+)\s*=>\s*\{",
    re.M,
)
_FIRST_CASE_BODY_PY = re.compile(
    r"^(?P<indent>[ \t]*)(?:async\s+)?def\s+test_\w*\s*\([^)]*\)\s*(?:->[^:]+)?:[ \t]*$",
    re.M,
)


def _inject_js_own_frame_call(content: str) -> str:
    """A call to a non-function property of ``expect``, which every vitest suite binds.

    Raises ``TypeError: expect.__squadops_injected_fault__ is not a function`` at the
    suite's own call site — roll 4's shape, without inventing an import.
    """
    match = _FIRST_CASE_BODY_JS.search(content)
    if match is None:
        return content
    at = match.end()
    return f"{content[:at]}\n{match.group('indent')}{_INJECTED_CALL_JS}{content[at:]}"


def _inject_py_own_frame_call(content: str) -> str:
    """A call to a name the module never binds, inside the first ``test_`` function.

    Raises ``NameError`` at the suite's own frame — the pytest own-frame shape
    ``_OWN_FRAME_SHAPES`` declares, and one the application cannot have caused.
    """
    match = _FIRST_CASE_BODY_PY.search(content)
    if match is None:
        return content
    at = match.end()
    body_indent = match.group("indent") + "    "
    return f"{content[:at]}\n{body_indent}{_INJECTED_CALL_PY}{content[at:]}"


def _qa_suite_own_frame_failure(content: str) -> str:
    """Make the qa suite die at its own call site, in whatever language it is written.

    **Runner-aware, because a capability is not a runner (#1304).** This fault targets
    ``qa.test``, and a cycle's plan may put a backend pytest suite on the qa task that runs
    first — a vitest shape cannot bite a Python file, so whether the prediction got
    exercised came down to which suite the planner happened to schedule. Two consecutive
    diagnostics went that way: `cyc_06747fde42f2` bit only because a frontend task also
    existed, and `cyc_ef8b997de07a` had one qa task, a pytest one, and exercised nothing.

    ``_OWN_FRAME_SHAPES`` is already keyed by runner; this now consults the same fact.

    Order is faithfulness first: the real import swap (React roll 4's own one-line edit),
    then the language-appropriate synthesized call.
    """
    swapped = content.replace("@testing-library/user-event", "@testing-library/react")
    if swapped != content:
        return swapped
    injected = _inject_js_own_frame_call(content)
    if injected != content:
        return injected
    return _inject_py_own_frame_call(content)


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
    # Renamed from `qa_suite_vitest_own_frame_type_error` (#1304): the shape is no longer
    # vitest-only, and a name that says otherwise would misdescribe what a diagnostic ran.
    "qa_suite_own_frame_failure": Fault(
        task="qa.test",
        transform=_qa_suite_own_frame_failure,
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
    """The fault names a cycle declares, in declaration order. Empty for a normal cycle.

    **A comma-separated string is a list** (#1298). ``execution_overrides`` reaches a cycle
    through ``squadops cycles create --set k=v``, whose values are strings with no coercion,
    so a declaration of two faults has no other way to arrive. Without this the chained
    diagnostic — one cycle taking an own-frame suite failure and then a prose-only repair —
    could not be launched at all, and that chain is how the 1.7.2 set exercises three of its
    predictions. Fault names are identifiers and never contain a comma.
    """
    if not resolved_config:
        return ()
    declared = resolved_config.get(DECLARATION_KEY)
    if not declared:
        return ()
    if isinstance(declared, str):
        declared = [part for part in (p.strip() for p in declared.split(",")) if part]
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


#: Set by the executor every time a task's outcome is handled, so the attempt that follows
#: can be told apart from the first (#1304).
PRIOR_ATTEMPTS_KEY = "prior_attempts"


def _is_first_attempt(task_id: str, inputs: Mapping[str, Any] | None) -> bool:
    """Whether this emission is the task's first — read off the inputs, never remembered.

    **Three markers, because two were not enough (#1304).** ``prior_attempts`` is the
    general one: the executor stamps it whenever a task's outcome is handled, so any later
    dispatch of that envelope carries it whatever caused the re-run. The other two are kept
    because they are independently truthful and cost nothing — ``emission_retry_feedback``
    (#566) for the emission retry, and a repair task's own attempt index.

    Before ``prior_attempts``, a re-dispatch from the CORRECTION loop carried neither of
    the other two, so the fault re-applied to every repaired emission and the loop could
    never be seen recovering — which is the entire thing a diagnostic watches. Observed on
    `cyc_06747fde42f2`: the same task id took the fault twice with a full correction round
    between.
    """
    supplied = inputs or {}
    if supplied.get(PRIOR_ATTEMPTS_KEY):
        return False
    if supplied.get("emission_retry_feedback"):
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
        if faulted == content:
            # #1300: "applied" and "applied and inert" used to print the same word, so a
            # fault that could not bite read as an exercise. The only signal was the two
            # char counts mid-line, which no readout compared.
            logger.warning(
                "fault_injection: DID NOT BITE %s on task=%s handler=%s — the emission was "
                "returned unchanged (%d chars), so the downstream path runs as if no fault "
                "were declared. THIS DIAGNOSTIC PROVES NOTHING about %s.",
                name,
                task_id,
                handler_name,
                len(content),
                fault.exercises,
            )
            return content
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
