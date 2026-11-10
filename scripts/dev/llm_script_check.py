"""Check a recorded script's answers against the handlers that will read them (#2892).

A scripted answer is read by the same handler a model's answer is, so an answer the handler's
own parse refuses fails its task at replay, however faithfully it was recorded. The 2.7 soak's
first dry run stopped that way at its first launch: the recorder replayed the stored
``change_request.yaml``, which carries the fields the framework derives, and the proposal handler
refuses a document that authors them.

Each answer is run through its handler's deterministic parse and validation, the functions the
live handler calls, on the answer alone:
- ``strategy.propose_increment``: the first YAML block, ``parse_change_request`` on the proposal's
  recorded arguments, and the stored document rebuilt from the answer and the recorded derived
  fields, which ``load_stored_change_request`` accepts only if its hash is the recording's;
- the plan-authoring steps: their ``from_yaml`` parse, the proposer's role, and the brief id the
  proposals and the guidance must cite (the brief's answer in the same script);
- ``governance.define_done``, ``data.analyze_failure``, ``governance.correction_decision``: the JSON
  object, and the analysis's schema or the decision's correction path;
- ``governance.review_plan``: its frontmatter, with a readiness and a score the handler keeps;
- the build and test steps: at least one fenced file;
- the repair steps: their anchored edits, none malformed.

What it can't see is anything that reads the run's tree or inputs: the proposal's rails against
the product, a test suite's result, a typed check, an edit's anchor in the deploy's base. The
dry run reads those.

An answer whose attempt the recording banked as failed (``recorded_from.failed_in_recording``) may
be refused: the replay takes the same path.

Usage::

    python scripts/dev/llm_script_check.py [<script name> ...]   # default: every packaged script
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from squadops.campaigns.change_request import (  # noqa: E402
    ChangeRequestError,
    IncrementBasis,
    load_stored_change_request,
    parse_change_request,
)
from squadops.capabilities.anchored_edits import parse_anchored_edits  # noqa: E402
from squadops.capabilities.handlers._plan_authoring import _first_yaml_block_or_none  # noqa: E402
from squadops.capabilities.handlers.fenced_parser import extract_fenced_files  # noqa: E402
from squadops.capabilities.handlers.impl._json_extraction import (  # noqa: E402
    JSONExtractionError,
    extract_first_json_object,
)
from squadops.capabilities.handlers.impl.analyze_failure import FailureAnalysis  # noqa: E402
from squadops.capabilities.handlers.impl.correction_decision import (  # noqa: E402
    _VALID_CORRECTION_PATHS,
    _VALID_PLAN_CHANGE_CANDIDATES,
)
from squadops.capabilities.handlers.planning.review import _VALID_READINESS  # noqa: E402
from squadops.cycles.plan_authoring_brief import PlanAuthoringBrief  # noqa: E402
from squadops.cycles.plan_guidance import PlanGuidance  # noqa: E402
from squadops.cycles.proposed_role_tasks import ProposedRoleTasks  # noqa: E402
from squadops.llm.script import AnswerKey, LLMScript, ScriptLibrary  # noqa: E402
from squadops.prompts.frontmatter import (  # noqa: E402
    FrontmatterError,
    parse_frontmatter,
    split_frontmatter,
)
from squadops.tasks.task_types import TaskType  # noqa: E402

#: ``recorded_from`` keys the recorder writes for this check.
CHANGE_REQUESTS_KEY = "change_requests"
FAILED_KEY = "failed_in_recording"


class _Refused(Exception):
    """The handler would refuse this answer, and why."""


def _yaml_block(content: str) -> str:
    block = _first_yaml_block_or_none(content)
    if block is None:
        raise _Refused("no YAML block the handler would read")
    return block


def _proposal(content: str, key: AnswerKey, recorded: dict[str, Any]) -> None:
    derived = (recorded.get(CHANGE_REQUESTS_KEY) or {}).get(str(key))
    if not isinstance(derived, dict):
        raise _Refused(f"no recorded {CHANGE_REQUESTS_KEY} entry for it, so it can't be checked")
    authored = yaml.safe_load(_yaml_block(content))
    if not isinstance(authored, dict):
        raise _Refused("its change request is not a mapping")
    basis = IncrementBasis(str(derived.get("basis") or IncrementBasis.MANIFEST))
    try:
        # The live handler's parse (validate_proposal, either basis), on the proposal's identity.
        parse_change_request(
            authored,
            proposal_id=str(derived["proposal_id"]),
            version=int(derived["version"]),
            baseline_tree=str(derived["baseline_tree"]),
            basis=basis,
        )
        # The stored document rebuilt: accepted only if the answer is what was ruled on.
        stored = {**authored, **{k: v for k, v in derived.items() if k != "footprint"}}
        if "footprint" in derived:
            stored["footprint"] = derived["footprint"]
        load_stored_change_request(yaml.safe_dump(stored, sort_keys=False))
    except ChangeRequestError as e:
        raise _Refused(str(e)) from e


def _brief(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
    try:
        PlanAuthoringBrief.from_yaml(_yaml_block(content))
    except ValueError as e:
        raise _Refused(f"plan_authoring_brief.yaml failed to parse: {e}") from e


def _role_tasks(role: tuple[str, ...]) -> Callable[[str, AnswerKey, dict[str, Any]], None]:
    def check(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
        try:
            proposal = ProposedRoleTasks.from_yaml(_yaml_block(content))
        except ValueError as e:
            raise _Refused(f"proposed_plan_tasks.yaml failed to parse: {e}") from e
        if proposal.proposing_role not in role:
            raise _Refused(f"proposing_role {proposal.proposing_role!r}, not {role[0]!r}")

    return check


def _guidance(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
    try:
        PlanGuidance.from_yaml(_yaml_block(content))
    except ValueError as e:
        raise _Refused(f"plan_guidance.yaml failed to parse: {e}") from e


def _json_object(content: str) -> dict[str, Any]:
    try:
        return extract_first_json_object(content)
    except JSONExtractionError as e:
        raise _Refused(f"no JSON object the handler would read: {e}") from e


def _define_done(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
    _json_object(content)


def _analysis(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
    try:
        FailureAnalysis.model_validate(_json_object(content))
    except ValueError as e:
        raise _Refused(f"the failure analysis is refused by its schema: {e}") from e


def _decision(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
    decision = _json_object(content)
    # An unknown path is not refused: the handler reads it as `abort`, a different correction.
    if decision.get("correction_path") not in _VALID_CORRECTION_PATHS:
        raise _Refused(f"correction_path {decision.get('correction_path')!r} would read as abort")
    candidate = decision.get("structural_plan_change_candidate", "none")
    if candidate not in _VALID_PLAN_CHANGE_CANDIDATES:
        raise _Refused(f"structural_plan_change_candidate {candidate!r} would read as none")


def _review(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
    if split_frontmatter(content)[0] is None:
        raise _Refused("no frontmatter, so the handler re-asks")
    try:
        front, _ = parse_frontmatter(content)
    except FrontmatterError as e:
        raise _Refused(f"its frontmatter is refused: {e}") from e
    # An invalid readiness or score is not refused: the handler substitutes its default.
    if front.get("readiness") not in _VALID_READINESS:
        raise _Refused(f"readiness {front.get('readiness')!r} would read as revise")
    try:
        score = int(front.get("sufficiency_score"))
    except (TypeError, ValueError) as e:
        raise _Refused("sufficiency_score would read as 3") from e
    if not 0 <= score <= 5:
        raise _Refused(f"sufficiency_score {score} would read as 3")


def _files(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
    if not extract_fenced_files(content):
        raise _Refused("no fenced file the handler would extract")


def _edits(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
    # A repair that edits nothing yields no file, which the handler reports as such and the
    # verifier judges; only an edit fence it can't read refuses the whole response.
    parse = parse_anchored_edits(content)
    if parse.malformed:
        raise _Refused("; ".join(f"{m.path}: {m.reason}" for m in parse.malformed))


def _document(content: str, _key: AnswerKey, _recorded: dict[str, Any]) -> None:
    if not content.strip():
        raise _Refused("an empty document")


#: Each dispatched step's check: what its handler reads from an answer. A step with no entry
#: makes no model call, or none a recording has held yet, and is named as unchecked.
CHECKS: dict[str, Callable[[str, AnswerKey, dict[str, Any]], None]] = {
    TaskType.STRATEGY_PROPOSE_INCREMENT: _proposal,
    TaskType.GOVERNANCE_PREPARE_PLAN_AUTHORING_BRIEF: _brief,
    TaskType.DEVELOPMENT_PROPOSE_PLAN_TASKS: _role_tasks(("development", "dev")),
    TaskType.QA_PROPOSE_PLAN_TASKS: _role_tasks(("qa",)),
    TaskType.STRATEGY_PROPOSE_PLAN_GUIDANCE: _guidance,
    TaskType.DEVELOPMENT_DESIGN_PLAN: _document,
    TaskType.QA_DEFINE_TEST_STRATEGY: _document,
    TaskType.GOVERNANCE_REVIEW_PLAN: _review,
    TaskType.GOVERNANCE_DEFINE_DONE: _define_done,
    TaskType.DATA_ANALYZE_FAILURE: _analysis,
    TaskType.GOVERNANCE_CORRECTION_DECISION: _decision,
    TaskType.DEVELOPMENT_DEVELOP: _files,
    TaskType.QA_TEST: _files,
    TaskType.DEVELOPMENT_CORRECTION_REPAIR: _edits,
    TaskType.QA_TEST_REPAIR: _edits,
    TaskType.BUILDER_ASSEMBLE_REPAIR: _edits,
}

#: Steps that store files with their task type but call no model: their answers are never
#: asked for, so nothing reads them.
NO_MODEL_CALL = frozenset({TaskType.GOVERNANCE_MERGE_PLAN})


def _brief_ids(script: LLMScript) -> list[str]:
    """The plan proposals and guidance must cite the brief their run's brief step wrote."""
    problems = []
    briefs = {
        k.occurrence: PlanAuthoringBrief.from_yaml(_yaml_block(a.content)).brief_id
        for k, a in script.answers.items()
        if k.task_type == TaskType.GOVERNANCE_PREPARE_PLAN_AUTHORING_BRIEF
    }
    readers: dict[str, Callable[[str], Any]] = {
        TaskType.DEVELOPMENT_PROPOSE_PLAN_TASKS: ProposedRoleTasks.from_yaml,
        TaskType.QA_PROPOSE_PLAN_TASKS: ProposedRoleTasks.from_yaml,
        TaskType.STRATEGY_PROPOSE_PLAN_GUIDANCE: PlanGuidance.from_yaml,
    }
    for key, answer in script.answers.items():
        reader = readers.get(key.task_type)
        if reader is None or key.occurrence not in briefs:
            continue
        cited = reader(_yaml_block(answer.content)).source_brief_id
        if cited != briefs[key.occurrence]:
            problems.append(
                f"{script.reference} {key}: cites brief {cited!r}, but the brief its run writes "
                f"is {briefs[key.occurrence]!r}"
            )
    return problems


def script_problems(script: LLMScript) -> list[str]:
    """Every answer of ``script`` its handler's own parse would refuse, unless the recording's
    attempt failed too, and every answer no check covers."""
    recorded = dict(script.recorded_from)
    failed = set(recorded.get(FAILED_KEY) or ())
    problems = []
    for key, answer in sorted(script.answers.items()):
        if key.task_type in NO_MODEL_CALL:
            continue
        check = CHECKS.get(key.task_type)
        if check is None:
            problems.append(f"{script.reference} {key}: no check covers {key.task_type}")
            continue
        try:
            check(answer.content, key, recorded)
        except _Refused as e:
            if str(key) not in failed:
                problems.append(f"{script.reference} {key}: {e}")
    if not problems:
        problems.extend(_brief_ids(script))
    return problems


def main(argv: list[str] | None = None) -> int:
    library = ScriptLibrary.packaged()
    names = (argv if argv is not None else sys.argv[1:]) or library.names()
    problems = [p for name in names for p in script_problems(library.get(name))]
    for problem in problems:
        print(problem)
    print(f"{len(names)} scripts checked, {len(problems)} answers the handlers would refuse")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
