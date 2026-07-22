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
from typing import TYPE_CHECKING

import yaml

from squadops.cycles.acceptance_check_spec import (
    ALLOWED_SEVERITIES,
    CHECK_SPECS,
    argv_matches_safelist,
    command_safelist_names,
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


def planner_build_task_types(*, has_builder: bool) -> set[str]:
    """Build task types the plan-authoring prompt may offer for a given squad.

    Returns the full known set when the squad has a builder role; otherwise
    drops builder-only task types so packaging/scaffolding is routed to a role
    the squad actually has (e.g. ``development.develop``) instead of producing a
    ``builder.assemble`` task no agent can handle.
    """
    if has_builder:
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
