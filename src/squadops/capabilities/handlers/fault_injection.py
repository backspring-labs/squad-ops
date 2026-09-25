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

import asyncio
import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from squadops.tasks.task_types import TaskType

logger = logging.getLogger(__name__)

#: The ``execution_overrides`` key a cycle declares faults under. One key, so a cycle that
#: carries a fault is recognisable from its stored overrides alone — which is what lets the
#: driver refuse to count it without knowing anything about the individual faults.
DECLARATION_KEY = "fault_injection"

_FENCE_OPEN = re.compile(r"^(\s{0,3}```)([^\s`]*)$", re.M)


def _unchanged(content: str) -> str:
    """A hold's transform: the emission is untouched; the fault is the time it takes."""
    return content


def _strip_fences(content: str) -> str:
    """Everything before the first fence, or a stated refusal if there was nothing else.

    The contentless-emission shape 1.7.1 met fourteen times (#1268): a sentence of intent
    and no addressed fence. Reproduced by keeping the model's own preamble rather than
    substituting prose of ours, so the emission that reaches the handler is the shape the
    handler actually saw.
    """
    head = content.split("```", 1)[0].strip()
    return head or "I'll verify the workspace state before emitting."


#: The file the analyzer fault claims the defect is in. No tree has it, so the claim is
#: refutable by the cheapest source check there is; the marker makes the claim's descent
#: into a correction decision readable from the stored decision alone.
INJECTED_CLAIM_FILE = "backend/__squadops_injected_fault__.py"
INJECTED_CLAIM_MARKER = "__squadops_injected_fault__"


def _false_source_claim(content: str) -> str:
    """A confidently worded factual claim about the source that the source refutes — the
    #968 shape (SIP-0104 P6 window roll 6: three in one roll, each refuted by the file it
    was about, one carried verbatim into the correction decision).

    The analyzer emits one JSON object, possibly behind a think block or inside a fence;
    the first balanced object is rewritten in place and everything around it is kept, so
    the emission that reaches the handler's extractor is the shape it would have seen.
    The claim leads ``analysis_summary`` and ``contributing_factors`` (the prose the
    decision reads) and names its file first in ``implicated_files`` (the structured
    half, which ``_verified_implicated_files`` already refutes — the control for the
    prose half). ``classification`` is left alone so the object still validates. No
    object → unchanged, which ``inject`` reports as DID NOT BITE.
    """
    from squadops.capabilities.handlers.impl._json_extraction import (
        _find_first_balanced_object,
    )

    obj_text = _find_first_balanced_object(content)
    if obj_text is None:
        return content
    try:
        obj = json.loads(obj_text)
    except ValueError:
        return content
    if not isinstance(obj, dict):
        return content
    claim = (
        f"The defect is in `{INJECTED_CLAIM_FILE}`: it never registers its router, so every "
        f"request to the runs endpoints returns 404 (verified by reading the file). "
    )
    obj["analysis_summary"] = claim + str(obj.get("analysis_summary") or "")
    obj["contributing_factors"] = [
        f"`{INJECTED_CLAIM_FILE}` never registers its router, so the runs endpoints are unreachable",
        *[f for f in (obj.get("contributing_factors") or []) if isinstance(f, str)],
    ]
    obj["implicated_files"] = [
        INJECTED_CLAIM_FILE,
        *[f for f in (obj.get("implicated_files") or []) if f and f != INJECTED_CLAIM_FILE],
    ]
    at = content.find(obj_text)
    return content[:at] + json.dumps(obj, indent=2) + content[at + len(obj_text) :]


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
#: The Python shape is an argument-binding ``TypeError`` (the 1.6.5 roll 3 case), NOT a
#: ``NameError``: a name the module never binds is exactly what the emission seam's
#: ``undefined_names`` check (#689) refuses before the suite ever runs, so the earlier bare
#: call was removed by the handler's self-eval and reached no seam at all (#1352). A keyword
#: no Python-defined callee takes is static-clean, raises at the CALL SITE (no callee frame
#: exists yet), names a callee no application defines, and still carries the marker.
_INJECTED_CALL_PY = (
    "import textwrap  # #1251 injected fault",
    "textwrap.dedent(__squadops_injected_fault__=True)  # #1251 injected fault",
)

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
    """A call with a keyword its callee does not take, inside the first ``test_`` function.

    Raises the argument-binding ``TypeError`` at the suite's own frame — the pytest
    own-frame shape ``_OWN_FRAME_SHAPES`` declares, and one the application cannot have
    caused — and passes the emission seam's static checks on the way there (#1352).
    """
    match = _FIRST_CASE_BODY_PY.search(content)
    if match is None:
        return content
    at = match.end()
    body_indent = match.group("indent") + "    "
    injected = "".join(f"\n{body_indent}{line}" for line in _INJECTED_CALL_PY)
    return f"{content[:at]}{injected}{content[at:]}"


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


#: One addressed fenced block of an emission: the opening line's info string and its body.
_ADDRESSED_BLOCK = re.compile(
    r"^(?P<open>[ \t]{0,3}```(?P<info>[^\s`]*)[^\n]*\n)(?P<body>.*?)(?P<close>^[ \t]{0,3}```[ \t]*$)",
    re.M | re.S,
)
#: A Python route decorator whose path ends in ``/join`` — the frozen decorator both stacks'
#: FastAPI skeletons pin (``@router.post("/runs/{run_id}/join", ...)``).
_PY_JOIN_DECORATOR = re.compile(r"^@\w+\.(?:post|put|patch)\(\s*[\"'][^\"']*/join[\"']", re.M)
_PY_TOP_LEVEL = re.compile(r"^(?:@|def |async def |class |\S)", re.M)
_PY_RETURN = re.compile(r"^(?P<indent>[ \t]+)return (?P<expr>[\w.\[\]\"']+)[ \t]*$", re.M)
#: The success return every stored Next.js join route ends with (3 of 3 accepted 1.7.5 rolls).
_TS_JSON_RETURN = re.compile(
    r"return (?P<ctor>Response|NextResponse)\.json\((?P<expr>[\w.]+)(?P<rest>\s*,[^()]*)?\)(?P<semi>;?)"
)
_INJECTED_JOIN_NOTE = "#1251 injected fault: the join response omits the run's declared fields"


def _python_join_without_fields(body: str) -> str:
    """The join handler's final ``return <value>`` answers ``{"id": <value>.id}`` instead.

    Every accepted 1.7.5 React roll ends the handler with ``return run`` under the frozen
    ``response_model=Run`` decorator, so the response fails the model and the app answers
    500 where the contract probe expects 200 and the run's fields.
    """
    decorator = _PY_JOIN_DECORATOR.search(body)
    if decorator is None:
        return body
    start = body.find("\n", decorator.end()) + 1
    # The handler runs to the next top-level line after its own ``def``.
    signature = re.compile(r"^(?:async )?def ", re.M).search(body, start)
    if signature is None:
        return body
    after_def = body.find("\n", signature.end()) + 1
    following = _PY_TOP_LEVEL.search(body, after_def)
    end = following.start() if following else len(body)
    returns = list(_PY_RETURN.finditer(body, after_def, end))
    if not returns:
        return body
    last = returns[-1]
    replacement = (
        f'{last.group("indent")}return {{"id": getattr({last.group("expr")}, "id", None)}}'
        f"  # {_INJECTED_JOIN_NOTE}"
    )
    return body[: last.start()] + replacement + body[last.end() :]


def _typescript_join_without_fields(body: str) -> str:
    """The route's final ``return Response.json(<value>)`` answers ``{ id }`` instead.

    The frozen join shell's response floor (#1029) asserts the declared fields before any
    qa fill runs, so the probe fails on the missing fields. The cast keeps ``next build``'s
    type check clean, so the defect reaches the probe rather than stopping at the build.
    """
    returns = list(_TS_JSON_RETURN.finditer(body))
    if not returns:
        return body
    last = returns[-1]
    replacement = (
        f"return {last.group('ctor')}.json({{ id: ({last.group('expr')} as unknown as "
        f"{{ id?: unknown }}).id }}{last.group('rest') or ''}){last.group('semi')} "
        f"// {_INJECTED_JOIN_NOTE}"
    )
    return body[: last.start()] + replacement + body[last.end() :]


def _join_response_omits_declared_fields(content: str) -> str:
    """Make the join endpoint's success response carry only the run's id.

    **The class, not the literal 1.6.3 field.** 1.6.3's Next.js rolls 1, 4 and 5 were
    rejected, correctly, because the join response failed the frozen response floor every
    round: bare-string ``participants`` where the manifest declared objects, and a missing
    ``normalized`` field (record §6). Today's rolls author their own manifests, and in all
    seven accepted 1.7.5 join handlers the collection's element kind is whatever that
    manifest declares, so rewriting the element would inject a correct app on some rolls.
    Omitting the declared fields is the same defect class — the response against the
    declared shape — and fails on every manifest.

    Scoped by language to the join handler: a Python block's function under a ``/join``
    decorator, and a TypeScript block addressed at a ``join/route.ts`` path. Every other
    block, and every other handler in the same file, is returned unchanged.
    """

    def rewrite(match: re.Match[str]) -> str:
        info, body = match.group("info"), match.group("body")
        path = info.partition(":")[2]
        if path.endswith(".py"):
            new_body = _python_join_without_fields(body)
        elif path.endswith("join/route.ts"):
            new_body = _typescript_join_without_fields(body)
        else:
            return match.group(0)
        return match.group("open") + new_body + match.group("close")

    return _ADDRESSED_BLOCK.sub(rewrite, content)


class FaultScope(Enum):
    """Which attempts of the target task take the fault — the scope of "once" (#1310).

    "Apply once" (#1304) exists so the loop can be *seen recovering*; but which recovery a
    fault exists to watch differs per fault, and one global rule put ``qa_suite_absent``
    on the wrong side of it. Its recovery is the REPAIR that supplies the missing suite
    (L2, #1269) — not the emission retry, which under FIRST_ATTEMPT emitted a good suite,
    succeeded, and never let the task reach correction (`cyc_e38566bb7b5d`: "correction
    rounds: 0"). The diagnostic bit and proved nothing about the seam it names.
    """

    #: The task's first attempt only. Right for a fault whose recovery is a repair or a
    #: re-take of that same task — the retry that follows must run clean.
    FIRST_ATTEMPT = "first_attempt"
    #: Every emission attempt of the target task — first and each emission retry (#566) —
    #: so the task exhausts its retries and fails into correction. Never the repair task
    #: (a different capability) and never a correction re-dispatch of the target, which
    #: carries ``prior_attempts`` without an emission-retry marker: that IS the recovery.
    ALL_EMISSION_ATTEMPTS = "all_emission_attempts"


@dataclass(frozen=True)
class Fault:
    """One named emission shape, and the attempts of the task that take it."""

    #: Suffix of the task id the fault applies to — the capability, as the executor names
    #: it (``task-run_x-m006-qa.test`` ends with ``qa.test``).
    task: str
    transform: Callable[[str], str]
    #: The roll that produced this shape, so a diagnostic's own record can cite it.
    found_in: str
    #: The prediction the fault exists to exercise.
    exercises: str
    #: The scope of "once" (#1310).
    scope: FaultScope = FaultScope.FIRST_ATTEMPT
    #: A hold, not a transform (1.8.2 item 15): the handler stops answering after the model
    #: returns, until the declared task timeout ends it. ``transform`` is then the identity.
    hold: bool = False


#: Every declared fault. Adding one is a declaration, not a policy change: the transform
#: reproduces a shape a real roll produced, and ``found_in`` says which.
FAULTS: dict[str, Fault] = {
    "qa_suite_absent": Fault(
        task=TaskType.QA_TEST,
        transform=_strip_fences,
        found_in="#1268 — 14 attempts across the 1.7.1 counted rolls",
        exercises="L2 (#1269): a repair that supplies the suite an emission failure lacked "
        "is retested",
        # #1310: the recovery under test is the repair, so the emission retries must not
        # be the thing standing between the fault and the seam.
        scope=FaultScope.ALL_EMISSION_ATTEMPTS,
    ),
    "qa_suite_at_path_prefix": Fault(
        task=TaskType.QA_TEST,
        transform=_prefix_paths_with_path_segment,
        found_in="#1272 — React roll 5 (cyc_ca02bed7fbb4)",
        exercises="L8 (#1272): no emission lands under a literal `path/` prefix",
    ),
    # Renamed from `qa_suite_vitest_own_frame_type_error` (#1304): the shape is no longer
    # vitest-only, and a name that says otherwise would misdescribe what a diagnostic ran.
    "qa_suite_own_frame_failure": Fault(
        task=TaskType.QA_TEST,
        transform=_qa_suite_own_frame_failure,
        found_in="#1270 — React roll 4 (cyc_de4b2dea73a0), R2 falsified",
        exercises="L7 (#1270): an own-frame failure in a qa-owned file routes to `qa.test_repair`",
    ),
    "repair_prose_only": Fault(
        task=TaskType.QA_TEST_REPAIR,
        transform=_strip_fences,
        found_in="#1273 — Next.js roll 1 (cyc_9be98128f0e9)",
        exercises="L4 (#1273): a prose-only repair is refunded rather than verified",
    ),
    # 1.7.4 plan §3.1: the two void counted rolls in two lines (#1318, #1364) were reached
    # by chance; this makes the shape exercisable. #1506 split it in two, because since #1372
    # gave the builder an aimed retry one fault cannot reach both seams: the retry recovers
    # attempt 2 before the task ever fails into correction. This one is R1's — first attempt
    # only, so the recovery under test is the retry that carries the fact.
    "builder_emission_contentless": Fault(
        task=TaskType.BUILDER_ASSEMBLE,
        transform=_strip_fences,
        found_in="#1364 — 1.7.3 counted roll 1 (cyc_af7dd4ad95b0), void: a 160-token first "
        "emission with no fence",
        exercises="R1 (#1372): the contentless builder attempt is retried with its "
        "emission-shape fact, and the retry's emission is accepted",
    ),
    # #1506: F1's — the same shape on every emission attempt, so the builder exhausts its
    # retries and fails into correction, and the accepted patch's framework rows are composed
    # from the patched set (#1374). The 1.7.5 diagnostic could not reach this seam on any deploy
    # carrying #1372 (plan §3.9a, record §4); the scope #1310 added for `qa_suite_absent` is
    # exactly what it lacked.
    "builder_emission_contentless_all_attempts": Fault(
        task=TaskType.BUILDER_ASSEMBLE,
        transform=_strip_fences,
        found_in="#1506 — the 1.7.5 contentless-builder diagnostic: R1 reached, F1 unreachable "
        "since #1372's retry recovers the builder before correction",
        exercises="F1 (#1374): a builder attempt contentless through its emission retries fails "
        "into correction, and the accepted patch's framework rows are re-derived from the "
        "patched set, never composed from the contentless attempt",
        scope=FaultScope.ALL_EMISSION_ATTEMPTS,
    ),
    # 1.8.0 plan §4.1: the dev lane had no fault, so no diagnostic could force a development
    # repair and Scoped Code Revision's dev grant (SIP-0107 §38 step 3) had nothing to prove
    # itself on. First attempt only: the develop task's emission takes it, the qa task's
    # probes reject the app, and the development repair that follows runs clean.
    "dev_join_response_omits_declared_fields": Fault(
        task=TaskType.DEVELOPMENT_DEVELOP,
        transform=_join_response_omits_declared_fields,
        found_in="#1029's response floor — 1.6.3 Next.js set record §6: rolls 1, 4 and 5 rejected, "
        "correctly, on a join response that failed the frozen floor every round",
        exercises="the dev lane: a probe failure on a developer-owned route is repaired by a "
        "development repair aimed at the probe-owned slot, verified and applied",
    ),
    # 1.7.4 plan §3.1: A1's exercise. The correction task id carries the round as its
    # attempt index (``corr-<run>-00-data.analyze_failure``), so FIRST_ATTEMPT is round 0's
    # analysis only and the rounds after it run clean — the readout asks whether the
    # decision of that round inherited the claim. Reached only behind a failure, so a
    # diagnostic chains it after a failure-producing fault (#1298).
    # 1.8.2 plan §4.1, the unattended-chain diagnostic's hang cycle: a hold, not a transform.
    "handler_hang": Fault(
        task=TaskType.DEVELOPMENT_DEVELOP,
        transform=_unchanged,
        found_in="#995 — V7 roll 1: the final development.develop attempt was killed by the "
        "1,800 s task timeout mid self-eval; the hang a campaign left unattended must survive "
        "(1.8.2 plan §4.1 unattended-chain)",
        exercises="item 15: the hung task fails at the declared task timeout as a typed "
        "task_timeout fact, and the run proceeds to correction or termination",
        hold=True,
    ),
    "analyzer_false_source_claim": Fault(
        task=TaskType.DATA_ANALYZE_FAILURE,
        transform=_false_source_claim,
        found_in="#968 — SIP-0104 P6 window roll 6: three claims in one roll, each refuted by "
        "the file it was about, one carried verbatim into the correction decision",
        exercises="A1 (#968): a correction decision does not inherit an analyzer claim the "
        "source refutes",
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
INJECTED_TASKS: frozenset[str] = frozenset(
    {
        TaskType.QA_TEST,
        TaskType.QA_TEST_REPAIR,
        TaskType.DEVELOPMENT_DEVELOP,
        # 1.7.4 plan §3.1: the builder's and the analyzer's emission seams.
        TaskType.BUILDER_ASSEMBLE,
        TaskType.DATA_ANALYZE_FAILURE,
    }
)


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


def _is_emission_retry(inputs: Mapping[str, Any] | None) -> bool:
    """A re-dispatch after an emission failure (#566) — the executor's own marker."""
    return bool((inputs or {}).get("emission_retry_feedback"))


def _applies(fault: Fault, task_id: str, inputs: Mapping[str, Any] | None) -> bool:
    """Whether this attempt is inside the fault's scope (#1310) — a table, not a branch."""
    return _SCOPE_RULES[fault.scope](task_id, inputs)


_SCOPE_RULES: dict[FaultScope, Callable[[str, Mapping[str, Any] | None], bool]] = {
    FaultScope.FIRST_ATTEMPT: _is_first_attempt,
    FaultScope.ALL_EMISSION_ATTEMPTS: lambda task_id, inputs: (
        _is_first_attempt(task_id, inputs) or _is_emission_retry(inputs)
    ),
}


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
        if fault is None or fault.hold or not task_id.endswith(fault.task):
            continue
        if not _applies(fault, task_id, inputs):
            logger.info(
                "fault_injection: %s declared for %s but this attempt is outside its scope "
                "(%s) — not applied (the recovery path is what the diagnostic observes)",
                name,
                task_id,
                fault.scope.value,
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
            "fault_injection: APPLIED %s to task=%s handler=%s chars %d -> %d scope=%s "
            "(found_in=%s exercises=%s) — this cycle is a DIAGNOSTIC and must not be counted",
            name,
            task_id,
            handler_name,
            len(content),
            len(faulted),
            fault.scope.value,
            fault.found_in,
            fault.exercises,
        )
        return faulted
    return content


#: How long a hold lasts if nothing ends it: a day, far past any declared task timeout. The
#: agent's own bound — the declared wait the dispatcher stamps on the task — cancels it first.
HANG_SECONDS = 24 * 60 * 60


async def hold(
    content: object,
    *,
    handler_name: str,
    task_id: str,
    resolved_config: Mapping[str, Any] | None,
    inputs: Mapping[str, Any] | None = None,
) -> None:
    """Stop answering, if a declared hold applies to this attempt (1.8.2 item 15).

    Called at the emission seam right after ``inject``: the model has returned and the handler
    goes quiet, as it would behind a stuck call. The sleep is cooperative, so the agent's
    heartbeat keeps running; what ends it is the task's declared bound, on the agent's side
    and the orchestrator's. Logged in ``APPLIED`` form so a record's ``faults_applied`` reads it
    like any other fault.
    """
    for name in declared_faults(resolved_config):
        fault = FAULTS.get(name)
        if fault is None or not fault.hold or not task_id.endswith(fault.task):
            continue
        if not _applies(fault, task_id, inputs):
            logger.info(
                "fault_injection: %s declared for %s but this attempt is outside its scope "
                "(%s) — not applied (the recovery path is what the diagnostic observes)",
                name,
                task_id,
                fault.scope.value,
            )
            continue
        size = len(content) if isinstance(content, str) else 0
        logger.warning(
            "fault_injection: APPLIED %s to task=%s handler=%s chars %d -> %d scope=%s "
            "(found_in=%s exercises=%s) — holding after the model returned until the declared "
            "task timeout ends it; this cycle is a DIAGNOSTIC and must not be counted",
            name,
            task_id,
            handler_name,
            size,
            size,
            fault.scope.value,
            fault.found_in,
            fault.exercises,
        )
        await asyncio.sleep(HANG_SECONDS)
