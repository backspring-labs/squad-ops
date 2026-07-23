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

from collections.abc import Callable
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
        notes: Free-text constraint rendered into the proposer vocabulary as a
            ``- Note:`` line. For constraints the param schema alone can't
            express (e.g. the command safelist).
    """

    name: str
    required_params: frozenset[str]
    optional_params: frozenset[str] = frozenset()
    param_types: dict[str, type | tuple[type, ...]] = field(default_factory=dict)
    supported_stacks: frozenset[str] = frozenset()
    requires_stack_context: bool = False
    path_params: frozenset[str] = frozenset()
    example: dict[str, object] = field(default_factory=dict)
    notes: str = ""


# Allowed severity values. Anything else → ValueError at parse time.
ALLOWED_SEVERITIES: frozenset[str] = frozenset({"error", "warning", "info"})


# ---------------------------------------------------------------------------
# Command safelist (RC-10a) — single source for the ``command_exit_zero``
# argv contract. Consumed by the runtime evaluator (``acceptance_checks.py``),
# the authoring-time lint (``implementation_plan.py``, #422), and the proposer
# vocabulary below, so the three surfaces cannot drift.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandPattern:
    name: str
    matcher: Callable[[list[str]], bool]


def _exact(*expected: str) -> Callable[[list[str]], bool]:
    expected_list = list(expected)

    def matcher(argv: list[str]) -> bool:
        return list(argv) == expected_list

    return matcher


def _exact_then_one_path(*prefix: str) -> Callable[[list[str]], bool]:
    prefix_list = list(prefix)

    def matcher(argv: list[str]) -> bool:
        return len(argv) == len(prefix_list) + 1 and list(argv[: len(prefix_list)]) == prefix_list

    return matcher


def _prefix_with_args(*prefix: str) -> Callable[[list[str]], bool]:
    prefix_list = list(prefix)

    def matcher(argv: list[str]) -> bool:
        return len(argv) > len(prefix_list) and list(argv[: len(prefix_list)]) == prefix_list

    return matcher


def _argv0_with_args(name: str) -> Callable[[list[str]], bool]:
    def matcher(argv: list[str]) -> bool:
        return len(argv) >= 1 and argv[0] == name

    return matcher


# Order matters only for human readability; the matcher is `any(...)`.
COMMAND_SAFELIST: tuple[CommandPattern, ...] = (
    CommandPattern(
        "python -m py_compile <file>", _exact_then_one_path("python", "-m", "py_compile")
    ),
    CommandPattern("python -m mypy <args...>", _prefix_with_args("python", "-m", "mypy")),
    CommandPattern("node --check <file>", _exact_then_one_path("node", "--check")),
    CommandPattern("ruff check <args...>", _prefix_with_args("ruff", "check")),
    CommandPattern("tsc --noEmit", _exact("tsc", "--noEmit")),
    CommandPattern("eslint <args...>", _argv0_with_args("eslint")),
    CommandPattern("pyflakes <file>", _exact_then_one_path("pyflakes")),
)


def argv_matches_safelist(argv: list[str]) -> bool:
    """True when argv matches one of the safelisted command forms."""
    return any(pat.matcher(argv) for pat in COMMAND_SAFELIST)


# #464: regex_match may only target document artifacts. Regexes against
# source files prescribe another roll's stylistic choices (quote style,
# identifier names) and have twice produced criteria unwinnable by correct
# code; source files are verifiable by the style-immune checks
# (endpoint_defined / import_present / field_present / function_defined /
# command_exit_zero) and the behavioral required checks (tests_pass /
# frontend_build).
REGEX_DOCUMENT_SUFFIXES: tuple[str, ...] = (".md", ".txt", ".rst")


def regex_target_is_document(file: str) -> bool:
    """True when a regex_match target is a document artifact (#464)."""
    return isinstance(file, str) and file.lower().endswith(REGEX_DOCUMENT_SUFFIXES)


def command_safelist_names() -> tuple[str, ...]:
    """Human-readable safelisted command forms, for error messages and prompts."""
    return tuple(pat.name for pat in COMMAND_SAFELIST)


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
    "function_defined": CheckSpec(
        name="function_defined",
        required_params=frozenset({"file", "name_prefix"}),
        optional_params=frozenset({"min_count"}),
        param_types={"file": str, "name_prefix": str, "min_count": int},
        supported_stacks=frozenset({"python"}),
        requires_stack_context=True,
        path_params=frozenset({"file"}),
        example={"file": "backend/tests/test_runs.py", "name_prefix": "test_", "min_count": 3},
        # The style-immune answer to "this file defines test functions" — the
        # intent that otherwise tempts a proposer into a #464 regex on a source
        # file. AST-based: a prefix on the real function name, not a text regex.
        notes=(
            "AST-based, style-immune: counts `def`/`async def` whose name starts "
            "with `name_prefix` (default `min_count` 1). Use this — NOT "
            "regex_match — to assert a source file defines functions such as "
            "pytest `test_*`."
        ),
    ),
    "harness_boundary": CheckSpec(
        name="harness_boundary",
        required_params=frozenset({"file", "entry_modules"}),
        optional_params=frozenset({"client_ctor"}),
        param_types={"file": str, "entry_modules": list, "client_ctor": str},
        supported_stacks=frozenset({"python"}),
        requires_stack_context=True,
        path_params=frozenset({"file"}),
        example={
            "file": "backend/tests/test_runs.py",
            "entry_modules": ["backend.main", "app.main"],
            "client_ctor": "TestClient",
        },
        # SIP-0100 scaffold test boundary: the mechanical guarantee behind the harness. The
        # test must consume the scaffold-owned `client` fixture, not re-derive the app.
        notes=(
            "SIP-0100 scaffold test boundary: a QA test must consume the scaffold-owned "
            "`client` fixture — it must NOT import an app entry module (`entry_modules`) or "
            "directly construct the app test client (`client_ctor`, default `TestClient`). "
            "AST-based; a pure unit test that never touches the app passes."
        ),
    ),
    "regex_match": CheckSpec(
        name="regex_match",
        required_params=frozenset({"file", "pattern"}),
        optional_params=frozenset({"count_min"}),
        param_types={"file": str, "pattern": str, "count_min": int},
        supported_stacks=frozenset(),
        requires_stack_context=False,
        path_params=frozenset({"file"}),
        # pattern carries a backslash escape on purpose: the rendered example
        # must teach proposers the single-quote style for real regexes, since
        # double-quoting \w / \. is exactly what broke YAML parsing in #182's wake.
        # The example targets a DOCUMENT on purpose (#464): regex on source
        # files is rejected at plan validation — teach the allowed shape.
        example={"file": "qa_handoff.md", "pattern": r"## How to \w+", "count_min": 2},
        notes=(
            "Documents only (.md/.txt/.rst) — a regex on a SOURCE file is "
            "rejected at plan validation (#464). To assert a source file defines "
            "functions (e.g. pytest `test_*`), use `function_defined` instead."
        ),
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
        # argv elements are not single paths; the RC-10a safelist above
        # validates argv shapes pattern-by-pattern. cwd is path-checked at
        # evaluation time, not here.
        path_params=frozenset(),
        example={"argv": ["python", "-m", "py_compile", "app/main.py"]},
        notes=(
            "argv MUST match one of these safelisted forms (anything else — "
            "pytest, npm, make, pip, setup.py, ... — cannot execute and fails "
            "plan validation): " + "; ".join(f"`{p.name}`" for p in COMMAND_SAFELIST)
        ),
    ),
}


def reserved_keys_for(check_name: str) -> frozenset[str]:
    """Return the keys reserved for the wrapper (not part of params).

    Useful for the parser's flat-YAML normalization rule: params is the
    authored dict minus these keys. ``id`` is reserved so a ``TypedCheck``
    resolved from a verification-contract ``criteria_ref`` (SIP-0098 98.3)
    carries the stable contract criterion id through parse/serialize/wire
    round-trips without the id leaking into the check's params.
    """
    return frozenset({"check", "severity", "description", "id"})


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
    """Render an example param value as inline YAML, strings SINGLE-quoted.

    The quote style is load-bearing: proposers copy whatever style the example
    uses, and single-quoted YAML scalars do not process backslash escapes — a
    regex like ``\\.length`` round-trips literally. Double quotes would read
    ``\\.`` as an escape sequence and ``yaml.safe_load`` raises "unknown escape
    character", which drops the entire proposal (observed in cyc_82c9b3f5a2c1,
    the #182 follow-up regression). Embedded single quotes are escaped as ``''``
    per the YAML single-quoted scalar rule.
    """
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
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
        if spec.notes:
            out.append(f"- Note: {spec.notes}")
        out.append("- Example:")
        out.append("  ```yaml")
        out.append(f"  - check: {name}")
        for key, value in spec.example.items():
            out.append(f"    {key}: {_format_example_value(value)}")
        out.append("    severity: error")
        out.append("  ```")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
