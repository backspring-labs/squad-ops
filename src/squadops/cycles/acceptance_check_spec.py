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

# Allowed severity values. Anything else → ValueError at parse time.
ALLOWED_SEVERITIES: frozenset[str] = frozenset({"error", "warning", "info"})

# ---------------------------------------------------------------------------
# Governance vocabulary (1.5 A5, #730 — the curated menu as a registry
# extension per docs/plans/1-5-typed-check-governance-design.md)
# ---------------------------------------------------------------------------

#: What a check's failure *indicts* — the repair-targeting and evidence-
#: taxonomy axis (#688 lineage / A3).
OWNERSHIP_PRODUCT = "product"
OWNERSHIP_SUITE = "suite"
OWNERSHIP_PLAN = "plan"
OWNERSHIP_CONTRACT = "contract"
OWNERSHIP_INFRASTRUCTURE = "infrastructure"

FAILURE_OWNERSHIP_VALUES: frozenset[str] = frozenset(
    {
        OWNERSHIP_PRODUCT,
        OWNERSHIP_SUITE,
        OWNERSHIP_PLAN,
        OWNERSHIP_CONTRACT,
        OWNERSHIP_INFRASTRUCTURE,
    }
)


#: Where a framework-injected ``file`` check is applied (``CheckSpec.injection_scope``).
#: ``file``: each emitted artifact whose extension the check parses. ``recipe``: each
#: container recipe (#598). The handler seam reads ``framework_injected_checks(scope)``;
#: nothing infers a scope from the shape of another field.
INJECTION_SCOPE_FILE = "file"
INJECTION_SCOPE_RECIPE = "recipe"
#: Each emitted JS/TS suite file (``JS_SUITE_SUFFIXES``, the harness's own vocabulary):
#: a check whose rules only mean something for a test, not for the source it tests (#1022).
INJECTION_SCOPE_SUITE = "suite"
INJECTION_SCOPES = frozenset({INJECTION_SCOPE_FILE, INJECTION_SCOPE_RECIPE, INJECTION_SCOPE_SUITE})


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
        (``supported_stacks`` was removed by #818: declared on 11 specs and read
            by nothing, repo-wide. It was also a *third* stack vocabulary, and an
            internally inconsistent one — ``{"fastapi"}`` named a framework,
            ``{"python"}`` a language, ``{"python", "javascript", "typescript"}``
            languages. What it appeared to do is done by ``applicable_extensions``,
            which is read at two live call sites, plus each evaluator's own stack
            branch. Deleted rather than wired: wiring an unvalidated vocabulary
            would have minted the stack-blueprint schema by accident, which is
            exactly what S1 declined to do when it named its type ``ScaffoldStack``.)
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
        framework_injected: The framework applies this check itself, to every
            applicable emitted artifact — it is not something a plan author
            selects. Kept OUT of the rendered proposer vocabulary (#689): a
            check the system always runs is not a decision the author should
            be asked to make, and offering it invites redundant rows that can
            only be authored wrong. The evaluator is registered normally, so
            authoring one still parses and evaluates rather than becoming a
            second rejection path.
        applicable_extensions: File extensions (lowercase, with dot) the
            evaluator can actually parse for this check's ``file`` target.
            Empty = not file-scoped or applicable to any file. pf-47/pf-49: the
            five AST checks read Python source only, but nothing told the plan
            author, so QA tasks dressed ``.jsx`` test files in pytest-idiom
            checks — every one skipped at evaluation, and a repair to such a
            task could never produce an executed verdict. Declared here so the
            authoring vocabulary renders it and dispatch can strip dead checks;
            derived consumers cannot drift from this table.
        injection_scope: WHICH emitted artifacts a framework-injected ``file`` check
            is applied to (``INJECTION_SCOPES``): ``file`` — every artifact whose
            extension the check parses (the default); ``recipe`` — every container
            recipe (``is_container_recipe``), which has no extension for the file
            rule to see (#598); ``suite`` — every emitted JS/TS suite file whose
            extension the check parses, never the source beside it (#1022). Declared,
            not inferred from an empty ``applicable_extensions``: a file-scoped check
            that happened to declare none would otherwise turn into a recipe check by
            accident.

    Governance attributes (1.5 A5, #730 — required keyword-only so every
    present and future entry DECLARES its governance; there is no default to
    slip through on):

        failure_ownership: What the check's failure indicts
            (``FAILURE_OWNERSHIP_VALUES``) — consumed by repair targeting
            (#688 lineage) and A3's evidence taxonomy.
        qa_available: Whether the check can reach ``qa.test`` emissions,
            authored and injected both (A1/#670's accounting axis).
        signature_participation: Whether the check's failures may enter the
            correction failure-signature (A4.1). Environment-variant checks
            stay out — a failure that does not reproduce deterministically
            must not key chain-termination identity.
        outcome_contribution: Whether evaluations feed the SIP-0096
            ``CycleOutcome`` roll-up.
        replayable: Whether a stored emission re-evaluates deterministically
            (Track C): pure static analysis over stored bytes is; anything
            that executes tooling against a live environment is not.
        blocking_default: Severity an injected instance runs at
            (``ALLOWED_SEVERITIES``); authored instances may still set their
            own severity.
    """

    name: str
    required_params: frozenset[str]
    optional_params: frozenset[str] = frozenset()
    param_types: dict[str, type | tuple[type, ...]] = field(default_factory=dict)
    requires_stack_context: bool = False
    path_params: frozenset[str] = frozenset()
    example: dict[str, object] = field(default_factory=dict)
    notes: str = ""
    #: The executables the evaluator shells out to, by the names ``CHECK_ENV_TOOLS`` uses.
    #: Empty means the check runs on the always-present runtime (Python, a base-lock
    #: dependency). The owner's rule B (#1229): a typed check executes in the producing
    #: role's agent container, so every role whose handlers evaluate typed checks
    #: provisions each tool here as data, or declares the gap in
    #: ``DECLARED_TOOLING_GAPS`` — ``test_typed_check_tooling_is_provisioned_where_checks_run``
    #: reads the provisioning files and holds both sides.
    required_tooling: frozenset[str] = frozenset()
    applicable_extensions: frozenset[str] = frozenset()
    framework_injected: bool = False
    injection_scope: str = "file"
    failure_ownership: str = field(kw_only=True)
    qa_available: bool = field(kw_only=True)
    signature_participation: bool = field(kw_only=True)
    outcome_contribution: bool = field(kw_only=True)
    replayable: bool = field(kw_only=True)
    blocking_default: str = field(kw_only=True)

    def __post_init__(self) -> None:
        if self.failure_ownership not in FAILURE_OWNERSHIP_VALUES:
            raise ValueError(
                f"check {self.name!r}: unknown failure_ownership {self.failure_ownership!r}"
            )
        if self.blocking_default not in ALLOWED_SEVERITIES:
            raise ValueError(
                f"check {self.name!r}: unknown blocking_default {self.blocking_default!r}"
            )
        if self.injection_scope not in INJECTION_SCOPES:
            raise ValueError(
                f"check {self.name!r}: unknown injection_scope {self.injection_scope!r}"
            )


def is_check_applicable(check_name: str, file_path: str) -> bool:
    """Can ``check_name``'s evaluator ever parse ``file_path``?

    True for checks that are not file-scoped (no ``applicable_extensions``) and
    for unknown names (the parser rejects those elsewhere; this helper never
    invents a second rejection path). A False here means the check would skip at
    every evaluation forever — dead weight in a plan, and on a QA task whose
    checks are ALL dead, a repair can never produce an executed verdict.
    """
    spec = CHECK_SPECS.get(check_name)
    if spec is None or not spec.applicable_extensions:
        return True
    from pathlib import PurePosixPath

    return PurePosixPath(file_path).suffix.lower() in spec.applicable_extensions


# ---------------------------------------------------------------------------
# Command safelist (RC-10a) — the single source for the ``command_exit_zero``
# argv contract. Consumed by the runtime evaluator (``acceptance_checks.py``),
# the authoring-time lint (``implementation_plan.py``, #422), the plan-validation
# net (``validate_command_checks``), and the proposer vocabulary, so no surface
# can hold a private opinion about what a plan may ask for.
#
# **#707: it used to be two sources, and they disagreed in both directions.**
# ``implementation_plan`` carried ``_CHECK_ENV_EXECUTABLES`` — the tools the check
# environment provides — and of eleven plausible forms, nine were rejected by exactly
# one of the two gates. The two rejection messages recommended *disjoint* sets, so an
# author who followed one was refused by the other. #846 is the bill: VS's Next.js
# re-roll lost a 75-minute framing run because the squad reached for the obvious
# TypeScript check, ``tsc --noEmit``, exactly as this list advertised it, and plan
# validation refused it.
#
# The reconciliation is structural, not a one-time resync. Each form declares the
# ``tool`` it needs; ``CHECK_ENV_TOOLS`` declares what the images provide; and
# ``_assert_safelist_is_runnable`` (below) refuses to import a self-contradictory
# vocabulary. The old executable-name gate is gone — asking the safelist is strictly
# stronger, since it also catches ``python -c`` and other argv that shares a
# provisioned argv[0] with a legitimate form.
#
# Entries are MEASURED, not intended. Every form below was run in both agent
# containers (squadops-eve, squadops-neo, 2026-08-10). What the measurement removed:
#
#   ``ruff check <args...>``  — absent from both images. ``pyflakes`` is the one
#                               Python linter actually installed (requirements/
#                               base.txt, for the ``undefined_names`` evaluator) and
#                               was the one form the old env gate refused.
#   ``python -m mypy <args>`` — mypy is in no requirements file, so the module import
#                               fails. argv[0] is ``python``, which is why an
#                               executable-name gate could never have caught it and
#                               why this list now keys on the tool a form NEEDS.
#   ``tsc --noEmit``          — was never on PATH (TypeScript lived in the app's own
#                               ``node_modules/.bin``); since #939 it IS provisioned in
#                               the dev and qa images (npm-global-packages.txt) for the
#                               ``undefined_names`` evaluator. Still no safelist form:
#                               an authored ``tsc`` criterion would also be evaluated
#                               in runtime-api's cross-check, which has no node, and
#                               ``next build`` runs tsc anyway, so ``frontend_compiles``
#                               IS the type check (#822, ``_nextjs_ts_slot_criteria``).
#   ``eslint <args...>``      — present (Debian's npm pulls in v6.4.0) but unusable:
#                               with no eslint config in the tree it exits 2 before
#                               reading a line of source, which is #645's "fails on
#                               any content, correct or not" class.
#
# Adding a form back is a measurement, not a preference: run it in the agent image
# against a representative tree, then declare its tool here.
# ---------------------------------------------------------------------------

#: The tools the check environment provides, measured in both agent images
#: (squadops-eve, squadops-neo, 2026-08-10). Not a policy preference — a fact about
#: the images, and the reason it lives beside the safelist rather than in the
#: validator is #707: two modules cannot hold one fact without eventually disagreeing
#: about it.
#:
#: ``pytest``/``npm``/``npx``/``tsc`` are provisioned but reach no safelisted form. They
#: stay because this set describes the environment, not the vocabulary; the subset rule
#: runs one way only. This set is the UNION over the agent images; the per-role truth is
#: the provisioning data itself (``agents/instances/<role>/system-packages.txt`` and
#: ``npm-global-packages.txt``), which ``required_tooling`` below is checked against role
#: by role — ``tsc`` was added 2026-09-01 after the rebuild that provisioned it (#939).
CHECK_ENV_TOOLS: frozenset[str] = frozenset(
    {"python", "python3", "pytest", "node", "npm", "npx", "pyflakes", "tsc"}
)


@dataclass(frozen=True)
class CommandPattern:
    """One authorable ``command_exit_zero`` argv form.

    ``tool`` is the executable the form needs present, which is NOT always ``argv[0]``
    — ``python -m mypy`` needs mypy, not python. Declaring it per form is what makes
    "authorable" and "runnable" the same question (#707).
    """

    name: str
    matcher: Callable[[list[str]], bool]
    tool: str


def _exact_then_one_path(*prefix: str) -> Callable[[list[str]], bool]:
    prefix_list = list(prefix)

    def matcher(argv: list[str]) -> bool:
        return len(argv) == len(prefix_list) + 1 and list(argv[: len(prefix_list)]) == prefix_list

    return matcher


# Order matters only for human readability; the matcher is `any(...)`.
COMMAND_SAFELIST: tuple[CommandPattern, ...] = (
    CommandPattern(
        "python -m py_compile <file>",
        _exact_then_one_path("python", "-m", "py_compile"),
        tool="python",
    ),
    CommandPattern("node --check <file>", _exact_then_one_path("node", "--check"), tool="node"),
    CommandPattern("pyflakes <file>", _exact_then_one_path("pyflakes"), tool="pyflakes"),
)


def _assert_safelist_is_runnable() -> None:
    """Refuse to import a vocabulary that advertises what the environment cannot run.

    #707's acceptance is *"the set of authorable command forms equals the set of
    runnable command forms"*, and the way that was violated for eight months was a
    second list drifting quietly. A test would catch the drift; raising here means the
    contradictory state cannot exist at all — the #845 precedent, where a missing build
    profile stopped being swallowed. The condition is static module content, so this can
    only fire on an edit to this file, never on runtime data.
    """
    missing = sorted({pat.tool for pat in COMMAND_SAFELIST} - CHECK_ENV_TOOLS)
    if missing:
        raise RuntimeError(
            f"command safelist advertises {missing}, which CHECK_ENV_TOOLS does not "
            f"provide — an authored check using it can never execute, so it fails "
            f"identically on every correction attempt (#707). Either provision the tool "
            f"in agents/instances/<role>/ and declare it, or drop the form."
        )


_assert_safelist_is_runnable()


def argv_matches_safelist(argv: list[str]) -> bool:
    """True when argv matches one of the safelisted command forms."""
    return any(pat.matcher(argv) for pat in COMMAND_SAFELIST)


# #423: skip reasons that mean "enforcement is deliberately off by config" —
# the benign skip class. Every OTHER skip on an *authored* error-severity check
# is an evidence gap: the author asked for enforcement on a concrete target and
# the evaluator could not deliver it. That deliberately includes
# ``frontend_acceptance_checks_disabled`` — despite the name there is no such
# config flag; it marks the not-yet-implemented JS/TS analyzer, and an authored
# AST check on a ``.tsx`` file was exactly #423's measured exhibit (7 of 14
# evaluations skipped-yet-passed, the frontend contract surface unenforced).
CONFIG_OFF_SKIP_REASONS: frozenset[str] = frozenset(
    {
        "typed_acceptance_disabled",
        "command_acceptance_checks_disabled",
    }
)

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


# The frontend source-file family. Two readers, so it lives with the vocabulary:
# the evaluators skip AST analysis on these (JS/TS parsing is a follow-up), and
# #688's repair targeting uses the same line to decide which implementation source
# a failure may legitimately retarget — a backend failure must never reach frontend
# source, and vice versa.
FRONTEND_SUFFIXES: frozenset[str] = frozenset({".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"})


def is_frontend_source(path: str) -> bool:
    """True when ``path`` is a frontend source file by extension."""
    return isinstance(path, str) and path.lower().endswith(tuple(FRONTEND_SUFFIXES))


# The one vocabulary name read by a module that does not evaluate it: #688's
# probe→fill-slot resolution filters contract criteria on it. Bound to the
# CHECK_SPECS key below so a rename moves both together — a bare literal there
# would silently resolve to "no endpoints owned" and revert the fix to the
# no-op it was written to end.
CHECK_ENDPOINT_DEFINED = "endpoint_defined"

# #689: the framework-injected undefined-name check. Named here because the
# injection site filters on it, the same single-source reason as the constant
# above — a literal there would silently inject nothing after a rename.
CHECK_UNDEFINED_NAMES = "undefined_names"

#: #1082: the emission ends inside an unclosed construct — the shape a completion
#: takes when it runs out of budget mid-file. Narrower than a syntax gate on
#: purpose: it claims truncation only, so it can be exact on the brace languages
#: it cannot parse. `frontend_compiles` and `tests_pass` already fail on such a
#: file, but both run at acceptance — after the producing task is finished — so
#: the round gets spent by the consumer that tripped over it rather than by the
#: task that wrote it.
CHECK_UNTERMINATED_SOURCE = "unterminated_source"

#: #1217: a bare-specifier import naming a package the workspace never declares.
#: `unresolved_imports` (#591) deliberately ignores anything outside the workspace,
#: so nothing covered this boundary and a qa test importing
#: `@testing-library/user-event` — beside three declared `@testing-library/*`
#: siblings — reached test execution and spent three correction rounds
#: (cyc_0a0a33b4776e). Named here for the same single-source reason as the
#: constants above: the injection filter keys on it.
CHECK_DECLARED_IMPORTS = "declared_imports"

# #629 (1.5 A6/D2): the blocking suite-vs-contract check. Multi-reader constant
# (injection in task_plan, locus routing in failure_evidence, the evaluator,
# tests) — same single-source rule as the two above.
CHECK_CONTRACT_ASSERTIONS = "contract_assertions_match"

# #1153: the blocking suite-vs-declared-kind check — the free-authored counterpart of
# #1094's fill kind gate. Multi-reader constant (injection in task_plan, locus routing in
# failure_evidence, the evaluator, tests), same single-source rule as the one above.
CHECK_ASSERTION_KINDS = "assertion_kinds_match"
# #730 D1 / #504: the fill-slot signature surface, promoted from report to
# blocking injected check. Constant beside its CHECK_SPECS key so a rename
# moves both together.
CHECK_FILL_SLOT_SIGNATURE = "fill_slot_signature"

# SIP-0100 / #833: the QA harness-boundary check. Named here because `task_plan` filters its
# injection on the check's own applicability — the same single-source rule as the constants
# above, and it earns one for the same reason they do: a literal in an injection filter
# silently injects nothing after a rename.
CHECK_HARNESS_BOUNDARY = "harness_boundary"
# #1022: an author-written JS/TS suite is contained by the stack's own definition of
# "invokes the application" (``AppInvocation``) at emission — a live-server fetch inside an
# in-process harness, or a suite that invokes nothing of the application, is rejected with
# a named finding before it can spend a correction round. Promoted from #1052's
# reporting-only findings on the evidence of the V7, 1.6.6 and 1.7.0 rolls.
CHECK_ADDITIVE_CONTAINMENT = "additive_containment"

# #822: the per-view bundler check. Named here because `VerificationContract.view_slots`
# filters on it to identify a stack's view files for repair targeting — the same
# single-source rule as the constants above, and the same failure mode if it drifts: a
# literal that stops matching resolves to "this stack has no views" rather than erroring.
CHECK_FRONTEND_COMPILES = "frontend_compiles"

# #598: the emitted container's packaging, read statically — the three pf-38 defects as
# findings over the recipe and the tree it copies from. REPORTING-ONLY this line
# (``blocking_default="warning"``): the seam never missions on it, the verdict ledger, the
# correction signature and the failure category read it as advisory, and the findings are
# banked on the task's typed-check evaluation artifact for the per-round record. Whether it
# becomes blocking, and whether the image is built in-cycle (``package_builds``, declared
# unbuilt below), are the owner's separate calls (1.7.1 plan §6).
CHECK_CONTAINER_PACKAGING = "container_packaging"
#: The recipe an emission is recognised by: a file named ``Dockerfile`` at any depth, or
#: ``Dockerfile.<variant>``. Container vocabulary, not a stack's — both stacks package with
#: one, and the builder emits it under this name on every profile.
CONTAINER_RECIPE_BASENAME = "Dockerfile"


def is_container_recipe(path: str) -> bool:
    """Whether ``path`` names a container recipe (``Dockerfile`` / ``Dockerfile.<variant>``)."""
    from pathlib import PurePosixPath

    name = PurePosixPath(path).name
    return name == CONTAINER_RECIPE_BASENAME or name.startswith(CONTAINER_RECIPE_BASENAME + ".")


# #629 (1.5 A6/D2): the ADVISORY prose-vs-contract identity. Deliberately NOT a
# ``CHECK_SPECS`` entry — that would make it plan-authorable; it names the
# warning rows the plan-prose lint emits (``implementation_plan``), keeping its
# lower evidence quality from laundering into the blocking check above. The
# full governance-registry entry rides #730's attribute backfill.
PLAN_PROSE_CONTRACT_DIVERGENCE = "plan_prose_contract_divergence"


# The `"METHOD /path"` endpoint-token grammar. `endpoint_defined.methods_paths`
# is authored in it and the evaluator matches route decorators against it; #688
# added a second reader — the contract resolves which fill slot owns a failing
# probe's endpoint — so the grammar lives here with the rest of the vocabulary
# rather than being duplicated or reached into privately.
HTTP_METHODS: frozenset[str] = frozenset(
    {"get", "post", "put", "delete", "patch", "options", "head"}
)


def normalize_route(path: str) -> str:
    """Normalize trailing slash for tolerant route comparison."""
    if path != "/" and path.endswith("/"):
        return path[:-1]
    return path


def parse_method_path(token: str) -> tuple[str, str] | None:
    """Parse a ``"METHOD /path"`` token; return ``(METHOD, /path)`` or ``None``.

    ``None`` on anything that is not two whitespace-separated fields whose first
    is an HTTP method — callers treat that as "not an endpoint token" rather
    than an error, so a malformed entry is inert instead of fatal.
    """
    parts = token.strip().split(maxsplit=1)
    if len(parts) != 2:
        return None
    method, path = parts[0].upper(), normalize_route(parts[1])
    if method.lower() not in HTTP_METHODS:
        return None
    return method, path


def parse_method_path_status(token: str) -> tuple[str, str, int] | None:
    """Parse a ``"METHOD /path STATUS"`` token (#629's pinned-status grammar).

    The three-field extension of ``parse_method_path`` — the wire shape the
    ``contract_assertions_match`` injection uses for its ``endpoints`` param,
    one token per (endpoint, pinned status). Same tolerance rule: ``None`` for
    anything malformed, so a bad entry is inert instead of fatal.
    """
    parts = token.strip().rsplit(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        return None
    method_path = parse_method_path(parts[0])
    if method_path is None:
        return None
    status = int(parts[1])
    if not 100 <= status <= 599:
        return None
    return method_path[0], method_path[1], status


# Rev 1 vocabulary. Each entry's evaluator implementation lands in M1.2;
# the parser already rejects authoring errors against this spec. The ``example``
# on each entry is rendered into the proposer prompt (issue #182) and is
# asserted parser-valid by test.
#: Languages the framework emits and therefore reasons about. A check that does not
#: apply to one of these is not covering it — and #1216 is that the difference used to
#: be invisible: `is_check_applicable` returns False and the injection loop simply
#: `continue`s, so a `.ts` emission got less checking than an identical `.py` one and
#: the resulting green looked the same.
EMISSION_LANGUAGES: frozenset[str] = frozenset({".py", ".js", ".jsx", ".ts", ".tsx"})

#: Framework-injected file-scoped checks that deliberately do not cover a language,
#: WITH THE REASON. Not a suppression list: an entry here is a coverage gap the
#: evidence should disclose, and `uncovered_languages` reads it so a green can say
#: what it did not check rather than implying it checked everything.
#:
#: `test_every_coverage_gap_is_declared` fails on an undeclared gap, so adding a
#: stack-specific check without saying what it leaves uncovered is a CI failure rather
#: than a discovery three rolls later (#939 sat open five weeks and cost a shakeout).
#: An entry whose gap no longer exists fails too, so the list stays exactly as large
#: as reality — the same two-sided shape as requirements/constraint-exceptions.txt.
DECLARED_COVERAGE_GAPS: dict[str, dict[str, str]] = {
    CHECK_ADDITIVE_CONTAINMENT: dict.fromkeys(
        (".py",),
        "A pytest suite runs the application in-process through TestClient, so a "
        "live-server fetch is not its failure mode, and its containment is the harness "
        "boundary, the contract-assertion gate and the assertion-kind gate. The JS/TS "
        "rules would misread every Python suite as invoking nothing.",
    ),
    CHECK_DECLARED_IMPORTS: dict.fromkeys(
        (".py",),
        "Python declares dependencies in requirements files, not a manifest beside "
        "the source, and resolution is environment-wide rather than per-directory. "
        "The equivalent check is a different check, not this one with another "
        "extension — no Python emission is silently less checked as a result, since "
        "undefined_names and the syntax gate both cover .py.",
    ),
}


def framework_file_scoped_checks() -> dict[str, frozenset[str]]:
    """``{check: applicable_extensions}`` for the checks #1216 governs.

    One predicate, read by both the disclosure and the guard. They were written
    separately first and disagreed immediately — the rendered menu listed gaps for
    checks the test never required declaring, which is the same class of drift the
    generated-doc rule exists to prevent, one level in.
    """
    return {
        name: spec.applicable_extensions
        for name, spec in CHECK_SPECS.items()
        if spec.framework_injected
        and spec.injection_scope in (INJECTION_SCOPE_FILE, INJECTION_SCOPE_SUITE)
        and spec.required_params == frozenset({"file"})
        and spec.applicable_extensions
    }


def framework_injected_checks(scope: str) -> tuple[str, ...]:
    """The framework-injected ``file`` checks declared for ``scope`` (``INJECTION_SCOPES``),
    sorted — what the handler seam applies to an emission, read from the specs rather
    than from a list kept beside them (#1082's drift). A check's scope is its own
    declaration; an unknown scope names nothing."""
    return tuple(
        sorted(
            name
            for name, spec in CHECK_SPECS.items()
            if spec.framework_injected
            and spec.required_params == frozenset({"file"})
            and spec.injection_scope == scope
        )
    )


def uncovered_languages(check_name: str) -> dict[str, str]:
    """``{extension: reason}`` a framework-injected check does not cover.

    The disclosure surface for #1216: a caller rendering evidence can say which
    languages went unchecked and why, instead of leaving a green to imply coverage
    the run never had.
    """
    extensions = framework_file_scoped_checks().get(check_name)
    if extensions is None:
        return {}
    declared = DECLARED_COVERAGE_GAPS.get(check_name, {})
    return {
        ext: declared.get(ext, "undeclared gap") for ext in sorted(EMISSION_LANGUAGES - extensions)
    }


CHECK_SPECS: dict[str, CheckSpec] = {
    CHECK_UNDEFINED_NAMES: CheckSpec(
        name=CHECK_UNDEFINED_NAMES,
        # tsc for the four frontend extensions; the .py half is pyflakes, a base-lock dependency.
        required_tooling=frozenset({"tsc"}),
        applicable_extensions=frozenset({".py", ".js", ".jsx", ".ts", ".tsx"}),
        required_params=frozenset({"file"}),
        param_types={"file": str},
        path_params=frozenset({"file"}),
        framework_injected=True,
        example={"file": "backend/routes.py"},
        notes=(
            "Applied by the framework to every emission from handlers on the "
            "typed-acceptance seam (dev, builder, qa); never authored. Python runs "
            "pyflakes in-process; .ts/.tsx/.js/.jsx run `tsc --noEmit` once per "
            "workspace and filter its unresolved-name diagnostics (TS2304/TS2552) to "
            "the file (#939). tsc is provisioned per role as data "
            "(agents/instances/<role>/npm-global-packages.txt); where no role declared "
            "it the check skips (missing_tooling), it does not fail."
        ),
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    CHECK_DECLARED_IMPORTS: CheckSpec(
        name=CHECK_DECLARED_IMPORTS,
        applicable_extensions=frozenset({".js", ".jsx", ".ts", ".tsx"}),
        required_params=frozenset({"file"}),
        param_types={"file": str},
        path_params=frozenset({"file"}),
        framework_injected=True,
        example={"file": "frontend/src/__tests__/runs.test.jsx"},
        notes=(
            "Applied by the framework to JS/TS emissions: every bare-specifier "
            "import must be declared in the nearest package.json, or be a Node "
            "builtin. Relative and absolute paths are unresolved_imports' business."
        ),
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    CHECK_UNTERMINATED_SOURCE: CheckSpec(
        name=CHECK_UNTERMINATED_SOURCE,
        applicable_extensions=frozenset({".py", ".ts", ".tsx", ".js", ".jsx"}),
        required_params=frozenset({"file"}),
        param_types={"file": str},
        path_params=frozenset({"file"}),
        framework_injected=True,
        example={"file": "app/api/runs/route.ts"},
        notes=(
            "Applied by the framework to every scannable emission from handlers on "
            "the typed-acceptance seam; never authored. Unlike the other file-scoped "
            "checks it covers the brace languages, because delimiter balance needs no "
            "parser and therefore no Node (#939's blocker)."
        ),
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    CHECK_ENDPOINT_DEFINED: CheckSpec(
        name=CHECK_ENDPOINT_DEFINED,
        applicable_extensions=frozenset({".py"}),
        required_params=frozenset({"file", "methods_paths"}),
        param_types={"file": str, "methods_paths": list},
        requires_stack_context=True,
        path_params=frozenset({"file"}),
        example={"file": "app/main.py", "methods_paths": ["GET /runs", "POST /runs"]},
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    "import_present": CheckSpec(
        name="import_present",
        applicable_extensions=frozenset({".py"}),
        required_params=frozenset({"file", "module"}),
        optional_params=frozenset({"symbol"}),
        param_types={"file": str, "module": str, "symbol": str},
        requires_stack_context=False,
        path_params=frozenset({"file"}),
        example={"file": "app/main.py", "module": "app.models", "symbol": "RunEvent"},
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    "field_present": CheckSpec(
        name="field_present",
        applicable_extensions=frozenset({".py"}),
        required_params=frozenset({"file", "class_name", "fields"}),
        param_types={"file": str, "class_name": str, "fields": list},
        requires_stack_context=True,
        path_params=frozenset({"file"}),
        example={"file": "app/models.py", "class_name": "RunEvent", "fields": ["id", "title"]},
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    "function_defined": CheckSpec(
        name="function_defined",
        applicable_extensions=frozenset({".py"}),
        required_params=frozenset({"file", "name_prefix"}),
        optional_params=frozenset({"min_count"}),
        param_types={"file": str, "name_prefix": str, "min_count": int},
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
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    "harness_boundary": CheckSpec(
        name="harness_boundary",
        applicable_extensions=frozenset({".py"}),
        required_params=frozenset({"file", "entry_modules"}),
        optional_params=frozenset({"client_ctor"}),
        param_types={"file": str, "entry_modules": list, "client_ctor": str},
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
        failure_ownership=OWNERSHIP_SUITE,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    "regex_match": CheckSpec(
        name="regex_match",
        required_params=frozenset({"file", "pattern"}),
        optional_params=frozenset({"count_min"}),
        param_types={"file": str, "pattern": str, "count_min": int},
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
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    "count_at_least": CheckSpec(
        name="count_at_least",
        required_params=frozenset({"glob", "min_count"}),
        param_types={"glob": str, "min_count": int},
        requires_stack_context=False,
        path_params=frozenset({"glob"}),
        example={"glob": "tests/test_*.py", "min_count": 3},
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    "command_exit_zero": CheckSpec(
        name="command_exit_zero",
        required_params=frozenset({"argv"}),
        optional_params=frozenset({"cwd", "timeout_s"}),
        param_types={"argv": list, "cwd": str, "timeout_s": int},
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
        # #707 DEPENDENCY: ownership is per-command in truth — `python -m mypy`
        # failing because the tool is absent is an infrastructure failure
        # masquerading as product. Untrustworthy until #707's allowlist
        # inventory + precedence ruling; recorded here, not solved here.
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=False,
        outcome_contribution=True,
        replayable=False,
        blocking_default="error",
    ),
    "frontend_compiles": CheckSpec(
        name="frontend_compiles",
        required_tooling=frozenset({"npm"}),
        applicable_extensions=frozenset({".js", ".jsx", ".ts", ".tsx"}),
        required_params=frozenset({"file"}),
        optional_params=frozenset({"timeout_s", "project_dir"}),
        param_types={"file": str, "timeout_s": int, "project_dir": str},
        requires_stack_context=False,
        path_params=frozenset({"file", "project_dir"}),
        example={"file": "frontend/src/views/RunsListView.jsx"},
        # #648: fay-4 and fay-8 both shipped a view with a rollup bind-time
        # error (an undefined identifier) — invisible to every static check
        # AND to `node --check` (which refuses .jsx outright), first surfacing
        # at final verification where no correction budget can reach it. This
        # is the real bundler, run at task time against the acceptance
        # workspace's full tree (#643).
        notes=(
            "Runs the actual frontend build (npm install + npm run build) in "
            "the buildable project directory and anchors blame to `file`. "
            "Catches bundler-level errors (undefined identifiers, broken "
            "imports) that no static check or `node --check` can see. "
            "`project_dir` is the workspace-relative directory holding "
            "package.json, defaulting to `frontend/` — a stack that builds at "
            "the root declares `.` (#822). Missing npm or a directory without "
            "package.json skips (missing_tooling), it does not fail."
        ),
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=False,
        signature_participation=False,
        outcome_contribution=True,
        replayable=False,
        blocking_default="error",
    ),
    CHECK_FILL_SLOT_SIGNATURE: CheckSpec(
        name=CHECK_FILL_SLOT_SIGNATURE,
        applicable_extensions=frozenset({".py"}),
        required_params=frozenset({"file", "routes"}),
        param_types={"file": str, "routes": list},
        requires_stack_context=False,
        path_params=frozenset({"file"}),
        framework_injected=True,
        example={
            "file": "backend/routes.py",
            "routes": [
                {
                    "route": "POST /runs",
                    "function": "create_run",
                    "params": ["payload"],
                    "response_model": "RunEvent",
                }
            ],
        },
        # #730 D1 / #504: pf-40's lesson made blocking. The stub header says
        # "scaffold-owned signatures, fill-only bodies"; instruction wasn't
        # enforcement, and SIP-0100's restore covers only the body-independent
        # elements. The rest was report-only — drift was free. Now it fails
        # acceptance with the divergence list as evidence, routing repair at
        # the producer instead of the framework ever rewriting producer code.
        notes=(
            "Injected by the framework on tasks that author .py fill slots: the "
            "slot's scaffold-owned signature surface — handler name, parameter "
            "names, response_model — is diffed against the seed's declared "
            "routes (params carry the declaration; the evaluator needs no "
            "scaffold access). status_code and the router assignment are "
            "restored at storage (SIP-0100), not checked here; a dropped route "
            "is endpoint_defined's job. Never authored."
        ),
        failure_ownership=OWNERSHIP_PRODUCT,
        # Fill slots are dev-lane emissions; qa authors suites, never slots.
        qa_available=False,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    CHECK_CONTRACT_ASSERTIONS: CheckSpec(
        name=CHECK_CONTRACT_ASSERTIONS,
        applicable_extensions=frozenset({".py"}),
        required_params=frozenset({"file", "endpoints"}),
        optional_params=frozenset({"allowed_error_statuses"}),
        param_types={"file": str, "endpoints": list, "allowed_error_statuses": list},
        requires_stack_context=False,
        path_params=frozenset({"file"}),
        framework_injected=True,
        example={
            "file": "backend/tests/test_runs.py",
            "endpoints": ["POST /runs 201", "POST /runs 422"],
            "allowed_error_statuses": [404, 409, 422],
        },
        # #629 / pf-54: five authored suite versions asserted 200-on-create
        # against a contract-pinned 201 — an unwinnable correction loop no
        # source repair could satisfy. The authoring injection (layer 1) is
        # guidance; this is the guarantee, injected by task_plan onto bound
        # qa.test tasks per expected suite file, never authored.
        notes=(
            "Injected by the framework on bind-mode qa.test tasks: asserted "
            "status codes in the suite are diffed against the contract's pinned "
            "endpoint statuses (`endpoints` tokens, `METHOD /path STATUS`); a "
            "pinned path requested through an undeclared prefix is also a "
            "violation. Never authored."
        ),
        failure_ownership=OWNERSHIP_SUITE,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    CHECK_ASSERTION_KINDS: CheckSpec(
        name=CHECK_ASSERTION_KINDS,
        applicable_extensions=frozenset({".py", ".js", ".jsx", ".ts", ".tsx"}),
        required_params=frozenset({"file", "field_kinds"}),
        param_types={"file": str, "field_kinds": dict},
        requires_stack_context=False,
        path_params=frozenset({"file"}),
        framework_injected=True,
        example={
            "file": "backend/tests/test_runs.py",
            "field_kinds": {"removed": "boolean", "participants": "list", "id": "string"},
        },
        # #1153 / 1.6.6 React roll 3: the manifest and the frozen model declared
        # `LeaveResult.removed: boolean`; four qa emissions asserted it equal to a
        # participant's NAME; the round-0 repair set it True — correct per contract —
        # and was rejected by the suite's own assertion, three rounds running. The
        # contradiction is between the assertion and a declared kind, so it is
        # decidable at emission, before any repair round.
        notes=(
            "Injected by the framework on bind-mode qa.test tasks, per suite file: an "
            "assertion that compares a response field to a literal whose kind cannot "
            "be the field's declared kind (a string against `boolean`, a number against "
            "`string`, an object against `list`) fails, naming the field, the line and "
            "the declared kind. `field_kinds` carries only names the manifest declares "
            'with one kind. Python suites are read by AST (`assert body["f"] == x`, '
            '`.get("f")`, `is True`); JS/TS suites by their `expect(...f).toBe(x)` / '
            "`.toEqual(x)` forms. Comparisons to names, calls or `None` are out of scope "
            "by design. Never authored."
        ),
        failure_ownership=OWNERSHIP_SUITE,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    "module_imports": CheckSpec(
        name="module_imports",
        applicable_extensions=frozenset({".py"}),
        required_params=frozenset({"file"}),
        optional_params=frozenset({"timeout_s"}),
        param_types={"file": str, "timeout_s": int},
        requires_stack_context=False,
        path_params=frozenset({"file"}),
        example={"file": "backend/routes.py"},
        # #628: every other check is static (AST / syntax) — pf-54 shipped a
        # routes.py that passed endpoint_defined + import_present + py_compile
        # yet NameError'd at import (the scaffold's `router = APIRouter()` line
        # was dropped). This is the one check that actually executes the
        # module's top level, in a subprocess, the way the app import will.
        notes=(
            "Imports the file's module in an isolated subprocess (workspace "
            "root on sys.path). Catches module-level runtime errors — NameError, "
            "missing symbols — that AST and py_compile cannot see. A dependency "
            "missing from the evaluating environment skips (missing_tooling), "
            "it does not fail."
        ),
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    CHECK_ADDITIVE_CONTAINMENT: CheckSpec(
        name=CHECK_ADDITIVE_CONTAINMENT,
        applicable_extensions=frozenset({".ts", ".tsx", ".js", ".jsx"}),
        required_params=frozenset({"file"}),
        # The scaffold stack, injected as a self-contained param (#629's pattern): the
        # evaluator's `stack` argument carries the check vocabulary (`fastapi`; Next.js
        # declares none), and the stack's `AppInvocation` is keyed by the scaffold name.
        optional_params=frozenset({"stack"}),
        param_types={"file": str, "stack": str},
        path_params=frozenset({"file"}),
        framework_injected=True,
        injection_scope=INJECTION_SCOPE_SUITE,
        example={"file": "__tests__/runs.test.ts", "stack": "nextjs_ts"},
        notes=(
            "Applied by the framework to every emitted JS/TS suite file (the harness's "
            "suite suffixes), on both stacks, at emission and on a repair's patch. Two "
            "rules read off the suite's own bytes against the stack's declaration of what "
            "invokes the application (`AppInvocation`): a fetch of a live server inside "
            "the in-process harness (nothing listens; the call can only hang or throw), and "
            "a suite that invokes nothing the stack counts as the application (it can only "
            "assert against its own stubs). Each failure names the rule and what the stack "
            "counts, so the re-emission brief carries it (#1022; the C3/C4 corpus reds and "
            "every V7 counted red). Python suites are contained by their own gates "
            "(harness_boundary, contract_assertions_match, assertion_kinds_match)."
        ),
        failure_ownership=OWNERSHIP_SUITE,
        qa_available=True,
        signature_participation=True,
        outcome_contribution=True,
        replayable=True,
        blocking_default="error",
    ),
    CHECK_CONTAINER_PACKAGING: CheckSpec(
        name=CHECK_CONTAINER_PACKAGING,
        required_params=frozenset({"file"}),
        param_types={"file": str},
        path_params=frozenset({"file"}),
        # Recipe-scoped, not suffix-scoped: a Dockerfile has no extension, and this is
        # not a language check — ``applicable_extensions`` stays empty so the #1216
        # coverage disclosure (a language axis) does not claim it, and injection keys
        # on ``is_container_recipe`` through the declared scope.
        framework_injected=True,
        injection_scope=INJECTION_SCOPE_RECIPE,
        example={"file": "Dockerfile"},
        notes=(
            "Applied by the framework to every emitted container recipe (a file named "
            "Dockerfile), REPORTING-ONLY: three static findings over the recipe, the tree "
            "it copies from and the entry script it runs — `npm ci` with no lockfile in "
            "the build context, a `COPY --from` of dist-packages off an official python "
            "image, and apt's nginx default site left in place under a conf.d server "
            "block (#598: pf-38's three build/run failures behind an accepted verdict). "
            "Does not build or start the image; `package_builds` is that criterion and "
            "stays declared unbuilt. Findings are banked on the evaluation artifact; the "
            "warning severity keeps them out of the verdict, the correction signature "
            "and the repair loop."
        ),
        failure_ownership=OWNERSHIP_PRODUCT,
        qa_available=False,
        # Reporting-only: it never fails a task, so a chain's identity must not read it.
        signature_participation=False,
        # Advisory rows are not ledger inputs (verification_normalize); banked elsewhere.
        outcome_contribution=False,
        replayable=True,
        blocking_default="warning",
    ),
}


def framework_recipe_scoped_checks() -> tuple[str, ...]:
    """The framework-injected checks applied to container recipes (#598) — the
    ``recipe`` scope of ``framework_injected_checks``, kept as a name because the
    handler seam and the menu read it beside ``is_container_recipe``."""
    return framework_injected_checks(INJECTION_SCOPE_RECIPE)


@dataclass(frozen=True)
class DeclaredUnbuiltCheck:
    """A menu entry that is visible but not evaluable and not authorable (#730 D4).

    The honesty pattern from ``frontend_acceptance_checks_disabled``: the menu
    names the check, states why it cannot exist yet, and names the trigger that
    unlocks the build — instead of the capability silently not existing. NOT a
    ``CHECK_SPECS`` entry: adding it there would make it plan-authorable, and
    an authorable check that can only ever skip is the pf-47/pf-49 dead-weight
    class the applicability net exists to strip.
    """

    name: str
    reason: str
    trigger: str


DECLARED_UNBUILT_CHECKS: tuple[DeclaredUnbuiltCheck, ...] = (
    DeclaredUnbuiltCheck(
        name="package_builds",
        reason=(
            "'the emitted container builds and runs' requires docker-in-"
            "verification (sandbox territory, SIP-0102 steps 3-7) and "
            "blueprint-owned packaging facts (Generalized Build). The static "
            "half — pf-38's three recipe defects as findings — is "
            "`container_packaging`, reporting-only (#598, 1.7.1)"
        ),
        trigger="Stack Blueprint lands (1.6)",
    ),
)


@dataclass(frozen=True)
class LanguageWithoutCommandForm:
    """A source language no safelisted ``command_exit_zero`` form can reach (#707).

    The same honesty pattern as ``DeclaredUnbuiltCheck``, applied one level down — to a
    check that *exists* but has no authorable form for some of the code it is offered
    against. It is declared rather than merely absent because of the argument the Stack
    Blueprint SIP makes against its own ``analysable_suffix`` sketch: that field encoded
    *a limitation of the tooling as a property of the domain*, and the frontend "was not
    modeled as a second language without checkers; it was silently absent, and absence
    demands no handling." **A partial model is worse than none: it implies the rest does
    not exist.** A shorter safelist with nothing said about TypeScript would repeat that
    exactly — the reader infers the list is complete rather than that a language fell off it.

    ``verified_by`` is the load-bearing field. An empty command surface is only acceptable
    while something else carries the claim, and naming that something is what forces the
    "then what verifies this language?" question the SIP asks downstream consumers to
    answer explicitly.
    """

    language: str
    reason: str
    verified_by: str


#: The environment axis of the declaration (#1229, rule B's third bullet): a role whose
#: handlers evaluate typed checks and whose image does NOT provision a tool a check's
#: evaluator needs, with the reason. Keyed ``(role, tool)``. Two-sided, like
#: ``DECLARED_COVERAGE_GAPS``: an entry for a role that now provisions the tool fails the
#: guard, so the list cannot outlive the gap. runtime-api is not a role here — under rule
#: B it re-runs typed checks only as a cross-check and provisions no stack toolchain.
DECLARED_TOOLING_GAPS: dict[tuple[str, str], str] = {
    ("builder", "npm"): (
        "The builder assembles packaging (Dockerfile, nginx, requirements) and emits no "
        "frontend source, so frontend_compiles never applies to its artifacts; its image "
        "declares no Node.js. Verified absent 2026-09-01 after the rebuild. The day an "
        "assemble emits a .js/.ts file this entry must go and the role must provision it."
    ),
    ("builder", "tsc"): (
        "Same as npm: no frontend emission from the builder, so undefined_names' tsc half "
        "never runs there. Declared rather than provisioned so the image stays what the "
        "role needs."
    ),
}


def required_tooling_by_check() -> dict[str, frozenset[str]]:
    """``check -> tools`` for every spec whose evaluator shells out — the guard's input."""
    return {
        name: spec.required_tooling for name, spec in CHECK_SPECS.items() if spec.required_tooling
    }


#: Languages the command safelist cannot reach. Rendered into the generated check menu,
#: so the gap is visible where the vocabulary is documented rather than inferred from a
#: list that happens not to mention it.
LANGUAGES_WITHOUT_COMMAND_FORM: tuple[LanguageWithoutCommandForm, ...] = (
    LanguageWithoutCommandForm(
        language="TypeScript (.ts/.tsx)",
        reason=(
            "the command safelist carries no TypeScript checker. `tsc` is provisioned "
            "globally in the dev and qa images since #939 (npm-global-packages.txt) for "
            "the undefined_names check, but a safelist entry is a separate decision: "
            "runtime-api has no node, so an authored `tsc` criterion would be #707's "
            "passes-the-allowlist-but-cannot-run class there until #1229. `node --check` "
            "refuses both extensions before parsing (ERR_UNKNOWN_FILE_EXTENSION, node "
            "v20.19.2, measured 2026-08-10)"
        ),
        verified_by=(
            "frontend_compiles / frontend_build — `next build` runs tsc itself and "
            "next.config.mjs declines to ignore type errors, so the bundler check IS "
            "the type check (#822 bend register entry 6)"
        ),
    ),
)


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
        if spec.framework_injected:
            continue  # #689: the framework runs it; it is not an authoring choice
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
        if spec.applicable_extensions:
            exts = ", ".join(f"`{e}`" for e in sorted(spec.applicable_extensions))
            out.append(
                f"- Applies to: {exts} files ONLY — never attach to any other "
                f"file type (e.g. `.js`/`.jsx`); it cannot be evaluated there "
                f"and is stripped at dispatch."
            )
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


def render_check_governance_menu() -> str:
    """Render the curated check menu (#730) — the governance table, generated.

    The doc file ``docs/architecture/typed-check-menu.md`` is this function's
    output, pinned by test: prose documentation is generated FROM the registry,
    never hand-maintained beside it (the design doc's rule). Two sections —
    the evaluable menu (every ``CHECK_SPECS`` entry) and the declared-unbuilt
    entries (visible, not evaluable, with their named triggers).
    """
    lines = [
        "# Typed-Check Menu (generated — do not edit)",
        "",
        "Generated from `CHECK_SPECS` / `DECLARED_UNBUILT_CHECKS` in",
        "`src/squadops/cycles/acceptance_check_spec.py` (1.5 A5, #730; design:",
        "`docs/plans/1-5-typed-check-governance-design.md`).",
        "Regenerate: `UPDATE_CHECK_MENU=1 pytest tests/unit/cycles/test_check_governance.py`",
        "",
        "## Evaluable checks",
        "",
        "| check | origin | ownership | qa | signature | outcome | replayable | blocking default |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in sorted(CHECK_SPECS):
        spec = CHECK_SPECS[name]
        lines.append(
            "| `{}` | {} | {} | {} | {} | {} | {} | {} |".format(
                name,
                "injected" if spec.framework_injected else "authored",
                spec.failure_ownership,
                "yes" if spec.qa_available else "no",
                "yes" if spec.signature_participation else "no",
                "yes" if spec.outcome_contribution else "no",
                "yes" if spec.replayable else "no",
                spec.blocking_default,
            )
        )
    gap_rows = [
        (name, ext, reason)
        for name in sorted(CHECK_SPECS)
        for ext, reason in sorted(uncovered_languages(name).items())
    ]
    if gap_rows:
        lines += [
            "",
            "## Declared coverage gaps",
            "",
            "Framework-injected checks that do not cover a language the framework emits,",
            "with the reason (#1216). A gap here is disclosure, not suppression: an emission",
            "in that language is checked less than an identical one elsewhere, and this is",
            "where a reader finds out. An undeclared gap fails",
            "`test_every_coverage_gap_is_declared`.",
            "",
            "| check | language | reason |",
            "|---|---|---|",
        ]
        for name, ext, reason in gap_rows:
            lines.append(f"| `{name}` | `{ext}` | {' '.join(reason.split())} |")

    tooling = required_tooling_by_check()
    if tooling:
        lines += [
            "",
            "## Tooling each check needs, and where it is declared absent",
            "",
            "A typed check executes in the producing role's agent container (#1229, rule B),",
            "so a role whose handlers evaluate typed checks provisions each tool below as data",
            "(`agents/instances/<role>/system-packages.txt`, `npm-global-packages.txt`) or",
            "declares the gap with its reason. Both sides are held by",
            "`test_typed_check_tooling_is_provisioned_where_checks_run`. A check whose tool is",
            "absent where it runs skips as `missing_tooling` and says so; it never fails the",
            "emission, and it never reads as a pass.",
            "",
            "| check | tools |",
            "|---|---|",
        ]
        for name in sorted(tooling):
            lines.append(f"| `{name}` | {', '.join(f'`{t}`' for t in sorted(tooling[name]))} |")
        lines += ["", "| role | tool | why absent |", "|---|---|---|"]
        for (role, tool), reason in sorted(DECLARED_TOOLING_GAPS.items()):
            lines.append(f"| `{role}` | `{tool}` | {' '.join(reason.split())} |")

    lines += [
        "",
        "`command_exit_zero` ownership is per-command in truth. The forms it may take",
        "are inventoried below — this replaces the standing caveat that called the",
        "surface untrustworthy pending #707's allowlist inventory.",
        "",
        "## Authorable `command_exit_zero` forms",
        "",
        "One list, not two (#707): a form is authorable exactly when the tool it needs is",
        "provisioned, and `acceptance_check_spec` refuses to import if that stops being true.",
        "Entries are measured in the agent images, never assumed.",
        "",
        "| form | tool needed |",
        "|---|---|",
    ]
    for pat in COMMAND_SAFELIST:
        lines.append(f"| `{pat.name}` | `{pat.tool}` |")
    lines += [
        "",
        "### Languages no form reaches",
        "",
        "Declared, not omitted — a list that simply fails to mention a language reads as",
        "complete. What carries the claim instead is named, because an empty command",
        "surface is only acceptable while something else verifies the code.",
        "",
        "| language | why no form | verified instead by |",
        "|---|---|---|",
    ]
    for gap in LANGUAGES_WITHOUT_COMMAND_FORM:
        lines.append(f"| {gap.language} | {gap.reason} | {gap.verified_by} |")
    lines += [
        "",
        "## Declared-unbuilt (visible, not evaluable, not authorable)",
        "",
        "| check | why not yet | trigger |",
        "|---|---|---|",
    ]
    for entry in DECLARED_UNBUILT_CHECKS:
        lines.append(f"| `{entry.name}` | {entry.reason} | {entry.trigger} |")
    lines.append("")
    return "\n".join(lines)
