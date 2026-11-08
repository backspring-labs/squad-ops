"""#2799: on a vitest product, a page criterion for a page the change adds fails on the accepted
tree as an assertion, through the page loader the framework places beside its test.

The product is invented: a React + Vite frontend tested by vitest 2.1.9, whose derived profile's
runner reads its tests one by one (#2757's reader). The change adds a search page; P1's test loads
the page's view through ``loadView``, P2's imports it, as ``cyc_7cbdae00b2ed``'s T3 to T5 did.

Every vitest output here is real: vitest 2.1.9, run by the product's own ``npm --prefix frontend
test --silent -- <name>`` with no TTY, stdout and stderr apart, in ``node:20-slim``, over exactly
the sources below with the framework's loader as ``page_loader_source`` writes it
(``tests/fixtures/findings/vitest-2.1.9-page-*.txt``). The sandbox is the real service; its one
stand-in is the backend, which answers the one-file command with the recording made on a tree of
the same shape: which view module, and whether the loader, the overlay holds. It refuses a tree
whose loader isn't the framework's, so a replay never stands for a loader nobody recorded.

What bugs would these catch?
- a page criterion that loads its view through the loader read ``only_setup_failures`` on the
  accepted tree, or a test that imports the new view read as discriminating (§24ci (a) loosened);
- the loader never placed, or placed beside a test that renders no JSX, or where its runner would
  collect it as a test with none in it;
- a bundle frozen without the loader, so the baseline's overlay, built from the accepted tree,
  fails at the import, and a later increment's re-run of the criterion can't load its view;
- delivery leaving the loader out of the candidate, or keeping what the squad wrote at its path;
- the qa author never told of the loader, or its suite and its retest run without it.
"""

from __future__ import annotations

import dataclasses
import json
import posixpath
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml

from squadops.campaigns.acceptance import DiscriminationReason, discrimination_on_runner
from squadops.campaigns.change_request import (
    ChangeRequestError,
    ProductContext,
    ProposalContext,
    load_stored_change_request,
    stored_change_request,
    validate_proposal,
)
from squadops.campaigns.criterion_placement import runner_placements
from squadops.campaigns.page_loader import PAGE_LOADER_IMPORT, page_loader_source
from squadops.cycles.models import ArtifactRef, Cycle, TaskFlowPolicy
from squadops.execution.product_acceptance import evaluate_product_increment
from squadops.execution.source_delivery import (
    placed_framework_files,
    squad_changes,
    with_framework_files,
)
from squadops.projects.derived_profile import parse_profile
from squadops.projects.models import CheckoutTree
from squadops.sandbox.evidence import OperationEvidenceJournal
from squadops.sandbox.findings import read
from squadops.sandbox.models import (
    CommandOutcome,
    CommandResult,
    OperationName,
    OperationStatus,
    RevisionOrigin,
    WorkspaceRevision,
)
from squadops.sandbox.service import SandboxService
from squadops.sandbox.workspace import WorkspaceStore
from tests.fixtures.shared_contract.repository import recorded
from tests.unit.cycles import test_source_backed_run

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "findings"
NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
R = DiscriminationReason

TESTS = "frontend/src/__tests__"
P1 = f"{TESTS}/criterion_P1.test.jsx"
P2 = f"{TESTS}/criterion_P2.test.jsx"
LOADER = f"{TESTS}/criterion_page_loader.js"
VIEW = "frontend/src/views/TrailSearchView.jsx"

#: The accepted tree: a list page, and the harness test the product came with.
HEAD = {
    "frontend/package.json": b'{\n  "name": "trailbook-frontend",\n  "type": "module",\n'
    b'  "scripts": { "test": "vitest run" },\n  "devDependencies": { "vitest": "2.1.9" }\n}\n',
    "frontend/vite.config.js": b"import { defineConfig } from 'vite'\n"
    b"import react from '@vitejs/plugin-react'\n\nexport default defineConfig({\n"
    b"  plugins: [react()],\n  test: {\n    environment: 'jsdom',\n"
    b"    setupFiles: ['src/test-setup.js'],\n  },\n})\n",
    "frontend/src/test-setup.js": b"import '@testing-library/jest-dom/vitest'\n"
    b"import { afterEach } from 'vitest'\nimport { cleanup } from '@testing-library/react'\n\n"
    b"afterEach(cleanup)\n",
    "frontend/src/App.jsx": b"import { Routes, Route } from 'react-router-dom'\n"
    b"import TrailsListView from './views/TrailsListView.jsx'\n\nexport default function App() {\n"
    b'  return (\n    <div className="app">\n      <Routes>\n'
    b'        <Route path="/" element={<TrailsListView />} />\n      </Routes>\n    </div>\n  )\n}\n',
    "frontend/src/views/TrailsListView.jsx": b"export default function TrailsListView() {\n"
    b'  return <div data-testid="trails-list">Trails</div>\n}\n',
    f"{TESTS}/harness.test.jsx": b"import { describe, expect, it } from 'vitest'\n"
    b"import { render } from '@testing-library/react'\nimport { MemoryRouter } from 'react-router-dom'\n"
    b"import App from '../App.jsx'\n\ndescribe('harness', () => {\n"
    b"  it('renders the shell', () => {\n"
    b"    const { container } = render(<MemoryRouter><App /></MemoryRouter>)\n"
    b"    expect(container.querySelector('.app')).toBeInTheDocument()\n  })\n})\n",
}
_BODY = """describe('{cid}: the trail search page', () => {{
  it('lists a trail matching the query', async () => {{
    vi.stubGlobal('fetch', async () => new Response(JSON.stringify([{{ id: 't1', name: 'Fernhollow' }}])))
{load}    render(
      <MemoryRouter initialEntries={{['/search?q=fern']}}>
        <TrailSearchView />
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('trail-search-view')).toHaveTextContent('Fernhollow')
  }})
}})
"""
_IMPORTS = (
    "import { describe, expect, it, vi } from 'vitest'\n"
    "import { render, screen } from '@testing-library/react'\n"
    "import { MemoryRouter } from 'react-router-dom'\n"
)
#: P1, as the appendix teaches: its view loaded through the framework's loader.
THROUGH_THE_LOADER = (
    _IMPORTS
    + f"import {{ loadView }} from '{PAGE_LOADER_IMPORT}'\n\n"
    + _BODY.format(
        cid="P1",
        load="    const TrailSearchView = await loadView('../views/TrailSearchView.jsx')\n",
    )
).encode()
#: P2, the way ``cyc_7cbdae00b2ed``'s T3 to T5 were written: the new view imported.
IMPORTING_THE_VIEW = (
    _IMPORTS
    + "import TrailSearchView from '../views/TrailSearchView.jsx'\n\n"
    + _BODY.format(cid="P2", load="")
).encode()
#: The squad's view: the page the change adds, its root carrying the anchor.
SEARCH_VIEW = b"""import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

export default function TrailSearchView() {
  const [params] = useSearchParams()
  const [trails, setTrails] = useState(null)
  useEffect(() => {
    fetch(`/api/trails?q=${encodeURIComponent(params.get('q') || '')}`)
      .then((r) => r.json())
      .then(setTrails)
  }, [params])
  if (trails === null) return <p>Loading</p>
  return (
    <ul data-testid="trail-search-view">
      {trails.map((t) => (
        <li key={t.id}>{t.name}</li>
      ))}
    </ul>
  )
}
"""

PROFILE = parse_profile(
    {
        "schema": "derived-profile/v1",
        "project_id": "prj-trailbook",
        "commit": "a" * 40,
        "development_configuration_revision": 1,
        "environment": {"image": "node:20-slim"},
        "languages": [
            {"name": "javascript", "package_manager": "npm", "manifests": ["frontend/package.json"]}
        ],
        "test_runners": [
            {
                "runner": "vitest",
                "checks": ["frontend"],
                "covers": ["frontend/src/**"],
                "roots": ["frontend/src"],
                "file_pattern": "*.test.*",
                "suite_argv": ["npm", "--prefix", "frontend", "test", "--silent"],
                "single_file_argv": [
                    "npm", "--prefix", "frontend", "test", "--silent", "--", "{name}",
                ],
                "test_ids": "vitest",
                "support_files": ["frontend/vite.config.js", "frontend/src/test-setup.js"],
            }
        ],
        "lint": [],
        "toolchains": [],
        "start_declared": False,
        "public_surfaces": [{"kind": "ui_base", "url": "http://127.0.0.1:5173/"}],
        "blueprint": None,
        "client_routes": None,
        "files": {
            "test": ["frontend/src/**/*.test.jsx"],
            "test_support": ["frontend/src/test-setup.js"],
        },
        "gaps": [],
    }
)  # fmt: skip
PRODUCT = ProductContext(
    surfaces=(("ui_base", "http://127.0.0.1:5173/"),),
    placements=runner_placements(PROFILE.runners, PROFILE.gaps, HEAD),
    test_files=PROFILE.test_files,
)


def _page_criterion(cid: str) -> dict:
    return {
        "id": cid,
        "statement": "The search page lists the trails whose names match the query",
        "surface_kind": "client_route",
        "surface": "/search",
        "observable": "/search?q=fern lists Fernhollow",
        "anchor": "trail-search-view",
        "paths": [VIEW],
    }


def _authored(criteria=("P1", "P2"), kind="feature") -> dict:
    return {
        "kind": kind,
        "prd_delta": []
        if kind == "refactor"
        else [{"id": "trail-search", "op": "add", "text": "A search page lists matching trails."}],
        "footprint": [VIEW, "frontend/src/App.jsx"] if kind != "refactor" else [VIEW],
        "criteria": [_page_criterion(c) for c in criteria],
        "must_not_break": [],
    }


def proposed(authored: dict | None = None, product: ProductContext = PRODUCT) -> str:
    """The change request as the proposal's rails accept and store it."""
    verdict = validate_proposal(
        authored or _authored(),
        ProposalContext(
            proposal_id="prop_trail0001",
            version=1,
            baseline_tree="f" * 64,
            baseline_manifest="",
            expected_stack="",
            allowed_scope=("frontend/**",),
            prior_criteria=(),
            product=product,
        ),
    )
    assert verdict.accepted, verdict.refusals
    return stored_change_request(verdict.change_request)


# --- placement ------------------------------------------------------------------------------


def test_the_rails_place_a_page_loader_beside_each_page_criterions_vitest_file():
    """Bugs caught: no loader placed, so the qa author has nothing to load a view through; one
    placed in the footprint, so the build may write it; the stored request losing it, so no
    reader after the proposal can find it; one changed after the ruling loading as ruled."""
    stored = proposed()

    request = load_stored_change_request(stored)
    assert [(f.criterion_id, f.path, f.page_loader) for f in request.criterion_files] == [
        ("P1", P1, LOADER),
        ("P2", P2, LOADER),
    ]
    assert LOADER not in request.footprint
    tampered = yaml.safe_load(stored)
    tampered["criterion_files"][0]["page_loader"] = f"{TESTS}/criterion_page_loader.ts"
    with pytest.raises(ChangeRequestError, match="is not the one beside its file"):
        load_stored_change_request(yaml.safe_dump(tampered, sort_keys=False))
    tampered["criterion_files"][0]["page_loader"] = "elsewhere/criterion_page_loader.js"
    with pytest.raises(ChangeRequestError, match="is not the one beside its file"):
        load_stored_change_request(yaml.safe_dump(tampered, sort_keys=False))


def _with_runner(**changes) -> ProductContext:
    runner = dataclasses.replace(PROFILE.runners[0], **changes)
    return dataclasses.replace(PRODUCT, placements=runner_placements((runner,), (), HEAD))


@pytest.mark.parametrize(
    ("product", "criterion_kind"),
    [
        (_with_runner(runner="jest"), "client_route"),
        # Its pattern takes `criterion_page_loader.js` as a test file as well as `*.jsx`.
        (_with_runner(file_pattern="*.js*"), "client_route"),
        (PRODUCT, "package"),
    ],
    ids=["another-runner", "a-runner-that-would-collect-it", "not-a-page-criterion"],
)
def test_no_loader_is_placed_where_it_cant_serve_a_page_criterion(product, criterion_kind):
    """Bugs caught: a loader placed for jest, whose page criteria have no reader to discriminate
    anyway and no Vite to import through; one placed where the runner collects it as a test file
    with none in it, which fails every run of the suite; one on a criterion that renders no page."""
    authored = _authored(criteria=("P1",))
    if criterion_kind != "client_route":
        authored["criteria"][0] = {
            **{k: v for k, v in authored["criteria"][0].items() if k != "anchor"},
            "surface_kind": "package",
            "surface": "trailbook-frontend",
        }
        product = dataclasses.replace(
            product, surfaces=(*product.surfaces, ("package", "trailbook-frontend"))
        )

    [placed] = load_stored_change_request(proposed(authored, product)).criterion_files

    assert placed.page_loader == ""


def test_a_typescript_test_takes_a_typescript_loader_told_not_to_type_check():
    """Bug caught: a ``.tsx`` criterion given a JavaScript loader, which a product that type-checks
    its tests refuses to import without a declaration."""
    tsx = dataclasses.replace(
        PRODUCT,
        placements=runner_placements(
            PROFILE.runners,
            (),
            {
                **{p: c for p, c in HEAD.items() if not p.endswith(".test.jsx")},
                f"{TESTS}/a.test.tsx": b"",
            },
        ),
    )

    [placed] = load_stored_change_request(proposed(_authored(("P1",)), tsx)).criterion_files

    assert (placed.path, placed.page_loader) == (
        f"{TESTS}/criterion_P1.test.tsx",
        f"{TESTS}/criterion_page_loader.ts",
    )
    assert page_loader_source(placed.page_loader).startswith("// @ts-nocheck\n")
    with pytest.raises(ValueError, match="not a page loader's path"):
        page_loader_source(f"{TESTS}/criterion_P1.test.tsx")


# --- the readings, from real vitest 2.1.9 output ---------------------------------------------


def _recording(name: str) -> tuple[str, str, int]:
    out = (FIXTURES / f"vitest-2.1.9-{name}.stdout.txt").read_text()
    err = (FIXTURES / f"vitest-2.1.9-{name}.stderr.txt").read_text()
    return out, err, 0 if name.endswith("present-view") else 1


def _reading(name: str):
    return read("vitest", *_recording(name))


@pytest.mark.parametrize(
    ("baseline", "candidate", "reason"),
    [
        ("page-loader-absent-view", "page-loader-present-view", R.DISCRIMINATES),
        ("page-import-absent-view", "page-import-present-view", R.ONLY_SETUP_FAILURES),
        ("page-loader-missing", "page-loader-present-view", R.ONLY_SETUP_FAILURES),
        ("page-loader-view-throws", "page-loader-present-view", R.ONLY_SETUP_FAILURES),
    ],
    ids=["through-the-loader", "importing-the-view", "loader-missing", "a-view-that-throws"],
)
def test_what_vitest_reports_on_each_tree_reads_by_section_24ci_a(baseline, candidate, reason):
    """The loader under the real runner. Bugs caught: the loader's not-found page failing as a
    setup error (the marker not renderable, the run-time import refused at transform); a view
    that exists and throws as it loads laundered into an assertion failure by the loader, which
    would let a broken baseline read as discriminating; a tree without the loader read as
    anything but setup."""
    assert discrimination_on_runner(
        "P", "vitest", _reading(baseline), _reading(candidate)
    ).reason is (reason)


# --- the evaluation, at delivery, on the product's runner -------------------------------------


class _Vault:
    def __init__(self) -> None:
        self.stored: dict[str, tuple[ArtifactRef, bytes]] = {}

    def put(self, artifact_id: str, artifact_type: str, filename: str, content: bytes, **meta):
        self.stored[artifact_id] = (
            ArtifactRef(
                artifact_id=artifact_id, project_id="prj-trailbook", artifact_type=artifact_type,
                filename=filename, content_hash="h", size_bytes=len(content),
                media_type="text/plain", created_at=NOW, cycle_id="cyc_trail_inc", metadata=meta,
            ),
            content,
        )  # fmt: skip
        return artifact_id

    async def store(self, ref, content):
        self.stored[ref.artifact_id] = (ref, content)
        return ref

    async def retrieve(self, artifact_id):
        return self.stored[artifact_id]


class _VitestReplay:
    """The sandbox backend: the one-file command answered with the vitest recording made on a tree
    of the overlay's shape, read by the declared reader, as the container backend reads it."""

    def __init__(self, store: WorkspaceStore) -> None:
        self.store = store
        self.ran: list[dict[str, bytes]] = []

    async def run_declared_command(
        self, *, revision, command, working_dir=".", setup=(), timeout_seconds=None,
        findings_reader=None,
    ):  # fmt: skip
        with self.store.disposable_copy(revision.cycle_id, revision.revision_id) as copy:
            files = {
                str(p.relative_to(copy)): p.read_bytes() for p in copy.rglob("*") if p.is_file()
            }
        self.ran.append(files)
        name = _recorded_as(files, command[-1])
        out, err, code = _recording(name)
        return CommandResult(
            operation=OperationName.RUN_DECLARED_COMMAND,
            workspace_revision_id=revision.revision_id,
            status=OperationStatus.SUCCEEDED if code == 0 else OperationStatus.FAILED,
            ran=True,
            command=tuple(command),
            outcome=CommandOutcome.EXITED,
            exit_code=code,
            stdout_tail=out[-500:],
            stderr_tail=err[-500:],
            findings=read(findings_reader, out, err, code).as_dict() if findings_reader else None,
        )


def _recorded_as(files: dict[str, bytes], name: str) -> str:
    """Which recording a run of test file ``name`` on ``files`` is: an unresolved static import
    fails the suite (the loader's, or the view's), and ``loadView`` finds its view or doesn't."""
    [test] = [p for p in files if p.endswith(f"/{name}")]
    source, here = files[test].decode(), posixpath.dirname(test)

    def present(ref: str) -> bool:
        base = posixpath.normpath(posixpath.join(here, ref))
        return any(base + ext in files for ext in ("", ".js", ".jsx", ".ts", ".tsx"))

    missing = [r for r in re.findall(r"^import .* from '(\..+)'$", source, re.M) if not present(r)]
    if missing:
        return (
            "page-loader-missing" if missing == [PAGE_LOADER_IMPORT] else "page-import-absent-view"
        )
    loaded = re.search(r"loadView\('([^']+)'\)", source)
    if loaded is None:
        return "page-import-present-view"
    loader = posixpath.join(here, "criterion_page_loader.js")
    assert files[loader] == page_loader_source(loader).encode(), "no recording for this loader"
    return "page-loader-present-view" if present(loaded[1]) else "page-loader-absent-view"


@pytest.fixture
def sandbox(tmp_path):
    store = WorkspaceStore(tmp_path / "sandbox")
    backend = _VitestReplay(store)
    service = SandboxService(
        store=store, journal=OperationEvidenceJournal(tmp_path / "sandbox"), backend=backend
    )
    service.backend = backend
    return service


def increment(vault: _Vault, request: str, *, frozen=()) -> Cycle:
    """The product's increment as its launch makes it: its block names the campaign branch and
    pins ``frozen``, and its approved change request rides its plan refs."""
    from squadops.projects.source_context import parse_source_context

    vault.put("art_cr", "change_request", "change_request.yaml", request.encode())
    return Cycle(
        cycle_id="cyc_trail_inc",
        project_id="prj-trailbook",
        created_at=NOW,
        created_by="campaign-launcher",
        prd_ref=None,
        squad_profile_id="full",
        squad_profile_snapshot_ref="sha256:x",
        task_flow_policy=TaskFlowPolicy(mode="sequential"),
        build_strategy="fresh",
        applied_defaults={"implementation_plan": True},
        execution_overrides={
            "campaign_proposal": {
                "proposal_id": "prop_trail0001",
                "version": 1,
                "basis": "campaign_branch",
                "baseline_tree": "f" * 64,
                "objective": {
                    "statement": "s",
                    "allowed_scope": ["frontend/**"],
                    "measurement": "m",
                },
                "prior_criteria": [],
                "frozen_criteria": list(frozen),
                "max_revisions": 2,
            },
            "plan_artifact_refs": ["art_cr"],
        },
        campaign_id="cmp_trail00001",
        kind="increment",
        source_context=parse_source_context(recorded("project_source_context", "valid")),
    )


async def delivered(cycle, vault, head: dict[str, bytes], emitted: dict[str, bytes | None]):
    """The squad's emissions as delivery composes the candidate from them: the squad's change,
    then the framework's files over it."""
    for path, content in emitted.items():
        if content is None:
            continue
        producer = "qa.test" if "__tests__" in path else "development.develop"
        vault.put(f"art_{path}", "test" if producer == "qa.test" else "source", path,
                  content, producing_task_type=producer)  # fmt: skip
    stored = [(i, ref) for i, (ref, _c) in vault.stored.items() if i.startswith("art_frontend")]
    contents = {i: vault.stored[i][1] for i, _ref in stored}
    changes, _left_out = squad_changes(stored, contents, head)
    # A removal, as a task's deletion reaches delivery (H.23).
    changes = {**changes, **{p: None for p, c in emitted.items() if c is None}}
    changes = with_framework_files(changes, await placed_framework_files(cycle, vault), head)
    content = {**head, **{p: c for p, c in changes.items() if c is not None}}
    content = {p: c for p, c in content.items() if changes.get(p, c) is not None}
    revision = WorkspaceRevision.cut(cycle_id="x", origin=RevisionOrigin.AGENT_PATCH, files=content)
    return SimpleNamespace(
        head=CheckoutTree("c" * 40, dict(head), frozenset(), frozenset(), frozenset()),
        changes=changes,
        verification=SimpleNamespace(candidate_revision_id=revision.revision_id),
    )


async def judged(sandbox, cycle, vault, delivery) -> dict:
    """``evaluate_product_increment``, the delivery's evaluator, and the document it stored."""
    configuration = SimpleNamespace(
        commands=SimpleNamespace(working_directory=".", check_setup=(), readings=())
    )
    projects = AsyncMock()
    projects.get_development_configuration.return_value = configuration

    async def read_profile(_cycle):
        return PROFILE

    stored_id = await evaluate_product_increment(
        cycle, "run_impl", delivery, vault=vault, projects=projects, sandbox=sandbox,
        route_renderer=None, read_profile=read_profile,
    )  # fmt: skip
    return json.loads(vault.stored[stored_id][1])


_BUILT = {VIEW: SEARCH_VIEW, P1: THROUGH_THE_LOADER, P2: IMPORTING_THE_VIEW}


async def test_through_the_loader_a_page_the_change_adds_discriminates_and_an_import_does_not(
    sandbox,
):
    """The wiring, at the evaluator delivery calls: the change request the rails placed, the
    candidate delivery composes, each criterion's file run on the accepted tree and the candidate.
    P1 fails on the accepted tree at its anchor's assertion and passes on the candidate; P2, which
    imports the view, still reads ``only_setup_failures`` (§24ci (a) unchanged). P1's bundle
    carries the loader as the framework wrote it, and the accepted tree's overlay ran it with the
    loader and without the view."""
    vault = _Vault()
    cycle = increment(vault, proposed())

    delivery = await delivered(cycle, vault, HEAD, _BUILT)
    document = await judged(sandbox, cycle, vault, delivery)

    assert delivery.changes[LOADER] == page_loader_source(LOADER).encode()
    assert [(d["criterion_id"], d["reason"]) for d in document["discriminations"]] == [
        ("P1", "discriminates"),
        ("P2", "only_setup_failures"),
    ]
    assert "criterion P2: only_setup_failures" in document["unmet"]
    bundle = document["new_bundles"]["P1"]
    assert sorted(bundle["files"]) == sorted(
        [P1, LOADER, "frontend/vite.config.js", "frontend/src/test-setup.js"]
    )
    assert bundle["files"][LOADER] == page_loader_source(LOADER)
    assert bundle["invocation"][-1] == "criterion_P1.test.jsx"
    on_baseline = sandbox.backend.ran[0]
    assert LOADER in on_baseline and VIEW not in on_baseline
    # The product's own tests never run beside a criterion's.
    assert all(f"{TESTS}/harness.test.jsx" not in seen for seen in sandbox.backend.ran)


async def test_the_squads_own_file_at_the_loaders_path_is_replaced_by_the_frameworks(sandbox):
    """Bug caught: a squad that writes (or edits) the loader keeps its copy in the candidate, so
    the criterion is judged, and frozen, through a loader nobody placed."""
    vault = _Vault()
    cycle = increment(vault, proposed(_authored(("P1",))))
    squad_loader = b"export async function loadView() { return () => 'anything' }\n"

    delivery = await delivered(cycle, vault, HEAD, {**_BUILT, LOADER: squad_loader})

    assert delivery.changes[LOADER] == page_loader_source(LOADER).encode()


async def _first_increment(sandbox) -> tuple[dict, dict[str, bytes]]:
    vault = _Vault()
    cycle = increment(vault, proposed(_authored(("P1",))))
    delivery = await delivered(cycle, vault, HEAD, {VIEW: SEARCH_VIEW, P1: THROUGH_THE_LOADER})
    document = await judged(sandbox, cycle, vault, delivery)
    assert document["discriminations"][0]["reason"] == "discriminates"
    head = {**HEAD, **{p: c for p, c in delivery.changes.items() if c is not None}}
    return document["new_bundles"]["P1"], head


@pytest.mark.parametrize(
    ("later", "held"),
    [
        ({LOADER: None}, "held"),
        ({VIEW: None}, "broken"),
    ],
    ids=["the-loader-gone-from-the-head", "the-view-removed"],
)
async def test_a_later_increments_frozen_page_criterion_runs_through_the_loader_its_bundle_carries(
    sandbox, later, held
):
    """The criterion frozen at the first increment's promotion, re-run by a later increment on its
    candidate. Bugs caught: the bundle frozen without the loader, so the re-run reads the head's
    copy, or none, and blocks or breaks on a product that still serves the page; a later change
    that removes the view not read as a break, because the loader hid it as a setup failure."""
    bundle, head = await _first_increment(sandbox)
    vault = _Vault()
    vault.put(
        "art_bundle_p1",
        "verifier_bundle",
        "P1.json",
        json.dumps({"criterion_id": "P1", **bundle}).encode(),
    )
    pin = {
        "criterion_id": "P1",
        "test_path": P1,
        "bundle_ref": "art_bundle_p1",
        "bundle_address": bundle["address"],
        "statement": "The search page lists the trails whose names match the query",
    }
    refactor = proposed(_authored((), kind="refactor"))
    cycle = increment(vault, refactor, frozen=[pin])
    sandbox.backend.ran.clear()

    delivery = await delivered(
        cycle, vault, head, {**later, "frontend/src/views/Note.jsx": b"// note\n"}
    )
    document = await judged(sandbox, cycle, vault, delivery)

    [frozen] = document["frozen"]
    assert (frozen["criterion_id"], frozen["held"]) == ("P1", held)
    [seen] = sandbox.backend.ran
    assert seen[LOADER] == page_loader_source(LOADER).encode()


# --- delivery, at the end of the plan, on the shared fixture's real clone --------------------

#: The shared fixture's Tally, its real clone and sandbox, and an executor over them.
world = test_source_backed_run.world
_TALLY_PAGE = "checks/criterion_R1.test.jsx"
_TALLY_LOADER = "checks/criterion_page_loader.js"


def _tally_page_request() -> str:
    """Tally's report change with R1 proven on a page its change adds, placed (as a vitest runner
    would place it) beside the framework's page loader. Tally's own runner never runs it: what this
    reads is delivery, not the evaluation."""
    from squadops.campaigns.change_request import (
        PlacedCriterionFile,
        SurfaceKind,
        content_hash,
    )
    from tests.unit.campaigns.test_product_increment_seams import _REQUEST

    [r1] = _REQUEST.criteria
    on_a_page = dataclasses.replace(
        r1, surface_kind=SurfaceKind.CLIENT_ROUTE, surface="/totals", anchor="totals-view"
    )
    request = dataclasses.replace(
        _REQUEST,
        criteria=(on_a_page,),
        footprint=("tally/report.py", _TALLY_PAGE),
        criterion_files=(PlacedCriterionFile("R1", _TALLY_PAGE, _TALLY_LOADER),),
    )
    return stored_change_request(dataclasses.replace(request, content_hash=content_hash(request)))


async def test_delivery_writes_the_loader_into_the_captured_candidate_over_the_squads_copy(
    world, tmp_path
):
    """Entered at ``_execute_sequential``'s end of plan, the live delivery seam: the candidate is
    verified, captured and judged. Bugs caught: the loader left out of the candidate, so the bundle
    frozen from it can't be complete and the criterion is never run; the squad's own file at the
    loader's path delivered in its place; the loader named nowhere in what the run changed."""
    from tests.fixtures.shared_contract.repository import tracked_files
    from tests.unit.campaigns.test_product_runner_acceptance_wiring import _LINE, REPORT, _judged
    from tests.unit.cycles.test_source_backed_run import _of_type

    repo, vault = world[0], world[1]
    report = tracked_files(repo.path, repo.second_commit)[REPORT]

    await _judged(
        world,
        {REPORT: report + _LINE, _TALLY_LOADER: b"export const loadView = () => null\n"},
        frozen=False,
        request=_tally_page_request(),
    )

    [(_v, raw)] = _of_type(vault, "source_verification")
    verification = json.loads(raw)
    assert _TALLY_LOADER in verification["changed_paths"]
    [(patch_ref, _patch)] = _of_type(vault, "source_patch")
    captured = tracked_files(
        tmp_path / "cache" / "prj-tally.git", patch_ref.metadata["captured_commit"]
    )
    assert captured[_TALLY_LOADER] == page_loader_source(_TALLY_LOADER).encode()


# --- before delivery: the qa author, its suite on the product's runner, its retest, the head --


def _qa_envelope(vault: _Vault):
    """The increment's ``qa.test`` as ``generate_task_plan`` makes it, with what dispatch adds on
    a product: its view of the repository and the accepted workspace."""
    from squadops.cycles.models import Run
    from squadops.cycles.task_plan import generate_task_plan
    from tests.unit.cycles._product_increment import squad
    from tests.unit.cycles.test_increment_evaluation_wiring import _PLAN

    request = proposed()
    cycle = increment(vault, request)
    implementation = Run(
        "run_impl", cycle.cycle_id, 3, "running", "system", "cfg", workload_type="implementation"
    )
    plan = generate_task_plan(cycle, implementation, squad(), plan=_PLAN, change_request=request)
    [qa] = [e for e in plan if e.task_type == "qa.test"]
    inputs = {
        **qa.inputs,
        "artifact_contents": {p: c.decode() for p, c in HEAD.items()},
        "source_repository": {
            "commit": "c" * 40,
            "map": "",
            "runners": [
                {"runner": "vitest", "roots": ["frontend/src"], "file_pattern": "*.test.*"}
            ],
        },
    }
    return cycle, dataclasses.replace(qa, inputs=inputs)


async def test_the_qa_author_is_shown_the_loader_and_how_to_load_its_view_through_it(monkeypatch):
    """Entered at ``generate_task_plan`` and the qa handler's ``handle()`` with the real assets.
    Bugs caught: the scope never naming the loader, so no author is told of it and the tests
    import the view as before; the appendix shown without the loader it teaches, or with a
    placeholder left in."""
    from tests.unit.campaigns.test_increment_test_scope import _qa_prompt

    _cycle, qa = _qa_envelope(_Vault())
    shown = dataclasses.replace(
        qa, inputs={k: v for k, v in qa.inputs.items() if k != "source_repository"}
    )

    prompt = await _qa_prompt(shown, monkeypatch)

    assert qa.inputs["increment_test_scope"]["page_loaders"] == [
        {"criterion_id": "P1", "path": P1, "loader": LOADER},
        {"criterion_id": "P2", "path": P2, "loader": LOADER},
    ]
    assert "### How a page criterion's test loads its view" in prompt
    assert f"- P1: `{P1}` imports `loadView` from `./criterion_page_loader` (`{LOADER}`)" in prompt
    assert page_loader_source(LOADER).rstrip() in prompt
    assert "{{" not in prompt


def _suite_failed(qa):
    from squadops.tasks.models import TaskResult, TaskResultStatus

    return TaskResult(
        task_id=qa.task_id,
        status=TaskResultStatus.FAILED,
        error="suite not run in the image",
        outputs={
            "artifacts": [{"name": P1, "content": THROUGH_THE_LOADER.decode(), "type": "test"}],
            "test_result": {"executed": False, "exit_code": None, "tests_passed": False},
            "validation_result": {
                "passed": False,
                "checks": [{"check": "tests_pass", "passed": False, "executed": False}],
            },
        },
    )


async def test_the_suite_on_the_products_runner_and_its_retest_run_beside_the_loader():
    """The qa task's suite runs on the product's runner before delivery has written anything:
    entered at ``judge_on_product_runner`` (the executor's) and ``reexecute_repaired_suite`` (the
    retest a repair's patch acceptance reads). Bugs caught: the suite run on a tree without the
    loader, so a correct page criterion fails at its import in-cycle and the task is repaired for
    nothing; the retest losing the scope that names it, so a repaired suite does the same."""
    from squadops.execution.correction_runner import CorrectionRunner
    from squadops.execution.product_suite import judge_on_product_runner
    from tests.unit.cycles._product_increment import squad
    from tests.unit.cycles.test_product_suite_runner import (
        _PROJECTS,
        _executor,
        _profile_of,
        _Repository,
        _Sandbox,
    )

    cycle, qa = _qa_envelope(_Vault())
    sandbox = _Sandbox()

    judged = await judge_on_product_runner(
        _suite_failed(qa), task_type="qa.test", task_id=qa.task_id, inputs=qa.inputs, cycle=cycle,
        run_id="run_impl", sandbox=sandbox, projects=_PROJECTS, repository=_Repository(),
        read_profile=_profile_of(PROFILE),
    )  # fmt: skip

    assert judged is not None
    assert sandbox.seeded[LOADER] == page_loader_source(LOADER)
    assert sandbox.seeded[P1] == THROUGH_THE_LOADER.decode()

    executor = _executor()
    executor._derived_profile_for = _profile_of(PROFILE)
    runner = object.__new__(CorrectionRunner)
    runner._judge_suite = lambda result, envelope, cycle, run_id: (
        executor._judged_on_product_runner(result, envelope, envelope, cycle, run_id)
    )
    retests: list = []

    async def dispatch(envelope, *_a, **_k):
        retests.append(envelope)
        return _suite_failed(qa)

    runner._dispatch_protocol_step = dispatch
    await runner.reexecute_repaired_suite(
        "run_impl", cycle, qa,
        [{"name": P1, "content": THROUGH_THE_LOADER.decode(), "type": "test"}], 1,
        prior_outputs={}, all_artifact_refs=[], stored_artifacts=[], completed_task_ids=[],
        plan_delta_refs=[], profile=squad(),
    )  # fmt: skip

    [retest] = retests
    assert retest.inputs["increment_test_scope"] == qa.inputs["increment_test_scope"]
    assert executor._sandbox.seeded[LOADER] == page_loader_source(LOADER)


async def test_the_head_check_runs_a_page_criterion_beside_the_loader():
    """§24cz's check, entered at ``check_criteria_on_head``, which the executor calls once the qa
    task's files are stored. Bug caught: the head check running a page criterion's test without the
    loader, so it fails at its import on every head, and a page the head already serves is never
    read as met."""
    from squadops.execution.criterion_head_check import check_criteria_on_head
    from tests.unit.cycles.test_product_suite_runner import _PROJECTS, _Repository, _Sandbox

    vault = _Vault()
    cycle, qa = _qa_envelope(vault)
    vault.put("art_p1", "test", P1, THROUGH_THE_LOADER, producing_task_type="qa.test")
    sandbox = _Sandbox()

    async def read_profile(_cycle):
        return PROFILE

    checked = await check_criteria_on_head(
        task_type="qa.test", task_id=qa.task_id, inputs=qa.inputs, cycle=cycle, run_id="run_impl",
        stored_artifacts=[("art_p1", vault.stored["art_p1"][0])], vault=vault, sandbox=sandbox,
        projects=_PROJECTS, repository=_Repository(HEAD), read_profile=read_profile,
        write_record=False,
    )  # fmt: skip

    assert checked is not None
    assert sandbox.seeded[LOADER] == page_loader_source(LOADER)
    assert sandbox.seeded[P1] == THROUGH_THE_LOADER.decode()
    assert VIEW not in sandbox.seeded
