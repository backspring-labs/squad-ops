"""Stack #2's behavior-shell emitter — the nextjs_ts test scaffold (SIP-0104 P1).

A separate module for the same reason ``stack_nextjs_ts`` is: shell templates are stack-#2
vocabulary and belong beside it, not interleaved with the stack-neutral orchestration in
``verification_scaffold_emission``.

Derivation sources, per the contract's precedence (``verification_scaffold``):

- **behavior inventory, request bodies, expected statuses** ← the verification contract's
  behavioral probes (``scaffold_contract._probes`` — the same derivation the probe runner
  executes, so a shell and its probe cannot disagree; SIP §5's dedup rule depends on this);
- **route-file placement and import targets** ← the expanded tree (checked, never assumed);
- **invocation form** ← the stack's taught execution model (#877): import the handler,
  invoke with ``new Request(...)``, pass ``{ params }`` for parameterized routes.

The v1 required-coverage inventory, stated so omissions read as omissions (demote, don't
guess — SIP §4.1):

- one shell per behavioral probe (create, blank-rejection, child action, duplicate-conflict),
  each an in-process twin of its probe;
- a shell per parameterless GET endpoint (declared success status, 200 default);
- success + unknown-id shells per single-parameter GET under a create whose response entity
  declares ``id`` (the probe capture rule applied to reads); the unknown-id shell exists only
  when the endpoint declares an error code the error contract maps to 404.

NOT in the inventory (the qa author's additive surface): PUT/DELETE endpoints,
multi-parameter paths, parameterized GETs with no create chain, and all DOM behavior.

Chained state is derived from the probe list's own sequence semantics: the probe runner
executes probes in order against one app instance, so a child probe's precondition is the
success of the child probes before it. A shell is test-isolated (``beforeEach(reset)``), so
it replays that prefix in-process: create, then each earlier child success, then its own
invocation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from squadops.capabilities.scaffold_contract import _slug
from squadops.capabilities.stack_nextjs_ts import _segments
from squadops.capabilities.verification_scaffold import (
    BehaviorSlot,
    ScaffoldDerivationError,
    slot_begin_marker,
    slot_end_marker,
)

if TYPE_CHECKING:  # pragma: no cover - annotations only
    from squadops.capabilities.scaffold import InterfaceManifest

#: Where every emitted shell lives. Inside the stack's ``__tests__`` namespace so the
#: vitest include pattern collects it; the ``.scaffold.test.ts`` suffix marks provenance.
logger = logging.getLogger(__name__)

SCAFFOLD_TEST_DIR = "__tests__/scaffold"

_STORE_PATH = "lib/store.ts"
_URL_BASE = "http://test"  # the host the stack's taught execution model uses (#877)


def _route_file(url_path: str) -> str:
    """Declared URL → owning route file — the same derivation as the expander (bend 1)."""
    return f"app/{_segments(url_path)}/route.ts".replace("//", "/")


def _alias(route_file: str) -> str:
    """Deterministic import alias: ``app/api/runs/[run_id]/route`` → ``routeApiRunsRunId``."""
    parts = route_file.removeprefix("app/").removesuffix("/route.ts").split("/")
    words: list[str] = []
    for part in parts:
        for word in re.split(r"[^a-zA-Z0-9]+", part.strip("[]")):
            if word:
                words.append(word[0].upper() + word[1:])
    return "route" + "".join(words)


def _placeholders(url_path: str) -> list[str]:
    return re.findall(r"\{(\w+)\}", url_path)


@dataclass(frozen=True)
class _Step:
    """One handler invocation: method + declared URL path + optional JSON body.

    ``param_expr`` is the TypeScript expression for the single path parameter's value
    (``"created.id"`` for chained steps, ``"'missing'"`` for the unknown-id shell, ``""``
    for parameterless paths).
    """

    method: str
    url_path: str
    body: Any = None
    param_expr: str = ""


@dataclass(frozen=True)
class _Behavior:
    """One behavior shell: its identity, provenance, and invocation plan."""

    behavior_id: str
    label: str
    expect_status: int
    final: _Step
    probe_id: str = ""
    prerequisites: tuple[_Step, ...] = field(default=())


def _fail_missing_surface(url_path: str, method: str, route_file: str, reason: str) -> None:
    raise ScaffoldDerivationError(
        f"the interface manifest declares {method} {url_path}, but the expanded tree "
        f"{reason} ({route_file}). The generator never reconciles this by inference "
        f"(SIP-0104 §7): by construction the tree is expand(manifest), so this implies "
        f"generator-version drift or a mutated workspace."
    )


def _require_surfaces(behaviors: list[_Behavior], expanded: dict[str, str]) -> None:
    """Every invoked handler must exist in the tree the imports resolve against."""
    if _STORE_PATH not in expanded:
        raise ScaffoldDerivationError(
            f"the expanded tree lacks {_STORE_PATH} — the store seam every shell's "
            f"lifecycle (beforeEach(reset)) imports. Generator-version drift or a mutated "
            f"workspace (SIP-0104 §7)."
        )
    for behavior in behaviors:
        for step in (*behavior.prerequisites, behavior.final):
            route_file = _route_file(step.url_path)
            content = expanded.get(route_file)
            if content is None:
                _fail_missing_surface(step.url_path, step.method, route_file, "has no file")
            elif f"export async function {step.method}" not in content:
                _fail_missing_surface(
                    step.url_path, step.method, route_file, f"does not export {step.method}"
                )


def _classify_probes(probes: list[dict]) -> list[tuple[str, dict]]:
    """Structurally classify each probe: create / reject / child / duplicate.

    Structural, not id-string, classification (the strings-boundary rule): a rejection twin
    is guarded by the scaffold; a child touches a parameterized path; a duplicate repeats an
    earlier child's exact request with a different expectation.
    """
    classified: list[tuple[str, dict]] = []
    seen_child_requests: set[str] = set()
    for probe in probes:
        request = probe.get("request", {})
        key = json.dumps(request, sort_keys=True)
        if probe.get("guards") == "scaffold":
            classified.append(("reject", probe))
        elif "{" in request.get("path", ""):
            if key in seen_child_requests:
                classified.append(("duplicate", probe))
            else:
                seen_child_requests.add(key)
                classified.append(("child", probe))
        else:
            classified.append(("create", probe))
    return classified


def _behaviors_from_probes(classified: list[tuple[str, dict]]) -> list[_Behavior]:
    creates_by_path: dict[str, dict] = {}
    child_successes: list[dict] = []
    behaviors: list[_Behavior] = []

    def _final(probe: dict, param_expr: str = "") -> _Step:
        request = probe["request"]
        return _Step(
            method=request["method"],
            url_path=request["path"],
            body=request.get("json"),
            param_expr=param_expr,
        )

    def _chain(request_path: str) -> tuple[_Step, ...]:
        parent_path = request_path.split("/{", 1)[0]
        parent = creates_by_path.get(parent_path)
        if parent is None:
            # No create to chain from — the behavior is underivable, and underivable
            # elements are demoted, never guessed (SIP §4.1). Signalled with None below.
            return ()
        steps = [_final(parent)]
        for earlier in child_successes:
            if earlier["request"]["path"].split("/{", 1)[0] != parent_path:
                continue
            steps.append(_final(earlier, param_expr="created.id"))
        return tuple(steps)

    for kind, probe in classified:
        request = probe["request"]
        expect = probe["expect"]["status"]
        if kind == "create":
            creates_by_path[request["path"]] = probe
            label = f"{request['method']} {request['path']} -> {expect}"
            behaviors.append(
                _Behavior(
                    behavior_id=probe["id"],
                    label=label,
                    expect_status=expect,
                    final=_final(probe),
                    probe_id=probe["id"],
                )
            )
        elif kind == "reject":
            label = f"{request['method']} {request['path']} blank required fields -> {expect}"
            behaviors.append(
                _Behavior(
                    behavior_id=probe["id"],
                    label=label,
                    expect_status=expect,
                    final=_final(probe),
                    probe_id=probe["id"],
                )
            )
        else:
            prerequisites = _chain(request["path"])
            if not prerequisites:
                continue  # demoted: no derivable create chain for this child
            flavor = " duplicate" if kind == "duplicate" else ""
            # A duplicate's precondition includes its own first, successful firing —
            # which _chain already appended, because the original child probe was
            # recorded as a child success before its duplicate is classified.
            label = f"{request['method']} {request['path']}{flavor} -> {expect}"
            behaviors.append(
                _Behavior(
                    behavior_id=probe["id"],
                    label=label,
                    expect_status=expect,
                    final=_final(probe, param_expr="created.id"),
                    probe_id=probe["id"],
                    prerequisites=prerequisites,
                )
            )
            if kind == "child":
                child_successes.append(probe)
    return behaviors


def _minted_read_behaviors(
    manifest: InterfaceManifest, creates_by_path: dict[str, dict]
) -> list[_Behavior]:
    """GET shells the probe set does not carry: collection reads and reads-by-id."""
    error_http = {
        c.code: c.http
        for c in (manifest.api.error_contract.codes if manifest.api.error_contract else ())
    }
    entity_fields = {e.name: {f.name for f in e.fields} for e in manifest.entities}
    endpoints = {(ep.method, ep.path): ep for ep in manifest.api.endpoints}
    behaviors: list[_Behavior] = []
    for ep in manifest.api.endpoints:
        if ep.method != "GET":
            continue
        placeholders = _placeholders(ep.path)
        expect = ep.success_status or 200
        if not placeholders:
            behaviors.append(
                _Behavior(
                    behavior_id=f"vs-get-{_slug(ep.path) or 'root'}",
                    label=f"GET {ep.path} -> {expect}",
                    expect_status=expect,
                    final=_Step(method="GET", url_path=ep.path),
                )
            )
            continue
        if len(placeholders) != 1:
            continue  # multi-parameter reads are not derivable in v1 — demoted
        parent_path = ep.path.split("/{", 1)[0]
        create_probe = creates_by_path.get(parent_path)
        parent_ep = endpoints.get(("POST", parent_path))
        parent_entity = getattr(parent_ep, "response", "") if parent_ep else ""
        if create_probe is None or "id" not in entity_fields.get(parent_entity or "", set()):
            continue  # no derivable create chain — demoted
        create_step = _Step(
            method="POST",
            url_path=create_probe["request"]["path"],
            body=create_probe["request"].get("json"),
        )
        behaviors.append(
            _Behavior(
                behavior_id=f"vs-get-{_slug(ep.path) or 'root'}",
                label=f"GET {ep.path} -> {expect}",
                expect_status=expect,
                final=_Step(method="GET", url_path=ep.path, param_expr="created.id"),
                prerequisites=(create_step,),
            )
        )
        if any(error_http.get(code) == 404 for code in ep.errors):
            behaviors.append(
                _Behavior(
                    behavior_id=f"vs-get-{_slug(ep.path) or 'root'}-not-found",
                    label=f"GET {ep.path} unknown id -> 404",
                    expect_status=404,
                    final=_Step(method="GET", url_path=ep.path, param_expr="'missing'"),
                )
            )
    return behaviors


# --------------------------------------------------------------------------- rendering


def _url_expr(step: _Step) -> str:
    """The Request URL for a step: a plain string, or a template literal for chained ids."""
    placeholders = _placeholders(step.url_path)
    if not placeholders:
        return f"'{_URL_BASE}{step.url_path}'"
    name = placeholders[0]
    if step.param_expr == "created.id":
        return "`" + _URL_BASE + step.url_path.replace("{" + name + "}", "${created.id}") + "`"
    literal = step.param_expr.strip("'")
    return f"'{_URL_BASE}{step.url_path.replace('{' + name + '}', literal)}'"


def _invocation_lines(step: _Step, assign: str) -> list[str]:
    """One handler invocation, rendered exactly as the execution model teaches (#877)."""
    alias = _alias(_route_file(step.url_path))
    placeholders = _placeholders(step.url_path)
    open_line = f"{assign}await ({alias}.{step.method} as Handler)("
    if step.body is not None:
        request_lines = [
            f"      new Request({_url_expr(step)}, {{",
            f"        method: '{step.method}',",
            "        headers: { 'content-type': 'application/json' },",
            f"        body: JSON.stringify({json.dumps(step.body)}),",
            "      }),",
        ]
    else:
        request_lines = [f"      new Request({_url_expr(step)}),"]
    lines = [f"    {open_line}", *request_lines]
    if placeholders:
        lines.append(f"      {{ params: {{ {placeholders[0]}: {step.param_expr} }} }},")
    lines.append("    )")
    return lines


def _shell_source(behavior: _Behavior) -> str:
    """Render one behavior shell file: frozen spine plus one empty fill slot."""
    route_files = list(
        dict.fromkeys(
            _route_file(step.url_path) for step in (*behavior.prerequisites, behavior.final)
        )
    )
    slot_id = f"slot-{behavior.behavior_id}"
    lines = [
        "// Deterministic verification scaffold (SIP-0104). GENERATED — DO NOT EDIT.",
        "// The spine — placement, imports, lifecycle, invocation, status assertion — is",
        "// frozen (SIP-0104 §4.2); the marked fill slot is the qa author's mutable surface.",
        "import { beforeEach, describe, expect, it } from 'vitest'",
        # `all` is imported for the FILL, not for the spine (#936). The spine only calls
        # `reset`, but a fill may not add imports — "Assertions only. NO imports" — so any
        # store helper the fill vocabulary teaches must already be in scope here or the
        # fill cannot run. The appendix's own worked examples call `all('runs')`, and
        # every one of them died on `ReferenceError: all is not defined` until this line.
        # Keep this in step with the vocabulary the appendix teaches.
        "import { reset, all } from '@/lib/store'",
    ]
    for route_file in route_files:
        module = route_file.removesuffix(".ts")
        lines.append(f"import * as {_alias(route_file)} from '@/{module}'")
    lines += [
        "",
        "type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response",
        "",
        "beforeEach(() => reset())",
        "",
        f"describe('scaffold: {behavior.final.method} {behavior.final.url_path}', () => {{",
        f"  it('{behavior.label} [{behavior.behavior_id}]', async () => {{",
    ]
    for index, step in enumerate(behavior.prerequisites):
        if index == 0:
            lines += _invocation_lines(step, assign="const createRes = ")
            lines.append("    const created: any = await createRes.json().catch(() => ({}))")
        else:
            lines += _invocation_lines(step, assign="")
    lines += _invocation_lines(behavior.final, assign="const res = ")
    lines += [
        f"    expect(res.status).toBe({behavior.expect_status})",
        "    const body: any = await res.json().catch(() => ({}))",
        f"    {slot_begin_marker(slot_id)}",
        "    // FILL (qa): domain assertions for this behavior — response values and store",
        "    // effects beyond the declared status. `body` is the parsed response JSON.",
        "    void body",
        f"    {slot_end_marker(slot_id)}",
        "  })",
        "})",
        "",
    ]
    return "\n".join(lines)


def derive_scaffold_behaviors(
    manifest: InterfaceManifest,
) -> tuple[list[_Behavior], list[dict]]:
    """The behaviours this manifest yields, and the probes half of them derive from.

    Extracted so the coverage report (#951) reads the **same** derivation the emitter
    runs rather than a parallel reimplementation of it. A coverage report that computes
    its own answer is worse than none: it would drift from the shells silently and
    report a delta that is itself wrong.
    """
    from squadops.capabilities.scaffold_contract import emit_contract_dict

    contract = emit_contract_dict(manifest)
    probes = contract["behavioral"]["probes"]
    classified = _classify_probes(probes)
    behaviors = _behaviors_from_probes(classified)
    creates_by_path = {
        probe["request"]["path"]: probe for kind, probe in classified if kind == "create"
    }
    behaviors += _minted_read_behaviors(manifest, creates_by_path)
    return behaviors, probes


def emit_nextjs_ts_verification_scaffold(
    manifest: InterfaceManifest, expanded: list[dict[str, str]]
) -> list[tuple[str, str, tuple[BehaviorSlot, ...]]]:
    """The stack-#2 behavior shells: ``(path, content, slots)`` per emitted file.

    One behavior per file, so a degraded fill degrades one slot's file and attribution
    stays per-behavior. Deterministic order: probe twins in probe order, then minted read
    shells in endpoint declaration order.
    """
    from squadops.capabilities.scaffold_coverage import (
        probe_routes,
        slot_routes,
        summarize_coverage,
    )

    behaviors, probes = derive_scaffold_behaviors(manifest)

    # #951: the scaffold covers what it can DERIVE, not what the manifest DECLARES, and
    # the difference used to be recorded nowhere — so silence read as coverage. Roll 2
    # banked green with join and leave, the whole point of the app, untouched by every
    # deterministic layer. Emitting the delta here costs nothing and changes no shell
    # byte (Gate 1's pins and GENERATOR_VERSION are untouched); it is a report, not a
    # gate, because whether an uncovered endpoint should BLOCK is a separate ruling.
    coverage = summarize_coverage(
        [(ep.method, ep.path) for ep in manifest.api.endpoints],
        probe_routes(probes),
        slot_routes(behaviors),
    )
    log = logger.warning if coverage.uncovered else logger.info
    log("verification scaffold %s", coverage.summary())

    tree = {f["name"]: f["content"] for f in expanded}
    _require_surfaces(behaviors, tree)

    alias_owners: dict[str, str] = {}
    for behavior in behaviors:
        for step in (*behavior.prerequisites, behavior.final):
            route_file = _route_file(step.url_path)
            owner = alias_owners.setdefault(_alias(route_file), route_file)
            if owner != route_file:
                raise ScaffoldDerivationError(
                    f"route files {owner!r} and {route_file!r} derive the same import alias "
                    f"{_alias(route_file)!r} — the generator cannot emit unambiguous imports "
                    f"for this manifest."
                )

    emitted: list[tuple[str, str, tuple[BehaviorSlot, ...]]] = []
    for behavior in behaviors:
        slot = BehaviorSlot(
            slot_id=f"slot-{behavior.behavior_id}",
            behavior=behavior.label,
            probe_id=behavior.probe_id,
            criterion_ids=(behavior.probe_id,) if behavior.probe_id else (),
        )
        path = f"{SCAFFOLD_TEST_DIR}/{behavior.behavior_id}.scaffold.test.ts"
        emitted.append((path, _shell_source(behavior), (slot,)))
    return emitted
