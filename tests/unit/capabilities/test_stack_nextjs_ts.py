"""Stack #2 — the Next.js + TypeScript skeleton (#822, Stage 1c).

The second real stack the Stack Blueprint SIP's acceptance gate requires. What matters here is
not that it expands, but *where it disagrees with stack #1* — those disagreements are S3's
evidence, and a test suite that only proved it works would hide them.

Bug classes guarded:

- **stack #1 moving.** Its contract and manifest hashes are what every bind-mode cycle and the
  1.4 banked evidence key on; a second registration must be inert for it;
- **the API collapsing to one fill slot** (bend 1). Next derives the URL from the directory, so
  five endpoints across four paths are four files. A partition that returned one would put
  every endpoint in a file that cannot serve them;
- **path parameters surviving untranslated** (bend 2) — `{run_id}` reaching disk would create a
  literal `{run_id}` directory that Next never routes;
- **the skeleton passing its own probes.** A stub that returns success would make the
  behavioral gate measure the scaffold instead of the fill (SIP-0098 §7);
- a fill slot that is not expanded, or an expanded file claimed as a slot — the two halves
  disagreeing is how a plan claims a file that does not exist;
- **the pack demanding Python of a stack that has none**, which is what stack #1's
  `tests_pass: CAP_PYTHON` would have done before #818 gave each stack its own pack;
- the five per-stack registries drifting apart.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from squadops.capabilities import scaffold, scaffold_contract
from squadops.capabilities.dev_capabilities import DEV_CAPABILITIES, TEST_FRAMEWORK_VITEST
from squadops.capabilities.handlers import probe_runner as pr
from squadops.capabilities.scaffold import InterfaceManifest, expand, fill_slot_paths
from squadops.capabilities.scaffold_contract import emit_contract_dict, emit_contract_yaml
from squadops.sandbox.environment import get_environment_contract

pytestmark = [pytest.mark.domain_capabilities]

_STACK = "nextjs_ts"
_REFERENCE_SRC = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
).read_text(encoding="utf-8")


def _manifest(stack: str = _STACK) -> InterfaceManifest:
    """The reference design as this stack requires it declared (#859): API under `/api`,
    because App Router serves route handlers and pages from one tree."""
    from tests.unit.capabilities._stack_fixtures import manifest_for_stack

    return manifest_for_stack(stack)


def _names(manifest: InterfaceManifest) -> list[str]:
    return [f["name"] for f in expand(manifest)]


# --------------------------------------------------------------------------- #
# Stack #1 is untouched
# --------------------------------------------------------------------------- #


def test_registering_a_second_stack_leaves_the_first_byte_identical():
    """The release's banked evidence is bound to these two hashes."""
    reference = _manifest("fullstack_fastapi_react")

    assert reference.content_hash().startswith("bb472e267e53d5ad")
    # contract v10 (#1079): v9 plus json_has on the success probes, classified
    # ambiguity_removal — see test_contract_derivation_reference for both pins.
    assert (
        hashlib.sha256(emit_contract_yaml(reference).encode())
        .hexdigest()
        .startswith("bdd540d0d916e085")
    )


# --------------------------------------------------------------------------- #
# Bend 1 — the API is many fill slots
# --------------------------------------------------------------------------- #


def test_five_endpoints_across_four_paths_become_four_route_files():
    """The structural disagreement between the two stacks, and the most valuable thing this
    stack surfaces. Stack #1 holds every endpoint in one `backend/routes.py`."""
    manifest = _manifest()
    routes = [p for p in fill_slot_paths(manifest) if p.startswith("app/api/")]

    assert len(manifest.api.endpoints) == 5
    assert routes == [
        "app/api/runs/route.ts",
        "app/api/runs/[run_id]/route.ts",
        "app/api/runs/[run_id]/join/route.ts",
        "app/api/runs/[run_id]/leave/route.ts",
    ]


def test_the_two_endpoints_sharing_a_path_share_a_file():
    """`GET /runs` and `POST /runs` are one file exporting two handlers — the grouping is by
    path, which is what makes the count four rather than five."""
    content = next(
        f["content"] for f in expand(_manifest()) if f["name"] == "app/api/runs/route.ts"
    )

    assert "export async function GET(" in content
    assert "export async function POST(" in content


def test_the_contract_names_every_route_file_as_a_fill_slot():
    """A slot the contract does not cover ships unverified; a covered path that is not
    expanded is a plan claiming a file that does not exist."""
    manifest = _manifest()
    contract = emit_contract_dict(manifest)

    assert set(contract["fill_files"]) == set(fill_slot_paths(manifest))
    assert set(fill_slot_paths(manifest)) <= set(_names(manifest))


# --------------------------------------------------------------------------- #
# Bend 2 — path parameters translate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("declared", "placed"),
    [("{run_id}", "[run_id]"), (":id", "[id]")],
)
def test_declared_path_parameters_are_placed_as_bracket_directories(declared, placed):
    """Third convention after `{run_id}` and Express's `:run_id` (#820 trigger 3). An
    untranslated parameter creates a literal directory Next never routes."""
    names = " ".join(_names(_manifest()))

    assert placed in names
    assert declared not in names


# --------------------------------------------------------------------------- #
# The skeleton must fail its own probes
# --------------------------------------------------------------------------- #


def test_every_route_stub_throws_rather_than_returning_success():
    """SIP-0098 §7: if the bare skeleton answered its probes, the behavioral gate would be
    measuring the scaffold instead of the fill."""
    stubs = [
        f["content"]
        for f in expand(_manifest())
        if f["name"].startswith("app/api/") and f["name"].endswith("route.ts")
    ]

    assert stubs
    for content in stubs:
        assert "not_implemented" in content
        assert "TODO" in content


def test_the_declared_testids_reach_the_page_stub_as_required_anchors():
    """The QA suite queries these and nothing else; a stub that omitted them would leave the
    dev agent to rediscover them from the manifest it is not given."""
    page = next(f["content"] for f in expand(_manifest()) if f["name"] == "app/create/page.tsx")

    assert "create-run-form" in page


def test_the_frozen_package_declares_the_scripts_the_contract_runs():
    """`frontend_build` shells `npm run build` and the suite runs vitest; a package.json
    missing either turns both into environment skips rather than evidence."""
    pkg = json.loads(next(f["content"] for f in expand(_manifest()) if f["name"] == "package.json"))

    assert pkg["scripts"]["build"] == "next build"
    assert pkg["scripts"]["start"] == "next start"
    assert "vitest" in pkg["devDependencies"]


# --------------------------------------------------------------------------- #
# The pack
# --------------------------------------------------------------------------- #


def test_the_pack_requires_node_and_never_python():
    """Stack #1's pack emitted `tests_pass: CAP_PYTHON` unconditionally. Before #818 gave each
    stack its own pack, that demanded a Python toolchain of a stack that has none."""
    contract = emit_contract_dict(_manifest())

    assert contract["capabilities"] == ["node"]
    assert all(
        c["requires"] == "node"
        for c in (*contract["behavioral"]["build"], *contract["behavioral"]["suite"]["checks"])
    )


def test_every_fill_slot_carries_the_build_anchored_to_itself():
    """#641/#648: the check is attached to the file under evaluation so a failure repairs
    where the defect lives. Bend 5 records what that costs — seven whole-tree builds."""
    contract = emit_contract_dict(_manifest())

    for path, spec in contract["fill_files"].items():
        checks = [c for c in spec["implementation"] if c["check"] == "frontend_compiles"]
        assert checks, f"{path} has no static check at all"
        assert checks[0]["file"] == path
        assert checks[0]["project_dir"] == ".", "Next builds at the root, not in frontend/"


def test_the_behavioral_probes_transfer_unchanged():
    """S2's HTTP-constant containment paying off: probes are manifest-derived, so both stacks
    get the same five. This is the only tier that proves the endpoints answer."""
    assert len(emit_contract_dict(_manifest())["behavioral"]["probes"]) == len(
        emit_contract_dict(_manifest("fullstack_fastapi_react"))["behavioral"]["probes"]
    )


# --------------------------------------------------------------------------- #
# Five registries, one stack
# --------------------------------------------------------------------------- #


def test_the_stack_is_answered_by_every_registry():
    """Scaffold, criteria pack, probe profile, sandbox environment, dev capability. Forgetting
    one produces a plausible wrong answer rather than an error — the S1 failure, now guarded
    across all five."""
    stack = scaffold._STACKS[_STACK]

    assert stack.criteria_pack in scaffold_contract._CRITERIA_PACKS
    assert stack.probe_profile in pr._PROFILES
    assert stack.dev_capability in DEV_CAPABILITIES
    assert get_environment_contract(_STACK).app_port == 8000
    assert DEV_CAPABILITIES[stack.dev_capability].test_framework == TEST_FRAMEWORK_VITEST


def test_the_probe_profile_builds_before_it_boots():
    """`next start` serves `.next/`, which only `next build` produces. A profile that stopped
    at install would boot into "no production build found" and report it as a boot failure —
    the conflation #827 separated."""
    profile = pr.profile_for_stack(_STACK)

    assert profile is not None
    assert "next build" in " ".join(profile.prepare_argv)
    assert "start" in profile.boot_argv


def test_the_probe_prepare_installs_without_a_lockfile():
    """Roll 10 (cyc_43a216d43e1e): the scaffold emits no `package-lock.json` — an
    offline-deterministic expansion cannot produce one — and `npm ci` EUSAGE-refuses
    without a lockfile, so every probe reported "subject preparation failed" and 4 of 11
    contract criteria went unverified. Two facts pinned together: as long as the expansion
    carries no lockfile, preparation must not use the lockfile-only installer."""
    names = _names(_manifest())
    profile = pr.profile_for_stack(_STACK)
    prepare = " ".join(profile.prepare_argv)

    assert not any(n.endswith(("package-lock.json", "npm-shrinkwrap.json")) for n in names)
    assert "npm ci" not in prepare
    assert "npm install" in prepare


def test_vitest_resolves_the_alias_the_stack_teaches():
    """Roll 10 (cyc_43a216d43e1e): every frozen file imports via `@/` and tsconfig declares
    the alias, but vitest resolves through vite, which does not read tsconfig paths — so the
    scaffold's own harness test failed collection ("Failed to load url @/lib/store") and
    `tests_pass` was unwinnable by construction. Three facts must agree, pinned from the
    EXPANDED files so a template edit cannot silently split them: tsconfig declares `@/*`,
    vitest.config declares the resolve alias, and the harness test uses the taught form."""
    files = {f["name"]: f["content"] for f in expand(_manifest())}

    tsconfig = json.loads(files["tsconfig.json"])
    assert "@/*" in tsconfig["compilerOptions"]["paths"]

    vitest_cfg = files["vitest.config.ts"]
    assert "resolve" in vitest_cfg and "alias" in vitest_cfg
    assert "'@': root" in vitest_cfg

    assert "from '@/lib/store'" in files["__tests__/harness.test.ts"]


def test_the_typed_check_vocabulary_is_declared_empty_not_guessed():
    """#503's conservative default. The AST evaluators are Python implementations never
    verified against this stack, so its checks must skip rather than be fed a guess."""
    assert scaffold.check_stack_for(_STACK) is None
    assert scaffold.check_stack_for("fullstack_fastapi_react") == "fastapi"


# --------------------------------------------------------------------------- #
# #859 — the file path is derived from the URL, and the tree must be coherent
# --------------------------------------------------------------------------- #


def _with_api_paths(paths: list[str], routes: list[str] | None = None) -> InterfaceManifest:
    """The reference design with its API paths (and optionally its pages) replaced."""
    from tests.unit.capabilities._stack_fixtures import manifest_dict_for_stack

    raw = manifest_dict_for_stack(_STACK)
    raw["api"]["endpoints"] = [
        {**raw["api"]["endpoints"][i], "path": p} for i, p in enumerate(paths)
    ]
    if routes is not None:
        raw["frontend"]["routes"] = [{**raw["frontend"]["routes"][0], "path": p} for p in routes]
    import yaml

    return InterfaceManifest.from_yaml(yaml.safe_dump(raw, sort_keys=False))


def test_the_route_file_serves_the_url_the_manifest_declared():
    """Roll 6's defect, stated as the invariant it violated.

    The expander used to prefix `app/api/` unconditionally, so a manifest declaring the true
    Next URL — `/api/runs`, which is what an App Router author writes and what the frontend
    fetches — produced `app/api/api/runs/route.ts`. That file serves `/api/api/runs` while
    the contract's probes request `/api/runs`, so the app could never answer its own
    verification and the correction chain looped until the 7200s budget ended the run.
    """
    slots = fill_slot_paths(_with_api_paths(["/api/runs"]))

    assert "app/api/runs/route.ts" in slots
    assert not any("api/api" in s for s in slots), (
        "the declared URL was prefixed twice — the emitted file cannot serve the path the "
        "contract probes request"
    )


def test_an_unprefixed_api_path_is_placed_where_it_will_actually_serve():
    """`path` means the served URL on every stack, so `/runs` yields `app/runs/route.ts`.

    The correctness of that placement is the reason the collision guard below has to exist:
    the prefix is no longer supplied silently, so nothing keeps API files out of the page
    tree except the manifest's own paths.
    """
    slots = fill_slot_paths(_with_api_paths(["/runs"], routes=["/"]))

    assert "app/runs/route.ts" in slots


def test_an_api_path_colliding_with_a_page_is_refused():
    """A directory cannot hold both `route.ts` and `page.tsx`; Next serves one path from one
    file. Refusing is deliberate — silently relocating one would ship an app answering
    different URLs than its own contract, which is the failure this change ends."""
    with pytest.raises(ValueError, match="both a route handler and a page"):
        fill_slot_paths(_with_api_paths(["/runs"], routes=["/runs"]))


def test_two_paths_disagreeing_on_a_slug_name_are_refused():
    """The reference manifest's own shape: API `/runs/{run_id}` beside page `/runs/:id`.

    Next requires one slug name per dynamic segment, so these cannot coexist — which is why
    declaring the API under `/api` is now a requirement of this stack rather than a
    convention the expander supplied. Pinned with the exact pair that would otherwise have
    shipped, since the reference is the design every other stack test is built from.
    """
    with pytest.raises(ValueError, match="same position in the routing tree"):
        fill_slot_paths(_with_api_paths(["/runs/{run_id}"], routes=["/runs/:id"]))


# --------------------------------------------------------------------------- #
# The qa supplement states how the suite executes (#877)
# --------------------------------------------------------------------------- #


def test_the_test_supplement_states_the_serverless_execution_model():
    """Roll 14 (cyc_25b4a9b0b637): the qa author wrote live-`fetch` tests against
    localhost because nothing it was shown said the suite runs in a plain Node
    process with no server. The supplement is the stack-conditioned seam that owns
    this fact — if a rewrite drops it, that loss mode returns silently.
    """
    supplement = DEV_CAPABILITIES[_STACK].test_prompt_supplement

    assert "NO server" in supplement
    assert "localhost" in supplement  # the prohibition names the thing authors reach for
    assert "vitest run" in supplement


def test_the_test_supplement_shows_in_process_handler_invocation():
    """The prohibition alone leaves the author with no replacement strategy; the
    supplement must also show the working pattern — import the route handler,
    invoke it with a Request, including the params form for dynamic routes.
    """
    supplement = DEV_CAPABILITIES[_STACK].test_prompt_supplement

    assert "from '@/app/api/runs/route'" in supplement
    assert "new Request(" in supplement
    assert "{ params:" in supplement


class TestStoreUpdateSeam:
    """#1055: the store gained an update verb because it had none.

    Its whole write surface was `insert`, which is `push`. "Persist a change to an
    existing row" had no correct form: the working answer was to mutate the object
    `find` returned and call no write verb, which is non-obvious, and the
    natural-looking answer stored a duplicate. Two independent authorings on two models
    both chose `insert`, and both only in the handlers that update rather than create.
    """

    @staticmethod
    def _store() -> str:
        from squadops.capabilities.scaffold import expand
        from tests.unit.capabilities._stack_fixtures import manifest_for_stack

        tree = {f["name"]: f["content"] for f in expand(manifest_for_stack("nextjs_ts"))}
        return tree["lib/store.ts"]

    def test_the_store_exports_update(self):
        """Bug caught: a write surface with no way to write a change. `insert` remains
        create-only, so the two verbs stay distinguishable — making `insert` an upsert
        would have made a genuine double-create undetectable."""
        source = self._store()
        assert "export function update(table: Table, row: Record<string, unknown>)" in source
        assert "export function insert(table: Table, row: Record<string, unknown>)" in source
        assert "rows.findIndex((r) => r.id === row.id)" in source

    def test_update_upserts_rather_than_only_replacing(self):
        """A row absent from the table must still land. A replace-only update would
        silently drop the write, which is the same class of defect one step over."""
        source = self._store()
        body = source.split("export function update")[1].split("export function find")[0]
        assert "if (index >= 0) rows[index] = row" in body
        assert "else rows.push(row)" in body

    def test_the_frozen_index_advertises_the_new_verb(self):
        """A seam the author cannot see is a seam it will not use — #861's sentence, and
        the reason the previous absence cost two rolls. The index derives from the tree,
        so this asserts the derivation reaches the brief rather than that a list was
        edited."""
        from squadops.capabilities.scaffold import frozen_surface_index_lines
        from tests.unit.capabilities._stack_fixtures import manifest_for_stack

        store_line = next(
            line
            for line in frozen_surface_index_lines(manifest_for_stack("nextjs_ts"))
            if "lib/store.ts" in line
        )
        assert "update(table: Table, row: Record<string, unknown>)" in store_line


# --------------------------------------------------------------------------- #
# #1096 — the frozen model must not contradict the response floor
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("list[Participant]", "Participant[]"),
        ("Participant", "Participant"),
        ("LIST[Participant]", "Participant[]"),
        ("list[string]", "string[]"),
        ("integer", "number"),
        ("Unknownthing", "string"),
        ("list[list[Participant]]", "Participant[][]"),
    ],
)
def test_ts_type_passes_declared_names_through_and_keeps_the_string_fallback(raw, expected):
    """#1096: `list[Participant]` rendered `string[]` because the token was lower-cased and
    then looked up as a primitive. A declared name must survive case-preserved; an
    undeclared token must still fall to `string`, never `any`."""
    from squadops.capabilities.stack_nextjs_ts import _ts_type

    assert _ts_type(raw, {"Participant"}) == expected


def test_the_frozen_model_types_a_collection_by_the_interface_it_declares():
    """Bug caught (#1096): the frozen `lib/models.ts` defined `interface Participant` and
    three lines later declared `Run.participants: string[]`. The developer's brief carried
    that line under FROZEN FILES as *authoritative*; the floor demanded objects. Both
    renderings must now say `Participant[]`."""
    models = next(f["content"] for f in expand(_manifest()) if f["name"] == "lib/models.ts")
    assert "  participants: Participant[]" in models
    assert "string[]" not in models
    index = next(
        line for line in scaffold.frozen_surface_index_lines(_manifest()) if "models.ts" in line
    )
    assert "participants: Participant[]" in index


def test_the_frozen_model_and_the_response_floor_pin_the_same_element_kind():
    """The two derivations that disagreed for the stack's whole life. For every collection
    field whose element is a declared entity, the floor asserts the element's required
    fields and the model must declare the element's interface — the same manifest fact,
    rendered twice, must not read differently."""
    from squadops.capabilities.response_shape import derive_response_shape

    manifest = _manifest()
    models = next(f["content"] for f in expand(manifest) if f["name"] == "lib/models.ts")
    entities = {e.name for e in manifest.entities}
    checked = 0
    for entity in manifest.entities:
        shape = derive_response_shape(manifest, entity.name)
        floor = {e.field: e for e in (shape.elements if shape else ())}
        for field in entity.fields:
            inner = field.type[len("list[") : -1] if field.type.startswith("list[") else ""
            if inner in entities:
                assert floor[field.name].required_fields, field.name
                assert f"  {field.name}: {inner}[]" in models, (field.name, inner)
                checked += 1
    assert checked >= 1, "the reference manifest must exercise a list-of-entity field"


# --------------------------------------------------------------------------- #
# #1087 — the store hands out tables only for what a correct app persists
# --------------------------------------------------------------------------- #


def test_the_store_exports_a_table_only_for_root_persisted_entities():
    """Bug caught (#1087): `TABLES` carried `Participant` (an embedded shape) and every
    other declared entity. Rolls 1 and 4 of the 1.6.3 set asserted on it and rejected
    working applications. Only `RunEvent` — created by POST, read by id — is stored."""
    store = next(f["content"] for f in expand(_manifest()) if f["name"] == "lib/store.ts")
    assert "  RunEvent: 'run_event'," in store
    assert "Participant" not in store


def test_the_frozen_harness_demonstrates_a_root_table_not_the_first_declared_entity():
    """`Participant` is declared first on group_run; the harness used `entities[0]` and so
    demonstrated inserting into the phantom table right above the fill slots (#1087).
    It must address a table the store actually exports, or it stops compiling."""
    harness = next(
        f["content"] for f in expand(_manifest()) if f["name"] == "__tests__/harness.test.ts"
    )
    assert "TABLES.RunEvent" in harness
    assert "TABLES.Participant" not in harness
