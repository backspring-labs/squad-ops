"""Acceptance check specification registry — single source of truth (SIP-0092 M1).

This module defines the contract for every typed acceptance check vocabulary
entry. It is consumed by:

- The parser in ``implementation_plan.py`` (RC-11 authoring-time validation)
  to reject unknown check names, missing required params, wrong types, and
  malformed values at plan-parse time.
- The evaluator framework in ``acceptance_checks.py`` (M1.2, not yet shipped)
  to declare the per-check evaluator implementation against the same spec.
- ``render_typed_acceptance_vocabulary()`` (issue #182) to generate the
  proposer-prompt vocabulary reference, so proposers are told the exact param
  names + a parser-valid example for every check instead of guessing.

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
        example: A representative, parser-valid param dict for this check
            (params only — no ``check``/``severity`` wrapper). Rendered into the
            proposer vocabulary so models see the exact flat-YAML shape. Kept in
            sync with the spec by test (must include every required param and
            only allowed params, with correct types).
    """

    name: str
    required_params: frozenset[str]
    optional_params: frozenset[str] = frozenset()
    param_types: dict[str, type | tuple[type, ...]] = field(default_factory=dict)
    supported_stacks: frozenset[str] = frozenset()
    requires_stack_context: bool = False
    path_params: frozenset[str] = frozenset()
    example: dict[str, object] = field(default_factory=dict)


# Allowed severity values. Anything else → ValueError at parse time.
ALLOWED_SEVERITIES: frozenset[str] = frozenset({"error", "warning", "info"})


# Rev 1 vocabulary. Each entry's evaluator implementation lands in M1.2;
# the parser already rejects authoring errors against this spec. The ``example``
# on each entry is rendered into the proposer prompt (issue #182) and is
# asserted parser-valid by test.
CHECK_SPECS: dict[str, CheckSpec] = {
    "endpoint_defined": CheckSpec(
        name="endpoint_defined",
        required_params=frozenset({"file", "methods_paths"}),
        param_types={"file": str, "methods_paths": list},
        supported_stacks=frozenset({"fastapi"}),
        requires_stack_context=True,
        path_params=frozenset({"file"}),
        example={"file": "app/main.py", "methods_paths": ["GET /runs", "POST /runs"]},
    ),
    "import_present": CheckSpec(
        name="import_present",
        required_params=frozenset({"file", "module"}),
        optional_params=frozenset({"symbol"}),
        param_types={"file": str, "module": str, "symbol": str},
        supported_stacks=frozenset({"python", "javascript", "typescript"}),
        requires_stack_context=False,
        path_params=frozenset({"file"}),
        example={"file": "app/main.py", "module": "app.models", "symbol": "RunEvent"},
    ),
    "field_present": CheckSpec(
        name="field_present",
        required_params=frozenset({"file", "class_name", "fields"}),
        param_types={"file": str, "class_name": str, "fields": list},
        supported_stacks=frozenset({"python"}),
        requires_stack_context=True,
        path_params=frozenset({"file"}),
        example={"file": "app/models.py", "class_name": "RunEvent", "fields": ["id", "title"]},
    ),
    "regex_match": CheckSpec(
        name="regex_match",
        required_params=frozenset({"file", "pattern"}),
        optional_params=frozenset({"count_min"}),
        param_types={"file": str, "pattern": str, "count_min": int},
        supported_stacks=frozenset(),
        requires_stack_context=False,
        path_params=frozenset({"file"}),
        example={"file": "tests/test_runs.py", "pattern": "def test_", "count_min": 5},
    ),
    "count_at_least": CheckSpec(
        name="count_at_least",
        required_params=frozenset({"glob", "min_count"}),
        param_types={"glob": str, "min_count": int},
        supported_stacks=frozenset(),
        requires_stack_context=False,
        path_params=frozenset({"glob"}),
        example={"glob": "tests/test_*.py", "min_count": 3},
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
        example={"argv": ["python", "-m", "py_compile", "app/main.py"]},
    ),
}


def reserved_keys_for(check_name: str) -> frozenset[str]:
    """Return the keys reserved for the wrapper (not part of params).

    Useful for the parser's flat-YAML normalization rule: params is the
    authored dict minus these keys.
    """
    return frozenset({"check", "severity", "description"})


_PARAM_TYPE_NAMES: dict[type, str] = {
    str: "string",
    int: "integer",
    list: "list",
    bool: "boolean",
}


def _type_label(spec: CheckSpec, param: str) -> str:
    """Human-readable type name(s) for a param, from the spec's param_types."""
    declared = spec.param_types.get(param)
    if declared is None:
        return "value"
    types = declared if isinstance(declared, tuple) else (declared,)
    return " | ".join(_PARAM_TYPE_NAMES.get(t, getattr(t, "__name__", "value")) for t in types)


def _format_example_value(value: object) -> str:
    """Render an example param value as inline YAML (strings quoted)."""
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(_format_example_value(v) for v in value) + "]"
    return str(value)


def render_typed_acceptance_vocabulary() -> str:
    """Render the typed acceptance-criteria vocabulary for proposer prompts.

    Generated from ``CHECK_SPECS`` so it can never drift from the parser's
    contract. Fixes issue #182: proposers were given only check *names* (in the
    task-type fragments) with no params or examples — the ``count_at_least``
    check (the only one with two required params) failed validation because
    models guessed param names. This emits, for every check, the exact required
    and optional param names with types plus a parser-valid flat-YAML example.
    """
    out: list[str] = [
        "## Typed acceptance-criteria vocabulary",
        "",
        "Each entry under a task's `acceptance_criteria` is either an "
        "informational string or a typed-check mapping: a `check:` key, its "
        "params inline (flat — not nested under `params:`), and an optional "
        "`severity:` (`error` | `warning` | `info`, default `error`). Use the "
        "EXACT param names shown below — a missing, misnamed, or extra param "
        "fails plan validation and drops the entire proposal.",
        "",
    ]
    for name, spec in CHECK_SPECS.items():
        out.append(f"### `{name}`")
        required = ", ".join(
            f"`{p}` ({_type_label(spec, p)})" for p in sorted(spec.required_params)
        )
        out.append(f"- Required: {required}")
        if spec.optional_params:
            optional = ", ".join(
                f"`{p}` ({_type_label(spec, p)})" for p in sorted(spec.optional_params)
            )
            out.append(f"- Optional: {optional}")
        out.append("- Example:")
        out.append("  ```yaml")
        out.append(f"  - check: {name}")
        for key, value in spec.example.items():
            out.append(f"    {key}: {_format_example_value(value)}")
        out.append("    severity: error")
        out.append("  ```")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
