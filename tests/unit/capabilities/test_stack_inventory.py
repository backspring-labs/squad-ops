"""2a — the stack inventory, as an executable enumeration.

The 1.6 plan charters 2a as *"one place answering 'which stacks exist and what does each
declare', with today's six registries as members"*, so that S3 has a subject rather than a
scavenger hunt. This module is that place, and it is a test rather than a document on
purpose.

**Why a test.** 1a was the document version of this step. It bounded four items and
overclaimed three times: a premise verified by grepping with one line of context instead of
reading the enclosing function, a sweep scoped to `src/`+`adapters/` that missed `tests/`,
and a module (`handlers/build_profiles.py`) simply not looked at — which became #838 and cost
a 75-minute framing run to rediscover. A read-and-classify pass fails the way reading fails.
An enumeration derived from the registries cannot skip a member, because it does not know
which members it is looking at.

**What it enumerates, and why each check exists.** Every one of these is a defect that
actually shipped, generalized so the next stack meets it as a test failure:

- *membership* — a stack missing from a registry. #838: `BUILD_PROFILES` had no `nextjs_ts`
  entry and the failure was swallowed, so a correct manifest would have been silently
  unscaffolded.
- *slot reachability* — a fill slot no `criteria_ref` can address. #849: colliding criterion
  ids made `criterion_index()` drop five of seven slots while the plan read fully covered.
- *guard wiring* — a guard with no production caller. #849 again:
  `VerificationContract.lint()` detected the duplicate ids and was called only from CI and
  tests, both running the one input incapable of failing it.
- *declared language coverage* — a per-stack renderer that silently returns nothing for some
  inputs. The frozen-surface index describes `.py` only, on **both** stacks.

**The pattern these share, which is the finding 2a exists to make structural.** None of them
is a missing registry — they are correct machinery wired to fewer paths than it claims. The
registries were the thing this step was chartered to inventory; the wiring is where the bugs
were. Three defects in one working session, all this shape (#846, #707, #849).

**A membership matrix alone would pass today**, since both stacks are complete on all six
registries. That is exactly why it is not the only check here: a test that passes the moment
it is written has described the system rather than closed it.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

from squadops.capabilities import (
    dev_capabilities,
    scaffold,
    scaffold_contract,
    verification_scaffold_emission,
)
from squadops.capabilities.handlers import build_profiles, probe_runner
from squadops.capabilities.scaffold import InterfaceManifest
from squadops.cycles.verification_contract import VerificationContract
from squadops.sandbox import environment

pytestmark = [pytest.mark.domain_capabilities]

_REPO = pathlib.Path(__file__).resolve().parents[3]
_REFERENCE = _REPO / "examples" / "03_group_run" / "interface_manifest.yaml"

_STACK_NAMES = sorted(scaffold._STACKS)


# --------------------------------------------------------------------------- #
# The six registries, and how a stack reaches each
# --------------------------------------------------------------------------- #

#: ``registry name -> (mapping, ScaffoldStack field or None)``. Recording *how* a stack
#: addresses each registry is what makes this an inventory rather than a list, and it is the
#: distinction #838 turned into a live defect.
#:
#: Three are reached by an explicit ``ScaffoldStack`` field. Two are reached by naming
#: convention — the stack's own name is the key, with nothing declaring the link — and
#: **both convention-bound registries are the ones that broke**. That is not a design
#: distinction; it is the order the bugs arrived in.
#:
#: The field name is recorded rather than inferred. Inferring it does not work: stack #1's
#: ``criteria_pack`` *is* ``"fullstack_fastapi_react"``, so a value that happens to equal a
#: stack name proves nothing about how it was reached — which is the same confusion that let
#: two registries stay convention-bound without anyone deciding they should be.
_REGISTRIES: dict[str, tuple[dict, str | None]] = {
    "criteria_pack (emitter)": (scaffold_contract._CRITERIA_PACKS, "criteria_pack"),
    "probe_profile (boot)": (probe_runner._PROFILES, "probe_profile"),
    "dev_capability": (dev_capabilities.DEV_CAPABILITIES, "dev_capability"),
    "sandbox contract": (environment._CONTRACTS, None),
    "build profile": (build_profiles.BUILD_PROFILES, None),
    "verification_scaffold (test-scaffold emitter)": (
        verification_scaffold_emission._EMITTERS,
        "verification_scaffold",
    ),
}

#: Registries a stack joins by explicit opt-in (SIP-0104 §8): an EMPTY field is a declared
#: state — the stack has not opted in and emission skips — not a membership gap. A
#: NON-empty field must still resolve (declared-but-unregistered is the #838 class and
#: fails membership below). Pinned like _CONVENTION_BOUND so growth is deliberate.
_OPT_IN = frozenset({"verification_scaffold (test-scaffold emitter)"})

#: Registries with no declaring field. Pinned so the count can only shrink: converting one
#: to an explicit ``ScaffoldStack`` field is an improvement and updates this set, while
#: adding a third has to be a deliberate edit rather than a default. Both entries have
#: already produced a live defect (#829-class, #838).
_CONVENTION_BOUND = frozenset({"sandbox contract", "build profile"})


def _registry_key(stack_name: str, field: str | None) -> str:
    stack = scaffold._STACKS[stack_name]
    return stack_name if field is None else str(getattr(stack, field))


def _manifest_for(stack: str) -> InterfaceManifest:
    """The reference design, expressed as ``stack`` requires it (#859).

    Not a plain re-stack any more. Stack #2 serves API handlers and pages from one routing
    tree, so its API paths must be distinguishable from its page paths — the reference's
    `/runs` API beside its `/runs/:id` page is a collision Next refuses. The shared fixture
    owns that per-stack clause so a third stack adds one there rather than here.
    """
    from tests.unit.capabilities._stack_fixtures import manifest_for_stack

    return manifest_for_stack(stack)


def _contract_for(stack: str) -> VerificationContract:
    return VerificationContract.from_dict(
        scaffold_contract.emit_contract_dict(_manifest_for(stack))
    )


# --------------------------------------------------------------------------- #
# Membership
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("registry", sorted(_REGISTRIES))
@pytest.mark.parametrize("stack", _STACK_NAMES)
def test_every_stack_has_a_member_in_every_registry(stack, registry):
    """#838's class. A stack absent from a registry fails where that registry is read, which
    on the two convention-bound ones was a swallowed exception and a silently unscaffolded
    build — the wrong answer being the only one that worked."""
    mapping, field = _REGISTRIES[registry]
    key = _registry_key(stack, field)
    if not key and registry in _OPT_IN:
        return  # declared non-membership: the stack has not opted in (SIP-0104 §8)
    assert key, f"stack {stack!r} resolves an empty key for {registry!r}"
    assert key in mapping, (
        f"stack {stack!r} addresses {registry!r} as {key!r}, which is not registered "
        f"(known: {sorted(mapping)})"
    )


def test_the_convention_bound_registries_are_the_declared_ones():
    """Which registries lack a declaring field is a fact worth pinning, not a comment."""
    actual = {name for name, (_, field) in _REGISTRIES.items() if field is None}
    assert actual == _CONVENTION_BOUND, (
        f"convention-bound registries changed: {sorted(actual)} vs declared "
        f"{sorted(_CONVENTION_BOUND)} — update _CONVENTION_BOUND and say which way it moved"
    )


# --------------------------------------------------------------------------- #
# The contract each stack derives
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("stack", _STACK_NAMES)
def test_every_fill_slot_is_reachable_by_a_criteria_ref(stack):
    """#849, generalized past the duplicate ids that caused it.

    ``criterion_index()`` is keyed on id, so a slot whose criteria are all addressed by an
    id some other slot also claims is unreachable — the plan binds the ref, dispatch
    resolves it to the winner, and the loser is verified by nothing while every gate passes.
    Asserting *reachability* rather than *uniqueness* catches that however it arises: a
    collision, a slot emitting no criteria at all, or a future pack keying ids on something
    else that turns out not to be distinctive.
    """
    manifest = _manifest_for(stack)
    contract = _contract_for(stack)
    slots = set(scaffold.fill_slot_paths(manifest))
    reachable = {path for _, path in contract.criterion_index().values() if path}
    unreachable = sorted(slots - reachable)
    assert not unreachable, (
        f"stack {stack!r}: fill slot(s) {unreachable} are addressed by no resolvable "
        f"criterion id — a plan binding every ref it is offered would still leave these "
        f"verified by nothing"
    )


@pytest.mark.parametrize("stack", _STACK_NAMES)
def test_every_stack_derives_a_contract_that_passes_its_own_linter(stack):
    """The guard that existed and was never pointed at a contract that could fail it."""
    assert _contract_for(stack).lint() == []


# --------------------------------------------------------------------------- #
# Guard wiring — the shape all three of this session's defects shared
# --------------------------------------------------------------------------- #

#: Modules that exist to guard. Every public ``validate_*``/``lint``/``assess_*`` they define
#: is machinery whose whole value is being called; one without a production caller is a
#: guard that cannot fire.
_GUARD_MODULES = (
    "src/squadops/cycles/verification_contract.py",
    "src/squadops/cycles/manifest_gates.py",
    "src/squadops/cycles/implementation_plan.py",
    "src/squadops/cycles/authoring_failure.py",
    "src/squadops/cycles/preflight.py",
)


def _guard_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for rel in _GUARD_MODULES:
        tree = ast.parse((_REPO / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            n = node.name
            if n.startswith("_"):
                continue
            if n.startswith(("validate_", "assess_")) or n == "lint":
                names[n] = rel
    return names


def _production_call_names() -> set[str]:
    called: set[str] = set()
    for root in ("src", "adapters"):
        for path in (_REPO / root).rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover - unparseable source is its own failure
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if isinstance(fn, ast.Attribute):
                    called.add(fn.attr)
                elif isinstance(fn, ast.Name):
                    called.add(fn.id)
    return called


def test_every_guard_has_a_production_caller():
    """The defect shape this session produced three times, made mechanical.

    ``VerificationContract.lint()`` is the exhibit: it detected #849's duplicate ids exactly,
    and its only callers were ``scripts/dev/contract_gate.py`` and unit tests — both running
    the reference FastAPI manifest, whose ids cannot collide. A guard exercised solely by the
    one input incapable of failing it is indistinguishable from no guard, and it took a live
    run to notice.

    Tests and `scripts/` are deliberately NOT counted as callers. A guard that only CI calls
    does not protect a cycle.
    """
    guards = _guard_names()
    assert guards, "no guard-shaped callables found — the AST sweep is broken, not the code"
    orphans = sorted(set(guards) - _production_call_names())
    assert not orphans, (
        "guard(s) with no production caller: "
        + "; ".join(f"{n} ({guards[n]})" for n in orphans)
        + " — wire it where the artifact it guards is produced, or delete it"
    )


# --------------------------------------------------------------------------- #
# Declared language coverage
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("stack", _STACK_NAMES)
def test_frozen_index_describes_exactly_the_declared_suffixes(stack):
    """A renderer that returns nothing for some inputs must say which, or it reads as
    complete.

    The frozen-surface index names what each scaffold-owned file declares, and the plan
    appendix tells authors not to check a frozen file *unless the line proves it passes*.
    That rule needs a line. ``_python_surface`` handles ``.py`` only, so every non-Python
    frozen file renders as a bare name — and a Next.js author guessing into that vacuum is
    what produced #849's live rejection.

    The measurement that reframed it: **stack #1 renders 10 of 15 entries bare too**,
    including all of `frontend/`. This is not a stack-#2 gap, it is a language gap both
    stacks have always had. Asserting against the declared tuple keeps the two in step —
    extending the renderer without extending the declaration fails here, and so does the
    reverse.
    """
    manifest = _manifest_for(stack)
    described, bare = [], []
    for line in scaffold.frozen_surface_index_lines(manifest):
        name = line.split("`")[1]
        (described if "—" in line else bare).append(name)

    # One direction only, and the asymmetry is the honest part. A file with an UNDESCRIBED
    # suffix rendering declarations means the tuple is a lie. A file with a described suffix
    # rendering none does NOT: `backend/__init__.py` is empty, and an empty Python file
    # correctly has nothing to declare. Asserting both ways would have forced this test to
    # claim that every .py file declares something, which is false.
    # Coverage is declared on two axes: by suffix, and by basename for files whose
    # declaration surface is not a language's (package.json's dependency set, roll 9).
    for name in described:
        assert name.endswith(scaffold.DESCRIBED_FROZEN_SUFFIXES) or (
            name.rsplit("/", 1)[-1] in scaffold.DESCRIBED_FROZEN_BASENAMES
        ), (
            f"{name} renders declarations but is in neither DESCRIBED_FROZEN_SUFFIXES "
            f"{scaffold.DESCRIBED_FROZEN_SUFFIXES} nor DESCRIBED_FROZEN_BASENAMES "
            f"{scaffold.DESCRIBED_FROZEN_BASENAMES} — the declaration is now narrower "
            f"than the renderer"
        )

    # The reader must actually work on at least one file, or "everything is bare" would
    # satisfy the rule above while meaning the surface parser silently returns nothing.
    assert described, (
        f"stack {stack!r} renders NO declarations for any frozen file — every entry is a "
        f"bare name, so the appendix's 'unless the line proves it passes' rule has no line "
        f"anywhere and no frozen file may be checked at all"
    )


def test_the_ecmascript_surface_names_fields_not_just_types():
    """pf-42/pf-43's actual lesson, applied to the second stack.

    Those rolls did not fail because the author did not know `models.py` existed — they
    failed because it did not know the field was `location` and invented `meeting_location`,
    and because `store.py`'s module state was omitted so it wrote a task to build a store
    that already existed. **A name the author cannot see is a name it will invent.** An
    index that lists `RunEvent` without its fields is the same defect one level up, which is
    why the interface-name assertion below is not enough on its own.
    """
    surface = scaffold._ecmascript_surface(
        "import { z } from 'zod'\n"
        "export interface RunEvent {\n"
        "  id: string\n"
        "  location: string\n"
        "  distance?: string\n"
        "}\n"
        "export const ERROR_STATUS = {}\n"
        "export function reset(): void {}\n"
        "export async function load(): Promise<void> {}\n"
    )
    assert "`RunEvent(id: string, location: string, distance?: string)`" in surface
    assert "exports ERROR_STATUS" in surface
    assert "functions `reset(): void`, `load(): Promise<void>`" in surface
    assert "`zod`" in surface


def test_the_ecmascript_surface_is_empty_for_files_that_declare_nothing():
    """Config and data files must render bare rather than as noise — the bare/described
    split is what the appendix's rule keys on."""
    assert scaffold._ecmascript_surface("// a comment only\nconst private = 1\n") == ""


# --------------------------------------------------------------------------- #
# #861 — the developer receives what the frozen files declare
# --------------------------------------------------------------------------- #


def test_the_developer_is_told_what_the_frozen_files_declare():
    """Roll 7 died of this. `development.develop` writes `app/api/runs/route.ts`, whose job
    is calling into the frozen `lib/store.ts`, and emitted
    `import { runStore } from '@/lib/store'` against a module exporting
    `reset, all, insert, find, nextId`. The repair invented the same name again, because it
    was blind identically, so the correction terminated as `plan_defect` on a defect no
    repair could see.

    The index carrying the answer has existed since pf-42 and reached the plan author only.
    Asserted on the derived fragment rather than on the registry flag: the question is
    whether the exports reach the prompt, and a flag can be set while the deriver returns
    nothing (which is what `.py`-only rendering did to this stack before #851).
    """
    from squadops.capabilities.context_assembly import (
        CONTEXT_CONTRACTS,
        SURFACE_FROZEN,
        manifest_surface_fragments,
    )

    contract = CONTEXT_CONTRACTS["development.develop"]
    assert SURFACE_FROZEN in contract.manifest_surfaces

    fragments = manifest_surface_fragments(contract, _manifest_for("nextjs_ts"))
    rendered = "\n".join(fragments.get(SURFACE_FROZEN, []))
    assert "lib/store.ts" in rendered
    assert "reset" in rendered and "insert" in rendered, (
        "the developer must be told which symbols the frozen store exports — this is the "
        "exact line roll 7 needed and did not have"
    )


@pytest.mark.parametrize("stack", _STACK_NAMES)
def test_the_frozen_surface_reaches_the_developer_on_every_stack(stack):
    """Parameterized over the registry: a third stack inherits the wiring or fails here."""
    from squadops.capabilities.context_assembly import (
        CONTEXT_CONTRACTS,
        SURFACE_FROZEN,
        manifest_surface_fragments,
    )

    fragments = manifest_surface_fragments(
        CONTEXT_CONTRACTS["development.develop"], _manifest_for(stack)
    )
    assert fragments.get(SURFACE_FROZEN), (
        f"stack {stack!r} threads no frozen-surface lines to the developer"
    )


# --------------------------------------------------------------------------- #
# #863 — the index publishes how to CALL a frozen function, not just its name
# --------------------------------------------------------------------------- #


def test_the_frozen_store_publishes_its_call_signatures():
    """Roll 8's defect. The developer imported the right symbol from the right module and
    wrote `all()` against `all(table)`; tsc rejected it and the correction terminated.

    pf-42 gave classes their fields and left functions as bare names, so the index published
    a symbol's existence and withheld how to call it — in both language readers. Same
    sentence as pf-42, one level down: a signature the author cannot see is a signature it
    will guess.
    """
    line = next(
        line
        for line in scaffold.frozen_surface_index_lines(_manifest_for("nextjs_ts"))
        if "lib/store.ts" in line
    )
    assert "`all(table: string)" in line, "the arity roll 8 guessed wrong must be visible"
    assert "`insert(table: string, row: Record<string, unknown>)" in line
    assert "`reset()" in line, "a zero-argument function must show empty parens, not a bare name"


def test_a_generic_function_still_publishes_its_parameters():
    """`lib/api.ts` declares `export async function api<T>(path, init?)`.

    A first version of the #863 pattern required the argument list to follow the name
    directly, so the generic clause made this file render as a bare name — a file that had
    been described before the fix became undescribed by it. Caught before commit; pinned so
    it cannot return.
    """
    line = next(
        line
        for line in scaffold.frozen_surface_index_lines(_manifest_for("nextjs_ts"))
        if "lib/api.ts" in line
    )
    assert "`api(path: string, init?: RequestInit): Promise<T>`" in line


@pytest.mark.parametrize("stack", _STACK_NAMES)
def test_no_frozen_function_is_published_without_parentheses(stack):
    """Every stack, every frozen file: a function named without parens is a signature the
    author has to guess. Parameterized over the registry so a third stack's reader inherits
    the requirement or fails here."""
    for line in scaffold.frozen_surface_index_lines(_manifest_for(stack)):
        if "functions " not in line:
            continue
        listed = line.split("functions ", 1)[1].split(";")[0]
        # Two legitimate formats (#871): the ECMAScript reader wraps each typed signature
        # in backticks (commas inside `Record<string, unknown>` would otherwise read as
        # list separators); the Python reader stays names-only and bare. Splitting on
        # ", " would cut `insert(table, row)` in half — which the first version of this
        # test did, reporting the code broken when the test was.
        if "`" in listed:
            signatures = re.findall(r"`([^`]+)`", listed)
            for signature in signatures:
                assert re.match(r"\w+\(.*\)", signature), (
                    f"{stack}: {signature!r} is published without a call signature — {line}"
                )
            remainder = re.sub(r"`[^`]+`", "", listed).strip(" ,")
        else:
            signatures = re.findall(r"\w+\([^)]*\)", listed)
            remainder = re.sub(r"\w+\([^)]*\)", "", listed).strip(" ,")
        assert signatures, f"{stack}: no signatures published — {line}"
        assert not remainder, (
            f"{stack}: {remainder!r} is published without a call signature — {line}"
        )


def test_a_type_containing_commas_does_not_invent_parameters():
    """`insert(table: string, row: Record<string, unknown>)` has two parameters, not three.

    Splitting the argument list on every comma would read the generic's comma as a separator
    and publish a parameter that does not exist — teaching an author to pass three arguments
    to a two-argument function, which is the same defect this fix exists to remove.
    """
    surface = scaffold._ecmascript_surface(
        "export function insert(table: string, row: Record<string, unknown>): void {}\n"
    )
    assert "`insert(table: string, row: Record<string, unknown>): void`" in surface


# --------------------------------------------------------------------------- #
# #871 — the TS surface publishes types, returns, and classes (roll 12)
# --------------------------------------------------------------------------- #


def test_the_frozen_store_publishes_its_types_and_returns():
    """Roll 12's repair invented a numeric-id scheme in exactly the blind spot names-only
    left: `find(table, id)` concealed `id: string` and `nextId()` concealed its `string`
    return, so the repair wrote `find('runs', Number(run_id))`, the tree stopped compiling,
    and the run terminated. The types are literal in the frozen source — publishing them is
    the same sentence as #863, one level down: a type the author cannot see is a type it
    will guess."""
    line = next(
        line
        for line in scaffold.frozen_surface_index_lines(_manifest_for("nextjs_ts"))
        if "lib/store.ts" in line
    )
    assert "`find(table: string, id: string)" in line, (
        "the parameter type roll 12's repair guessed wrong must be visible"
    )
    assert "`nextId(): string`" in line, (
        "the return type the invented numeric-id scheme contradicts must be visible"
    )


def test_the_frozen_error_class_is_named_with_its_constructor():
    """`export class` had no reader clause, so `ApiError` — the one seam the error contract
    expects every route to use — was absent from the errors.ts line. Roll 12's original
    defect is the invention that predicts: the route passed a bare string to
    `errorResponse()` (TypeScript-legal, the param is `unknown`), `instanceof ApiError`
    failed at runtime, and every error path returned 500 where the contract pins 422/409."""
    line = next(
        line
        for line in scaffold.frozen_surface_index_lines(_manifest_for("nextjs_ts"))
        if "lib/errors.ts" in line
    )
    assert "classes `ApiError(code: string, detail: string = '')`" in line
    assert "`errorResponse(err: unknown): Response`" in line, (
        "the catch-seam signature must publish the type that forbids bare-string calls"
    )


def test_a_constructor_is_attributed_to_its_own_class():
    """The constructor search is bounded at the next top-level export: without the bound, a
    constructor-less first class would claim the NEXT class's constructor and publish a call
    signature that throws at runtime."""
    surface = scaffold._ecmascript_surface(
        "export class Marker extends Error {}\n"
        "export class Payload {\n"
        "  constructor(public body: string) {}\n"
        "}\n"
    )
    assert "`Marker()`" in surface
    assert "`Payload(body: string)`" in surface
