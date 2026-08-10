"""Implementation Plan — control-plane artifact for dynamic build decomposition.

Originally introduced as the build task manifest in SIP-0086 §6.1. Renamed to
"implementation plan" by SIP-0092 to disambiguate from build/CI/Docker manifests
and to align with the artifact's actual role as the squad's plan for the build
phase.

The plan is produced during planning and consumed by generate_task_plan() after
gate approval. It decomposes a build into focused subtasks, each targeting a
specific component with explicit expected artifacts and acceptance criteria.

The approved plan becomes immutable after gate approval (RC-1). Correction-
driven changes are represented as plan changes (SIP-0092 M3), not mutations.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

import yaml

from squadops.cycles.acceptance_check_spec import (
    ALLOWED_SEVERITIES,
    CHECK_SPECS,
    PLAN_PROSE_CONTRACT_DIVERGENCE,
    argv_matches_safelist,
    command_safelist_names,
    normalize_route,
    reserved_keys_for,
)

if TYPE_CHECKING:
    from squadops.cycles.verification_contract import VerificationContract

# Known task types that may appear in plan tasks.
_KNOWN_BUILD_TASK_TYPES = {
    "development.develop",
    "qa.test",
    "builder.assemble",
}

# Build task types only the builder role (bob) can execute. The plan author
# must not offer these to a squad without a builder, or the LLM can author a
# task that aborts at dispatch with "No handler for capability: builder.assemble".
# The plan *validator* still accepts the full set above — it validates plans
# regardless of the authoring squad.
_BUILDER_ROLE_BUILD_TASK_TYPES = {"builder.assemble"}

# #645 lived here as `_CHECK_ENV_EXECUTABLES`, a second opinion about what a command
# check may ask for. #707 deleted it rather than resynchronising it: the safelist in
# `acceptance_check_spec` now declares the tool each form needs and refuses to import
# unless the environment provides it, so "is this tool present" and "is this argv
# permitted" are one question with one answer. Asking the safelist is also strictly
# stronger than the old test, which passed `["python", "-c", "1"]` on argv[0] alone and
# left the refusal to evaluation time, an hour of correction budget later.

# #645: node refuses these extensions outright (ERR_UNKNOWN_FILE_EXTENSION, exit 1
# before parsing) — `node --check view.jsx` fails on ANY content, correct or not
# (fay-2's killer; verified in the QA container).
#
# `.ts` added by #707. It was missing, and the omission was invisible while the tree
# held one Python stack: `node --check route.ts` exits 1 on node v20.19.2 exactly as
# `.tsx` does (measured in squadops-eve, 2026-08-10). With stack #2 in the tree this is
# the one form a TypeScript author could still reach, so the hole sat directly under
# #846's Family A — a correct plan rejected, or worse, admitted and unwinnable.
_NODE_UNPARSEABLE_SUFFIXES = (".jsx", ".tsx", ".ts")


def _importable_module_surface(paths: frozenset[str] | set[str]) -> frozenset[str]:
    """The dotted module paths the scaffold surface can ever provide.

    Path→module conversion mirrors ``ModuleImportsCheck.evaluate``
    (acceptance_checks.py) — ``backend/routes.py`` → ``backend.routes``,
    ``backend/__init__.py`` → ``backend``; non-Python files and
    non-identifier segments contribute nothing.
    """
    modules: set[str] = set()
    for path in paths:
        pure = PurePosixPath(path)
        if pure.suffix != ".py":
            continue
        parts = list(pure.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts or not all(part.isidentifier() for part in parts):
            continue
        modules.add(".".join(parts))
    return frozenset(modules)


def planner_build_task_types(*, offer_builder: bool) -> set[str]:
    """Build task types the plan-authoring prompt may offer.

    ``offer_builder`` is the caller's judgment that a builder task could
    actually execute — the squad carries the builder role AND the resolved
    config carries a ``build_profile`` (#426; squad composition alone invited
    the author to write tasks ``generate_task_plan``'s #291 guard then refused,
    a deterministically dead plan). When False, builder-only task types are
    dropped so packaging/scaffolding routes to a role that can run (e.g.
    ``development.develop``).
    """
    if offer_builder:
        return set(_KNOWN_BUILD_TASK_TYPES)
    return _KNOWN_BUILD_TASK_TYPES - _BUILDER_ROLE_BUILD_TASK_TYPES


@dataclass(frozen=True)
class TypedCheck:
    """Canonical internal form of a machine-evaluable acceptance criterion (SIP-0092 M1).

    Authored in YAML as a flat dict with check, severity, description, and
    check-specific param keys. The parser normalizes the flat shape into this
    dataclass so the evaluator framework (M1.2) doesn't need to re-parse the
    raw YAML.

    Attributes:
        check: Vocabulary name. Must be a key in CHECK_SPECS.
        params: Check-specific parameters. Equals the authored dict minus the
            reserved keys ({check, severity, description}).
        severity: One of {error, warning, info}. Defaults to ``error``.
            Per RC-9, only severity=error AND status ∈ {failed, error}
            blocks validation.
        description: Human-readable description for evidence/UI. Optional.
        id: Stable verification-contract criterion id when this check was
            resolved from a plan ``criteria_ref`` in bind mode (SIP-0098 98.3);
            empty for framing-authored checks. Carried onto evidence rows so a
            result traces back to its contract criterion. Excluded from
            ``fingerprint`` — it labels provenance, not check identity.
    """

    check: str
    params: dict
    severity: str = "error"
    description: str = ""
    id: str = ""

    def fingerprint(self) -> str:
        """Stable identity for per-criterion error counting (SIP-0092 M1.3 / RC-9b).

        Hash spans (check, severity, params) so retries against the same
        criterion share an error counter, but a tightened-acceptance plan
        change that produces a distinct param shape resets it. Description
        and id are excluded — they're prose/provenance for evidence/UI, not
        part of the criterion's identity.
        """
        canonical = json.dumps(
            {"check": self.check, "severity": self.severity, "params": self.params},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class PlanTask:
    """A single focused build subtask within the plan."""

    task_index: int
    task_type: str
    role: str
    focus: str
    description: str
    expected_artifacts: list[str] = field(default_factory=list)
    # Mixed list: prose strings stay informational; TypedCheck instances are
    # machine-evaluated by the M1.2 framework. The parser normalizes flat-YAML
    # typed entries into TypedCheck (see ImplementationPlan.from_yaml).
    acceptance_criteria: list[str | TypedCheck] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    # SIP-0098 98.3 bind mode: stable verification-contract criterion ids this
    # task binds for the contract-covered fill files in ``expected_artifacts``.
    # Framing *binds* (lists refs) rather than *authors* typed criteria for
    # covered files; dispatch resolves each ref into a TypedCheck against the
    # seeded contract. Empty in contract-less (author) mode — the default.
    criteria_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlanSummary:
    """Metadata summary for the plan."""

    total_dev_tasks: int
    total_qa_tasks: int
    total_tasks: int
    estimated_layers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImplementationPlan:
    """Structured build decomposition plan — a control-plane artifact.

    Produced at planning time by GovernanceReviewHandler. Consumed at build
    time by generate_task_plan() to materialize focused build envelopes.
    """

    version: int
    project_id: str
    cycle_id: str
    prd_hash: str
    tasks: list[PlanTask]
    summary: PlanSummary

    @classmethod
    def from_yaml(
        cls, content: str, *, enforce_command_safelist: bool = False
    ) -> ImplementationPlan:
        """Parse and validate a plan from YAML string.

        Performs structural validation: required fields, known task types,
        dependency DAG correctness, and non-empty task list.

        Policy validation (min/max subtask counts) is NOT performed here —
        that belongs in the handler/executor using resolved config.

        Args:
            content: The plan YAML document.
            enforce_command_safelist: When true, reject ``command_exit_zero``
                criteria whose argv is outside the RC-10a execution safelist
                (#422). Authoring-boundary only — leave false when re-parsing
                already-approved plans, so pre-lint plans stay loadable and
                out-of-safelist commands keep failing closed at evaluation
                time instead of being demoted to unparseable.

        Raises:
            ValueError: If the YAML is malformed or structurally invalid.
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed YAML: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Plan must be a YAML mapping")

        # Required top-level fields
        for key in ("version", "project_id", "cycle_id", "prd_hash", "tasks", "summary"):
            if key not in data:
                raise ValueError(f"Missing required field: {key}")

        tasks_data = data["tasks"]
        if not isinstance(tasks_data, list) or len(tasks_data) == 0:
            raise ValueError("Plan must contain at least one task")

        # Parse tasks
        tasks: list[PlanTask] = []
        seen_indices: set[int] = set()
        for i, td in enumerate(tasks_data):
            if not isinstance(td, dict):
                raise ValueError(f"Task {i} must be a mapping")

            for req in ("task_index", "task_type", "role", "focus", "description"):
                if req not in td:
                    raise ValueError(f"Task {i} missing required field: {req}")

            task_type = td["task_type"]
            if task_type not in _KNOWN_BUILD_TASK_TYPES:
                raise ValueError(
                    f"Task {i}: unknown task_type '{task_type}'. "
                    f"Known types: {', '.join(sorted(_KNOWN_BUILD_TASK_TYPES))}"
                )

            task_index = td["task_index"]
            if task_index in seen_indices:
                raise ValueError(f"Duplicate task_index: {task_index}")
            seen_indices.add(task_index)

            depends_on = td.get("depends_on", [])
            if not isinstance(depends_on, list):
                raise ValueError(f"Task {task_index}: depends_on must be a list")

            raw_criteria = td.get("acceptance_criteria", [])
            if not isinstance(raw_criteria, list):
                raise ValueError(f"Task {task_index}: acceptance_criteria must be a list")
            criteria = _parse_acceptance_criteria(
                raw_criteria,
                task_index,
                enforce_command_safelist=enforce_command_safelist,
            )

            raw_refs = td.get("criteria_refs", [])
            if not isinstance(raw_refs, list) or not all(isinstance(r, str) for r in raw_refs):
                raise ValueError(f"Task {task_index}: criteria_refs must be a list of strings")

            tasks.append(
                PlanTask(
                    task_index=task_index,
                    task_type=task_type,
                    role=td["role"],
                    focus=td["focus"],
                    description=td["description"],
                    expected_artifacts=td.get("expected_artifacts", []),
                    acceptance_criteria=criteria,
                    depends_on=depends_on,
                    criteria_refs=list(raw_refs),
                )
            )

        # Validate dependency references
        all_indices = {t.task_index for t in tasks}
        for task in tasks:
            for dep in task.depends_on:
                if dep not in all_indices:
                    raise ValueError(
                        f"Task {task.task_index}: depends_on references "
                        f"non-existent task_index {dep}"
                    )

        # Validate no dependency cycles
        _check_dependency_dag(tasks)

        # Parse summary
        summary_data = data["summary"]
        if not isinstance(summary_data, dict):
            raise ValueError("summary must be a mapping")
        summary = PlanSummary(
            total_dev_tasks=summary_data.get("total_dev_tasks", 0),
            total_qa_tasks=summary_data.get("total_qa_tasks", 0),
            total_tasks=summary_data.get("total_tasks", len(tasks)),
            estimated_layers=summary_data.get("estimated_layers", []),
        )

        return cls(
            version=data["version"],
            project_id=data["project_id"],
            cycle_id=data["cycle_id"],
            prd_hash=data["prd_hash"],
            tasks=tasks,
            summary=summary,
        )

    def validate_against_profile(self, profile: object) -> list[str]:
        """Check that all plan roles exist in the squad profile.

        Args:
            profile: A SquadProfile object with an ``agents`` attribute.

        Returns:
            List of validation error strings (empty = valid).
        """
        available_roles = {a.role for a in profile.agents if a.enabled}  # type: ignore[attr-defined]
        errors: list[str] = []
        for task in self.tasks:
            if task.role not in available_roles:
                errors.append(f"Task {task.task_index}: role '{task.role}' not in profile")
        return errors

    def validate_check_applicability(self, resolved_config: dict) -> list[str]:
        """#715: a ``qa.test`` task's declared artifacts must be able to satisfy the
        required check that judges them.

        ``tests_pass`` judges a qa task's emission by the runner's discovery rules, so a
        task declaring only undiscoverable artifacts (shk-4's ``test_integration.js`` on a
        Python stack) fails on **any possible content** — the declared shape, not the
        work, is the failure. The correction loop cannot fix a shape the plan forbids
        changing: shk-4 burned three rounds and ~2h before escaping via a placebo ``.js``
        stub plus an undeclared ``.py`` twin, with the planned coverage silently narrowed
        under a green verdict. Statically visible right here, at authoring time.

        **The discovery rules are the stack's, not pytest's (#846).** This asserted
        ``test_*.py``/``*_test.py`` unconditionally, so for a vitest stack *every correct
        qa task failed it* — VS's Next.js re-roll was rejected for declaring
        ``__tests__/store.test.ts``, and the remedy the message suggested ("include a
        test_*.py") would have been wrong. The stack has declared its conventions since
        SIP-0072 (``DevelopmentCapability.test_file_patterns``); nothing asked it. Reached
        through ``ScaffoldStack.dev_capability`` (#832) — an explicit declared pointer
        rather than a naming convention, which is the distinction Stage 2a exists to close.

        Verification-only tasks (``expected_artifacts: []``) are exempt — they emit
        nothing for the runner to judge. Only applies when ``tests_pass`` is actually
        required by the resolved config.

        Returns:
            List of validation error strings (empty = valid).
        """
        if "tests_pass" not in (resolved_config.get("required_checks") or ()):
            return []
        from squadops.capabilities.dev_capabilities import (
            matches_test_file_patterns,
            test_file_patterns_for,
        )

        patterns = test_file_patterns_for(resolved_config)
        errors: list[str] = []
        for task in self.tasks:
            if task.task_type != "qa.test" or not task.expected_artifacts:
                continue
            if any(matches_test_file_patterns(p, patterns) for p in task.expected_artifacts):
                continue
            shown = " / ".join(patterns)
            errors.append(
                f"Task {task.task_index} ({task.focus}): qa.test declares "
                f"{task.expected_artifacts} but no file this stack's test runner "
                f"discovers ({shown}) — the required tests_pass check judges this task's "
                f"emission by those conventions, so it fails for any possible content. "
                f"Name at least one expected artifact matching {shown}, or make this a "
                f"verification-only task (expected_artifacts: [])"
            )
        return errors

    def validate_build_config(self, resolved_config: dict) -> list[str]:
        """#426: builder tasks require a configured ``build_profile``.

        The dispatch-time #291 guard already refuses such a plan — but only
        after the gate approved it and a full implementation run was admitted.
        This is the same rule at the gate seam, where a rejection costs a
        re-roll instead of a run.
        """
        if resolved_config.get("build_profile"):
            return []
        offending = [
            task.task_index
            for task in self.tasks
            if task.task_type in _BUILDER_ROLE_BUILD_TASK_TYPES
        ]
        if not offending:
            return []
        return [
            f"Task(s) {', '.join(str(i) for i in offending)}: builder task authored but no "
            "build_profile is configured — the plan cannot execute (a builder must not "
            "assemble for an assumed stack). Set build_profile in the cycle request "
            "profile, or author without builder tasks"
        ]

    def _regex_on_source_criteria(self):
        """Yield ``(task, criterion, target)`` for every ``regex_match`` criterion
        that targets a non-document file — the #464 violation shared by the fatal
        scope check and the soft-violation collector."""
        from squadops.cycles.acceptance_check_spec import regex_target_is_document

        for task in self.tasks:
            for criterion in task.acceptance_criteria:
                if not isinstance(criterion, TypedCheck) or criterion.check != "regex_match":
                    continue
                target = criterion.params.get("file", "")
                if not regex_target_is_document(target):
                    yield task, criterion, target

    @staticmethod
    def _regex_on_source_message(task: PlanTask, target: str) -> str:
        return (
            f"Task {task.task_index} ({task.focus}): regex_match on source "
            f"file {target!r} — regex criteria are allowed only on document "
            "artifacts (.md/.txt/.rst); verify source files with "
            "endpoint_defined/import_present/function_defined/command_exit_zero "
            "or the behavioral checks. To assert a file defines functions "
            "(e.g. pytest test_*), use function_defined (#464)"
        )

    def validate_criteria_scope(self) -> list[str]:
        """#464: regex_match criteria may only target document artifacts.

        Regexes against source files prescribe another roll's stylistic
        choices (quote style, identifier names) and have twice produced
        criteria unwinnable by correct code (attempts 3.9/3.10 of the
        Phase-0.5 spike). Prose guidance reduces the frequency; this is the
        mechanical guard. Prose criteria and unparseable rows are out of
        scope here (non-blocking per #420).

        Only ``severity=error`` violations reject the plan. A warning/info-severity
        regex-on-source is a soft authoring slip that cannot block a build at
        execution (RC-9), so it must not kill the cycle at plan validation either —
        those are surfaced by ``soft_criteria_violations`` for a logged, tolerated
        pass instead.

        Returns:
            List of validation error strings (empty = valid).
        """
        return [
            self._regex_on_source_message(task, target)
            for task, criterion, target in self._regex_on_source_criteria()
            if criterion.severity == "error"
        ]

    def validate_command_checks(self) -> list[str]:
        """#645: an error-severity command check must be executable where checks run.

        Two deterministic classes from the FAY measurement window, both provable
        at authoring time without running anything:

        - a form the check environment cannot run (fay-2's ``tsc``) — the spawn fails
          on every attempt until the correction budget is spent;
        - ``node`` pointed at a ``.jsx``/``.tsx``/``.ts`` file — node refuses the
          extension before parsing (``ERR_UNKNOWN_FILE_EXTENSION``), so the check
          fails on ANY content, correct or not.

        #707 replaced the first test's private executable list with the safelist itself.
        That is not a simplification for its own sake: the two lists recommended disjoint
        sets in their rejection messages, so an author who took one gate's advice was
        refused by the other. It is also stricter — an argv sharing a provisioned argv[0]
        with a legitimate form (``python -c``) used to pass here and fail at evaluation.

        Only ``severity=error`` rejects (RC-9: a warning cannot block a build, so
        a doomed warning check costs nothing — fay-6 and fay-8 both carried one
        harmlessly). Non-list/odd-shaped argv is the parser's concern, not ours.
        """
        errors: list[str] = []
        for task in self.tasks:
            for criterion in task.acceptance_criteria:
                if not isinstance(criterion, TypedCheck):
                    continue
                if criterion.check != "command_exit_zero" or criterion.severity != "error":
                    continue
                argv = criterion.params.get("argv") or []
                if not argv or not all(isinstance(a, str) for a in argv):
                    continue
                if not argv_matches_safelist(argv):
                    errors.append(
                        f"Task {task.task_index} ({task.focus}): command_exit_zero argv "
                        f"{argv} is not a form the check environment can run — the check "
                        f"can never execute, so no repair can fix it and the task fails "
                        f"identically on every correction attempt. Use one of: "
                        f"{'; '.join(command_safelist_names())} — or a named check"
                    )
                elif argv[0] == "node" and any(
                    arg.endswith(_NODE_UNPARSEABLE_SUFFIXES) for arg in argv[1:]
                ):
                    errors.append(
                        f"Task {task.task_index} ({task.focus}): command_exit_zero runs "
                        f"node against a .jsx/.tsx/.ts file — node refuses the extension "
                        f"before parsing (ERR_UNKNOWN_FILE_EXTENSION), so this fails on "
                        f"any content, correct or not. TypeScript and JSX are compiled by "
                        f"the frontend build, which type-checks them; drop the check or "
                        f"target plain .js"
                    )
        return errors

    def validate_expected_artifact_shapes(self) -> list[str]:
        """fay-9: an ``expected_artifacts`` entry must be a file, not a directory.

        The presence check compares entries against emitted artifact *names*; a
        directory entry (``backend/tests/``) can never appear there, so the task
        fails on every attempt — fay-9 went 16/17 with frontend built, suite
        passing, and both probes green, rejected solely on this shape. A
        verification-only task declares ``[]``.
        """
        errors: list[str] = []
        for task in self.tasks:
            for name in task.expected_artifacts:
                if isinstance(name, str) and name.endswith("/"):
                    errors.append(
                        f"Task {task.task_index} ({task.focus}): expected artifact "
                        f"{name!r} is a directory — expected_artifacts are the FILES "
                        f"the task emits, and the presence check reads a directory as "
                        f"a permanently missing file. A verification-only task "
                        f"declares expected_artifacts: []"
                    )
        return errors

    def validate_unique_expected_artifacts(self) -> list[str]:
        """#673: an artifact path may appear in only one task's ``expected_artifacts``.

        Expected artifacts are load-bearing task identity — they drive write
        authorization, repair scoping (#650) and missing-artifact locus routing
        (#665) — so a dual claim quietly aliases two tasks onto one file's fate:
        a failing non-producing claimant aims its repair at a file another task
        owns, and if both produce, last-wins ordering silently decides whose
        emission ships (the #389 class fay-14's repair chain replayed).

        fay-18's approved framing-2 plan carried the shape live: qa task 5
        declared dev task 4's ``backend/tests/test_runs.py`` with an explicit
        do-not-produce instruction. The dice were kind (zero corrections); the
        hazard rode anyway. There is no legitimate dual-claim the artifact-less
        form doesn't cover, so no warn tier — the legal shape for a
        verification-only task is ``expected_artifacts: []`` plus
        ``criteria_refs`` (the fay-13 framing-2 receipt).

        Plan-wide cross-task pass — the first of its kind in this family; the
        per-task rules above stay per-task. A path repeated *within* one task
        is a benign echo, not a claim conflict, and is not reported here.
        """
        claimants: dict[str, list[PlanTask]] = {}
        for task in self.tasks:
            seen_in_task: set[str] = set()
            for name in task.expected_artifacts:
                if not isinstance(name, str) or name in seen_in_task:
                    continue
                seen_in_task.add(name)
                claimants.setdefault(name, []).append(task)

        return [
            f"Tasks {' and '.join(f'{t.task_index} ({t.focus})' for t in tasks)} both declare "
            f"expected artifact {name!r} — expected artifacts are load-bearing task identity "
            f"(write authorization, repair scoping, missing-artifact routing), so a dual claim "
            f"aims repairs at another task's file and lets last-wins ordering decide whose "
            f"emission ships. Exactly one task owns each file; a verification-only task "
            f"declares expected_artifacts: [] and binds acceptance via criteria_refs"
            for name, tasks in claimants.items()
            if len(tasks) > 1
        ]

    def lint_prose_contract_conflicts(self, contract: VerificationContract) -> list[str]:
        """pf-31 Fix A3: WARNING-only lint for prose that contradicts bound criteria.

        The two observed poisonings were gate-visible in the plan text: pf-31's
        description said ``/runs/{run_id}/join`` where the bound ``endpoint_defined``
        pins ``{id}`` (all 7 repairs followed the prose and were rejected over that
        one token); pf-30's prose said ``DELETE /runs/{run_id}/leave`` vs the
        contract's ``POST``. This flags path-parameter names and methods used in a
        task's description/prose criteria that conflict with the task's resolved
        ``endpoint_defined`` expectations. Heuristic and conservative: warnings for
        the gate reviewer's eyes (surfaced via log at dispatch validation), never a
        rejection — the reverted #552 lesson bars new hard gates on prompt prose.
        """
        import re as _re

        from squadops.cycles.task_plan import resolve_contract_refs

        # #629 (A6/D2): the ADVISORY status-code rule — its own identity so its
        # evidence quality never launders into the blocking suite check.
        warnings: list[str] = _prose_status_divergence_warnings(self.tasks, contract)
        for task in self.tasks:
            if not task.criteria_refs:
                continue
            endpoint_paths: list[str] = []
            for check in resolve_contract_refs(list(task.criteria_refs), contract):
                if check.check == "endpoint_defined":
                    for item in check.params.get("methods_paths", []) or []:
                        endpoint_paths.append(
                            f"{item[0]} {item[1]}"
                            if isinstance(item, (list, tuple)) and len(item) == 2
                            else str(item)
                        )
            if not endpoint_paths:
                continue
            allowed_params = {m for p in endpoint_paths for m in _re.findall(r"\{(\w+)\}", p)}
            prose = " ".join([task.description, *[str(c) for c in task.acceptance_criteria]])
            for token in sorted(set(_re.findall(r"/\S*?\{(\w+)\}", prose))):
                if token not in allowed_params:
                    warnings.append(
                        f"Task {task.task_index} ({task.focus}): prose uses path "
                        f"parameter {{{token}}} but the bound contract paths use "
                        f"{sorted(allowed_params)} — prose-steered emissions will "
                        f"fail endpoint_defined (pf-31 class)"
                    )
            normalized = {
                (m.split()[0].upper(), _re.sub(r"\{\w+\}", "{}", m.split(maxsplit=1)[1]))
                for m in endpoint_paths
                if " " in m
            }
            for method, path in _re.findall(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)", prose):
                norm = _re.sub(r"\{\w+\}", "{}", path).rstrip(".,;:)")
                if (
                    any(p == norm for _m, p in normalized)
                    and (method.upper(), norm) not in normalized
                ):
                    warnings.append(
                        f"Task {task.task_index} ({task.focus}): prose says "
                        f"{method} {path} but the bound contract requires a "
                        f"different method for that path (pf-30 DELETE-/leave class)"
                    )
        return warnings

    def validate_criteria_refs(self, contract: VerificationContract) -> list[str]:
        """SIP-0098 §6.3: bind-mode plan validation against the seeded contract.

        In bind mode a plan *binds* the contract's acceptance by id rather than
        *authoring* its own typed criteria for contract-covered fill files. This
        enforces that discipline, returning one error string per defect (empty =
        valid). Callers surface the list at the existing #464/#473 seams alongside
        ``validate_criteria_scope`` — net-a (dispatch) raises, net-b (gate) records
        a system rejection. Contract-less mode never calls this (no contract to
        bind against), so today's plans are unaffected.

        Three rejection classes (§6.3, acceptance bullet 3):

        1. **Unresolvable ref** — a ``criteria_ref`` naming no contract criterion id.
        2. **Missing coverage** — a task produces a contract-covered fill file but
           does not bind *all* its interface+implementation criteria (silent
           descoping of verification is the #439 lesson at the criteria level).
        3. **Authored-on-covered** — a task authors a typed criterion targeting a
           contract-covered fill file (bind by id; do not author). Prose criteria
           and plan-introduced document regexes remain legal.
        """
        errors: list[str] = []
        index = contract.criterion_index()
        covered = contract.covered_fill_paths()

        for task in self.tasks:
            bound = set(task.criteria_refs)

            # 1. every ref must resolve.
            for ref in task.criteria_refs:
                if ref not in index:
                    errors.append(
                        f"Task {task.task_index} ({task.focus}): criteria_ref {ref!r} "
                        f"does not resolve against the seeded verification contract"
                    )

            # 2. every contract-covered fill file this task produces must bind all
            #    of its interface + implementation criteria (no silent descoping).
            for artifact in task.expected_artifacts:
                if artifact not in covered:
                    continue
                missing = [
                    rid for rid in contract.required_ref_ids_for(artifact) if rid not in bound
                ]
                if missing:
                    errors.append(
                        f"Task {task.task_index} ({task.focus}): fill file {artifact!r} "
                        f"is contract-covered but does not bind its criteria "
                        f"{sorted(missing)} — bind every interface+implementation ref "
                        f"(no silent descoping of verification)"
                    )

        # 3. authored typed criteria targeting a covered file are rejected — but
        #    only at severity=error. A warning/info-severity authored check on a
        #    covered file is a soft slip (the contract owns the file; RC-9: a
        #    warning can't block a build), tolerated + logged via
        #    soft_criteria_violations rather than killing the whole cycle.
        errors.extend(
            self._authored_on_covered_message(task, criterion, target)
            for task, criterion, target in self._authored_on_covered_criteria(contract)
            if criterion.severity == "error"
        )

        return errors

    def with_contract_criteria_bound(
        self, contract: VerificationContract
    ) -> tuple[ImplementationPlan, list[str]]:
        """Deterministically bind every contract-covered fill file's criteria (#509).

        Criterion linkage previously rode the framing LLM's plan authoring: a
        roll that under-listed ``criteria_refs`` either under-counted coverage
        (pre-descoping-validator) or burned a framing re-roll on an auto-
        rejection (pf-54 run 2 died exactly there, one draw from cycle death).
        The contract already states the authoritative answer — this puts it in
        the plan instead of asking the author to transcribe it.

        For each task, each expected artifact that is a contract-covered fill
        file has its interface+implementation criterion ids unioned into
        ``criteria_refs`` (authored refs keep their order; missing ids append
        sorted). Idempotent; a fully-bound plan returns unchanged content.
        ``validate_criteria_refs`` stays in force behind this as the guard —
        binding makes its descoping rule vacuous, not absent.

        Returns:
            (bound_plan, notes) — one human-readable note per task that gained
            refs, for the plan-validation log and the gate record.
        """
        covered = contract.covered_fill_paths()
        notes: list[str] = []
        new_tasks: list[PlanTask] = []
        for task in self.tasks:
            missing: list[str] = []
            bound = set(task.criteria_refs)
            for artifact in task.expected_artifacts:
                if artifact not in covered:
                    continue
                for rid in contract.required_ref_ids_for(artifact):
                    if rid not in bound:
                        bound.add(rid)
                        missing.append(rid)
            if missing:
                new_tasks.append(
                    dataclasses.replace(task, criteria_refs=[*task.criteria_refs, *sorted(missing)])
                )
                notes.append(f"Task {task.task_index} ({task.focus}): auto-bound {sorted(missing)}")
            else:
                new_tasks.append(task)
        if not notes:
            return self, []
        return dataclasses.replace(self, tasks=new_tasks), notes

    def validate_qa_artifact_ownership(self, contract: VerificationContract) -> list[str]:
        """pf-39: a ``qa.test`` task may not declare scaffold- or dev-owned files as
        its ``expected_artifacts``.

        Write authorization already refuses these at *emission* time
        (``unauthorized_slot_emission``), so a plan that declares them admits a task
        that provably cannot produce its own outputs. The cost is not the wasted task:
        a correction repair is scoped to the **failing task's** expected artifacts, so
        when such a task fails the repair is aimed at files that were never the defect.
        In pf-39 a ``qa.test`` task declared the three view fill slots; the analyzer
        correctly diagnosed a backend status-code defect in another task's file, and
        the repair rewrote the views instead — one whole correction attempt that could
        not have fixed anything.

        Same referent as write authorization (the contract's frozen + fill surfaces),
        applied at authoring time instead of emission time. Documents and test files
        are unaffected — only files the contract says someone else owns are rejected.

        Returns:
            List of validation error strings (empty = valid).
        """
        owned: dict[str, str] = {ff.path: "frozen (scaffold-owned)" for ff in contract.frozen_files}
        owned.update({ff.path: "a fill slot (dev-owned)" for ff in contract.fill_files})

        return [
            f"Task {task.task_index} ({task.focus}): qa.test declares expected artifact "
            f"{artifact!r}, which is {owned[artifact]} — write authorization refuses it at "
            f"emission, and a repair scoped to this task would target the wrong files. "
            f"QA tasks own their test files only"
            for task in self.tasks
            if task.task_type == "qa.test"
            for artifact in task.expected_artifacts
            if artifact in owned
        ]

    def validate_frozen_artifact_ownership(self, contract: VerificationContract) -> list[str]:
        """#658: no task, any role, may declare a frozen-surface file as an
        ``expected_artifact``.

        Frozen files are scaffold-owned: scaffold enforcement restores their
        bytes at emission, so a task claiming one can never satisfy its own
        expected artifacts through an accepted write, and a repair scoped to
        it aims at files that were never the defect. The qa.test rule above
        already covers this for qa tasks (alongside fill slots); this rule
        closes the asymmetry for every other role — fay-12 shipped a
        ``development.develop`` task claiming the frozen ``frontend/src/api.js``
        with prose-only criteria, which slipped between the qa net and the
        typed-criteria frozen-file rule.

        Fill slots are deliberately NOT checked here: they are dev-owned
        deliverables, and dev tasks claim them by design.

        Returns:
            List of validation error strings (empty = valid).
        """
        frozen = {ff.path for ff in contract.frozen_files}

        return [
            f"Task {task.task_index} ({task.focus}): {task.task_type} declares expected "
            f"artifact {artifact!r}, which is frozen (scaffold-owned) — no task may claim "
            f"a frozen file as a deliverable; scaffold enforcement restores frozen bytes "
            f"at emission, so the task cannot satisfy its expected artifacts and a repair "
            f"scoped to it would target the wrong files"
            for task in self.tasks
            if task.task_type != "qa.test"
            for artifact in task.expected_artifacts
            if artifact in frozen
        ]

    def validate_module_existence(self, contract: VerificationContract) -> list[str]:
        """#671: an error-severity ``import_present`` may not require a module the
        scaffold surface provably cannot provide.

        fay-17's framing-2 plan authored a blocking ``import_present: module:
        app.routes`` — the ``app`` package does not exist (the scaffold root is
        ``backend``, the pf-26 package-root class). Satisfying the check
        guarantees a collection-dead suite; omitting the import fails
        acceptance. Contradictory by construction, and provable at authoring
        time from the contract's file surface.

        Two rejected classes, both zero-false-positive on third-party imports:

        - a module under a scaffold package root that the closed surface does
          not contain (``backend.handlers`` — the scaffold owns everything
          under ``backend/``, so absence is proof);
        - a real scaffold module leaf under a package root that does not exist
          (``app.routes``, ``src.backend.main`` — the wrong-root hallucination).

        Everything else is out of scope by design: relative specs (``.errors``
        — the contract authors this form itself) and dotless specs (``errors``
        — #441 author-intent-relative semantics) validate at evaluation depth
        we don't have here, and dotted third-party modules
        (``fastapi.testclient``) are legitimately outside the scaffold surface.

        ``harness_boundary.entry_modules`` is deliberately NOT validated:
        entry modules are a FORBIDDEN-import list (the check fails a test that
        imports one), and the scaffold's own convention seeds nonexistent
        wrong-guess traps (``app.main``, ``main`` — ``_HARNESS_ENTRY_MODULES``)
        on purpose. A nonexistent entry there is protective, not doomed.

        Only ``severity=error`` rejects (RC-9, same split as the #645 rules).
        """
        surface = _importable_module_surface(
            {ff.path for ff in contract.frozen_files} | {ff.path for ff in contract.fill_files}
        )
        roots = {module.split(".", 1)[0] for module in surface}
        leaves = {module.rsplit(".", 1)[-1] for module in surface}

        errors: list[str] = []
        for task in self.tasks:
            for criterion in task.acceptance_criteria:
                if not isinstance(criterion, TypedCheck):
                    continue
                if criterion.check != "import_present" or criterion.severity != "error":
                    continue
                module = criterion.params.get("module")
                if not isinstance(module, str) or module.startswith(".") or "." not in module:
                    continue  # relative / dotless / malformed: out of scope (see docstring)
                if module in surface:
                    continue
                root, leaf = module.split(".", 1)[0], module.rsplit(".", 1)[-1]
                if root not in roots and leaf not in leaves:
                    continue  # third-party shaped (fastapi.testclient): out of scope
                errors.append(
                    f"Task {task.task_index} ({task.focus}): import_present requires "
                    f"module {module!r}, which the scaffold surface does not provide — "
                    f"the import can never succeed, so the check fails on any content "
                    f"and satisfying it kills the suite at collection instead. The "
                    f"importable scaffold modules are {sorted(surface)}"
                )
        return errors

    def _authored_on_covered_criteria(self, contract: VerificationContract):
        """Yield ``(task, criterion, target)`` for every authored ``TypedCheck``
        whose target file is contract-covered (§6.3 rule 3) — shared by the fatal
        refs check and the soft-violation collector."""
        covered = contract.covered_fill_paths()
        for task in self.tasks:
            for criterion in task.acceptance_criteria:
                if not isinstance(criterion, TypedCheck):
                    continue
                target = criterion.params.get("file", "")
                if target in covered:
                    yield task, criterion, target

    @staticmethod
    def _authored_on_covered_message(task: PlanTask, criterion: TypedCheck, target: str) -> str:
        return (
            f"Task {task.task_index} ({task.focus}): authored typed criterion "
            f"{criterion.check!r} targets contract-covered file {target!r} — "
            f"bind the contract criteria by id (criteria_refs); do not author "
            f"typed criteria for covered files"
        )

    def soft_criteria_violations(self, contract: VerificationContract | None = None) -> list[str]:
        """Warning/info-severity structural criteria violations that are TOLERATED,
        not rejected — regex-on-source (#464) and, when a contract is given (bind
        mode), authored-on-covered (§6.3). Each note is prefixed with the criterion's
        severity so the caller can log an audit trail; this method never rejects.

        Error-severity violations are NOT returned here — they stay fatal in
        ``validate_criteria_scope`` / ``validate_criteria_refs``. RC-9 anchors the
        split: a warning check cannot block a build at execution, so it must not
        kill the cycle at plan validation either.
        """
        notes: list[str] = [
            f"tolerated (severity={criterion.severity}): "
            + self._regex_on_source_message(task, target)
            for task, criterion, target in self._regex_on_source_criteria()
            if criterion.severity != "error"
        ]
        if contract is not None:
            notes.extend(
                f"tolerated (severity={criterion.severity}): "
                + self._authored_on_covered_message(task, criterion, target)
                for task, criterion, target in self._authored_on_covered_criteria(contract)
                if criterion.severity != "error"
            )
        return notes

    def to_dict(self) -> dict:
        """Serialize to dict for YAML/JSON transport.

        TypedCheck entries in ``acceptance_criteria`` are serialized as flat
        authored-form mappings (params spread to top level alongside check /
        severity / description), matching the on-disk YAML schema parsed by
        ``from_yaml``. This makes round-trip ``from_yaml → to_dict → safe_dump
        → from_yaml`` a stable identity, which is load-bearing for the
        canonical-hashing helper SIP-0092 M3 introduces.
        """
        result = dataclasses.asdict(self)
        for task_dict, task in zip(result["tasks"], self.tasks, strict=True):
            task_dict["acceptance_criteria"] = [
                _serialize_acceptance_criterion(c) for c in task.acceptance_criteria
            ]
        return result


_PROSE_METHOD_PATH_RE = r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)"


def _prose_status_divergence_warnings(
    tasks: list[PlanTask], contract: VerificationContract
) -> list[str]:
    """#629 (1.5 A6/D2) — ``plan_prose_contract_divergence``: the ADVISORY half.

    **Comparable prose** (A6's precondition for the rule existing at all, stated
    here): a ``METHOD /path`` token followed on the same line — before any next
    endpoint token — by an explicit 3-digit HTTP status. **The bound contract is
    the authoritative artifact.** Prose short of that shape is not comparable
    and is never flagged; the flag is a warning row on the existing
    never-rejects channel (the reverted-#552 rule bars hard gates on prose).
    Promotion to blocking requires a later registry change with proof of a
    deterministic representation (the D2 ruling) — until then this identity's
    lower evidence quality stays out of the blocking suite check.

    Same {param}-name-insensitive path normalization as the pf-31 rules: pf-54's
    plan prose said "returns 200" beside endpoints whose probes pinned 201.
    """
    import re as _re

    pinned = contract.pinned_endpoint_statuses()
    if not pinned:
        return []
    allowed = set(contract.allowed_error_statuses())
    norm_pinned: dict[tuple[str, str], set[int]] = {}
    for (method, path), statuses in pinned.items():
        key = (method, _re.sub(r"\{\w+\}", "{}", path))
        norm_pinned.setdefault(key, set()).update(statuses)

    warnings: list[str] = []
    for task in tasks:
        prose = "\n".join([task.description, *[str(c) for c in task.acceptance_criteria]])
        for line in prose.splitlines():
            matches = list(_re.finditer(_PROSE_METHOD_PATH_RE, line))
            for i, m in enumerate(matches):
                method, raw_path = m.group(1).upper(), m.group(2).rstrip(".,;:)")
                norm = _re.sub(r"\{\w+\}", "{}", normalize_route(raw_path))
                statuses = norm_pinned.get((method, norm))
                if not statuses:
                    continue
                # the status must belong to THIS token: same line, before the
                # next endpoint token — a neighbour's status is not comparable
                tail_end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
                status_match = _re.search(r"\b([1-5]\d{2})\b", line[m.end() : tail_end])
                if status_match is None:
                    continue
                status = int(status_match.group(1))
                if status not in statuses | allowed:
                    warnings.append(
                        f"{PLAN_PROSE_CONTRACT_DIVERGENCE}: Task {task.task_index} "
                        f"({task.focus}): prose says {method} {raw_path} → {status} but "
                        f"the contract pins {sorted(statuses | allowed)} — the contract "
                        f"is authoritative (#629)"
                    )
    return warnings


def resolve_contract_refs(
    criteria_refs: list[str], contract: VerificationContract
) -> list[TypedCheck]:
    """Resolve bind-mode ``criteria_refs`` into ``TypedCheck``s (SIP-0098 §6.3 dispatch).

    The #420 enrichment seam for contract binding: each ref names a contract
    criterion; this builds the executable ``TypedCheck`` for it, stamped with the
    stable criterion ``id`` and its target file (the contract's owning ``fill_files``
    key — contract criteria imply the file rather than inlining it). The resulting
    checks are merged into the dispatched task's ``acceptance_criteria`` so evaluation,
    correction, and retest operate on them unchanged.

    Only ``interface``/``implementation`` criteria (the typed-acceptance vocabulary)
    materialize here; a ref to a behavioral framework check (``frontend_build`` /
    ``tests_pass``) is skipped — those run through the qa/build handlers, not the
    typed-acceptance path (98.4). An unresolvable ref is skipped too: plan validation
    already rejects it (``validate_criteria_refs``), so this stays a pure materializer.
    """
    index = contract.criterion_index()
    checks: list[TypedCheck] = []
    for ref in criteria_refs:
        entry = index.get(ref)
        if entry is None:
            continue
        criterion, owning_path = entry
        if criterion.check not in CHECK_SPECS:
            continue  # behavioral check bound by ref — materialized elsewhere (98.4)
        spec = CHECK_SPECS[criterion.check]
        params = dict(criterion.params)
        if owning_path and ("file" in spec.required_params or "file" in spec.path_params):
            params.setdefault("file", owning_path)
        checks.append(TypedCheck(check=criterion.check, params=params, id=criterion.id))
    return checks


def _check_dependency_dag(tasks: list[PlanTask]) -> None:
    """Validate that task dependencies form a DAG (no cycles).

    Raises:
        ValueError: If a dependency cycle is detected.
    """
    # Build adjacency list
    adj: dict[int, list[int]] = {t.task_index: list(t.depends_on) for t in tasks}
    visited: set[int] = set()
    in_stack: set[int] = set()

    def _visit(node: int) -> None:
        if node in in_stack:
            raise ValueError(f"Dependency cycle detected involving task_index {node}")
        if node in visited:
            return
        in_stack.add(node)
        for dep in adj.get(node, []):
            _visit(dep)
        in_stack.remove(node)
        visited.add(node)

    for task in tasks:
        _visit(task.task_index)


def _serialize_acceptance_criterion(c: str | TypedCheck) -> str | dict:
    """Inverse of the parser's flat-YAML normalization.

    str entries pass through unchanged. TypedCheck entries become flat dicts
    with the wrapper keys (check, severity, description) at top level next to
    the check-specific params.
    """
    if isinstance(c, str):
        return c
    flat: dict = {"check": c.check}
    flat.update(c.params)
    flat["severity"] = c.severity
    if c.description:
        flat["description"] = c.description
    if c.id:
        flat["id"] = c.id
    return flat


def _parse_acceptance_criteria(
    raw: list,
    task_index: int,
    *,
    enforce_command_safelist: bool = False,
) -> list[str | TypedCheck]:
    """Parse a mixed acceptance_criteria list per SIP-0092 M1.

    Accepts:
        - str items: kept as-is (informational prose)
        - dict items: normalized into TypedCheck per the flat-YAML rule
          (params = dict minus reserved keys {check, severity, description})

    Authoring-time rejections (RC-11):
        - Unknown check name (not in CHECK_SPECS).
        - Missing required param per CHECK_SPECS[check].required_params.
        - Wrong-type param per CHECK_SPECS[check].param_types.
        - Unknown param key (not in required_params ∪ optional_params).
        - Unknown severity value (not in {error, warning, info}).
        - Path-typed param value containing absolute path or '..' traversal
          (cheap pre-eval rejection; full chrooting still applies at
          evaluation time per RC-10).
        - When ``enforce_command_safelist`` is set (authoring boundary only,
          #422): ``command_exit_zero`` argv outside the RC-10a execution
          safelist, or with non-string items. Such a command can never
          execute, so accepting it authors a run that is guaranteed to die
          at evaluation.

    Returns:
        Mixed list of str and TypedCheck instances, preserving authored order.
    """
    parsed: list[str | TypedCheck] = []
    for j, item in enumerate(raw):
        if isinstance(item, str):
            parsed.append(item)
            continue

        if not isinstance(item, dict):
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}]: "
                f"each entry must be a string (informational) or mapping (typed)"
            )

        # Typed check — must declare which check
        if "check" not in item:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}]: "
                f"typed criterion missing required key 'check'"
            )
        check_name = item["check"]
        if not isinstance(check_name, str):
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}]: 'check' must be a string"
            )
        if check_name not in CHECK_SPECS:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}]: "
                f"unknown check '{check_name}'. "
                f"Known checks: {', '.join(sorted(CHECK_SPECS))}"
            )

        spec = CHECK_SPECS[check_name]

        # Severity
        severity = item.get("severity", "error")
        if severity not in ALLOWED_SEVERITIES:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}] "
                f"({check_name}): unknown severity '{severity}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_SEVERITIES))}"
            )

        # Description
        description = item.get("description", "")
        if not isinstance(description, str):
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}] "
                f"({check_name}): 'description' must be a string"
            )

        # Params = item minus reserved keys
        reserved = reserved_keys_for(check_name)
        params = {k: v for k, v in item.items() if k not in reserved}

        # Required params
        missing = spec.required_params - set(params)
        if missing:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}] "
                f"({check_name}): missing required param(s): "
                f"{', '.join(sorted(missing))}"
            )

        # Unknown params
        allowed_params = spec.required_params | spec.optional_params
        unknown = set(params) - allowed_params
        if unknown:
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}] "
                f"({check_name}): unknown param(s): "
                f"{', '.join(sorted(unknown))}. "
                f"Allowed: {', '.join(sorted(allowed_params))}"
            )

        # Param types
        for key, value in params.items():
            expected = spec.param_types.get(key)
            if expected is None:
                continue  # spec didn't declare a type; tolerated
            if not isinstance(value, expected):
                expected_name = (
                    expected.__name__
                    if isinstance(expected, type)
                    else " | ".join(t.__name__ for t in expected)
                )
                raise ValueError(
                    f"Task {task_index}.acceptance_criteria[{j}] "
                    f"({check_name}): param '{key}' must be {expected_name}, "
                    f"got {type(value).__name__}"
                )

        # Path-traversal pre-eval rejection
        for path_key in spec.path_params:
            if path_key in params:
                _reject_unsafe_path(params[path_key], path_key, task_index, j, check_name)

        # Authoring-time command-safelist lint (#422)
        if enforce_command_safelist and check_name == "command_exit_zero":
            argv = params["argv"]
            if not all(isinstance(a, str) for a in argv):
                raise ValueError(
                    f"Task {task_index}.acceptance_criteria[{j}] "
                    f"(command_exit_zero): every argv item must be a string"
                )
            if not argv_matches_safelist(argv):
                raise ValueError(
                    f"Task {task_index}.acceptance_criteria[{j}] "
                    f"(command_exit_zero): command {argv!r} is not in the "
                    f"execution safelist and can never run. Use one of: "
                    f"{'; '.join(command_safelist_names())}"
                )

        criterion_id = item.get("id", "")
        if not isinstance(criterion_id, str):
            raise ValueError(
                f"Task {task_index}.acceptance_criteria[{j}] ({check_name}): 'id' must be a string"
            )

        parsed.append(
            TypedCheck(
                check=check_name,
                params=params,
                severity=severity,
                description=description,
                id=criterion_id,
            )
        )

    return parsed


def _reject_unsafe_path(
    value: object, key: str, task_index: int, criterion_index: int, check_name: str
) -> None:
    """Cheap pre-evaluation rejection of obviously unsafe paths.

    Full chrooting and symlink rejection still happens at evaluation time
    (M1.2, RC-10). This catches authoring errors at parse time so the squad
    sees feedback at the gate rather than at hour 2 of build.
    """
    if not isinstance(value, str):
        return  # type validation already handled by param_types check
    if value.startswith("/") or value.startswith("\\"):
        raise ValueError(
            f"Task {task_index}.acceptance_criteria[{criterion_index}] "
            f"({check_name}): {key}={value!r} is absolute "
            f"(must be workspace-relative)"
        )
    parts = value.replace("\\", "/").split("/")
    if ".." in parts:
        raise ValueError(
            f"Task {task_index}.acceptance_criteria[{criterion_index}] "
            f"({check_name}): {key}={value!r} contains '..' traversal"
        )
