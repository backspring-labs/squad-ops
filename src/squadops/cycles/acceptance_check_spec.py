"""Acceptance check specification registry — single source of truth (SIP-0092 M1).

This module defines the contract for every typed acceptance check vocabulary
entry. It is consumed by:

- The parser in ``implementation_plan.py`` (RC-11 authoring-time validation)
  to reject unknown check names, missing required params, wrong types, and
  malformed values at plan-parse time.
- The evaluator framework in ``acceptance_checks.py`` (M1.2, not yet shipped)
  to declare the per-check evaluator implementation against the same spec.

Adding a new check means adding one entry to ``CHECK_SPECS`` here plus one
evaluator class registration in M1.2 — no separate ``_KNOWN_CHECKS`` table
that could drift between parser and evaluator. This is the registry-of-record
going forward.

Per the SIP-0092 plan doc Terminology Lock, this module is allowed to read
legacy on-disk artifact names during a future migration, but new code in this
file should use the post-rename vocabulary (TypedCheck, ImplementationPlan,
PlanTask, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CheckSpec:
    """Static contract for a typed acceptance check.

    Attributes:
        name: Vocabulary name (e.g., ``endpoint_defined``). Must match the
            ``check`` field in the authored TypedCheck.
        required_params: Param keys that must be present on every authored
            instance. Missing → ValueError at parse time.
        optional_params: Param keys that may be present. Unknown keys are
            rejected at parse time.
        param_types: Map of param key → expected Python type (or tuple of
            types). The parser does an ``isinstance`` check; mismatches →
            ValueError.
        supported_stacks: Frozen set of stack identifiers (e.g., ``fastapi``,
            ``python``) on which the M1.2 evaluator can act. Empty set means
            stack-agnostic. The parser does NOT enforce stack compatibility —
            stack-unsupported but well-formed checks are valid plans (RC-11)
            that the evaluator returns ``skipped`` for at runtime (RC-12).
        requires_stack_context: When true, the M1.2 evaluator needs declared
            stack context (from ``HandlerContext``) to evaluate. When false,
            language-level cues (file extension) are sufficient. Per RC-12a,
            stack-context-unset for a check that requires it returns
            ``status: skipped`` reason ``unsupported_stack_or_syntax``, NOT
            ``error``.
        path_params: Param keys whose values are workspace-relative file or
            glob paths. The parser applies cheap pre-eval rejection (absolute
            paths, ``..`` traversal) on these so authoring-time errors don't
            slip through to evaluation. Full chrooting and symlink rejection
            still happens at evaluation time (M1.2).
    """

    name: str
    required_params: frozenset[str]
    optional_params: frozenset[str] = frozenset()
    param_types: dict[str, type | tuple[type, ...]] = field(default_factory=dict)
    supported_stacks: frozenset[str] = frozenset()
    requires_stack_context: bool = False
    path_params: frozenset[str] = frozenset()


# Allowed severity values. Anything else → ValueError at parse time.
ALLOWED_SEVERITIES: frozenset[str] = frozenset({"error", "warning", "info"})


# Rev 1 vocabulary. Each entry's evaluator implementation lands in M1.2;
# the parser already rejects authoring errors against this spec.
CHECK_SPECS: dict[str, CheckSpec] = {
    "endpoint_defined": CheckSpec(
        name="endpoint_defined",
        required_params=frozenset({"file", "methods_paths"}),
        param_types={"file": str, "methods_paths": list},
        supported_stacks=frozenset({"fastapi"}),
        requires_stack_context=True,
        path_params=frozenset({"file"}),
    ),
    "import_present": CheckSpec(
        name="import_present",
        required_params=frozenset({"file", "module"}),
        optional_params=frozenset({"symbol"}),
        param_types={"file": str, "module": str, "symbol": str},
        supported_stacks=frozenset({"python", "javascript", "typescript"}),
        requires_stack_context=False,
        path_params=frozenset({"file"}),
    ),
    "field_present": CheckSpec(
        name="field_present",
        required_params=frozenset({"file", "class_name", "fields"}),
        param_types={"file": str, "class_name": str, "fields": list},
        supported_stacks=frozenset({"python"}),
        requires_stack_context=True,
        path_params=frozenset({"file"}),
    ),
    "regex_match": CheckSpec(
        name="regex_match",
        required_params=frozenset({"file", "pattern"}),
        optional_params=frozenset({"count_min"}),
        param_types={"file": str, "pattern": str, "count_min": int},
        supported_stacks=frozenset(),
        requires_stack_context=False,
        path_params=frozenset({"file"}),
    ),
    "count_at_least": CheckSpec(
        name="count_at_least",
        required_params=frozenset({"glob", "min_count"}),
        param_types={"glob": str, "min_count": int},
        supported_stacks=frozenset(),
        requires_stack_context=False,
        path_params=frozenset({"glob"}),
    ),
    "command_exit_zero": CheckSpec(
        name="command_exit_zero",
        required_params=frozenset({"argv"}),
        optional_params=frozenset({"cwd", "timeout_s"}),
        param_types={"argv": list, "cwd": str, "timeout_s": int},
        supported_stacks=frozenset(),
        requires_stack_context=False,
        # argv elements are not single paths; the M1.2 safelist (RC-10a)
        # validates argv shapes pattern-by-pattern. cwd is path-checked at
        # evaluation time, not here.
        path_params=frozenset(),
    ),
}


def reserved_keys_for(check_name: str) -> frozenset[str]:
    """Return the keys reserved for the wrapper (not part of params).

    Useful for the parser's flat-YAML normalization rule: params is the
    authored dict minus these keys.
    """
    return frozenset({"check", "severity", "description"})
