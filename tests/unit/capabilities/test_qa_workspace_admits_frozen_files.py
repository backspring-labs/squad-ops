"""The QA build workspace must admit every frozen file the skeleton's build needs (#1476).

Found by the 1.7.5 checkpoint pair — on all six halves across three deploys, once #1468 and
#1472 made the reason readable:

    Next.js:  Module not found: Can't resolve './globals.css'   (app/layout.tsx)
    React:    Could not resolve "./index.css"                    (frontend/src/main.jsx)

`_get_source_artifacts` assembles the QA build/test workspace from the stored artifacts,
keeping a file only if its extension is in `source_filter` or its basename is in
`build_support_files`. `.css` was in neither. The sheet was emitted, stored and delivered — the
boot audit builds the delivered tree and passes — but the frozen entry point imports a file the
verification workspace was assembled without. 1.7.4: `frontend_build` failed in 0 of 17
records. 1.7.5, after #906 and #1463: 6 of 6.

Bug classes guarded:

- **a frozen file the build needs dropped by the workspace filter.** The wiring test enters at
  `_get_source_artifacts` with the real profiles, not at a copy of its predicate;
- **the next such file.** The guard is parametrized over the registered scaffold stacks and
  asks, for every frozen file the expander actually emits, whether the QA workspace admits it.
  The exceptions are named, never inferred: the container packaging the scaffold renders
  (`BuildProfile.scaffold_provided_files`, which no build or suite reads) and each file in
  `_NOT_IN_THE_QA_WORKSPACE` with its reason. So a frozen `.json` fixture or a second
  stylesheet is covered the day it lands, and a file the workspace drops must be named here.
  (Until #1975 the rule read `expected_extensions`, a field no production code read, which
  covered only the suffixes it happened to list.)
- **the filter widening past its purpose.** The control asserts an unrelated stylesheet that
  no frozen file imports is still excluded — the fix is two basenames, not `.css` in
  `source_filter`, because `source_filter` also decides what the qa author is SHOWN as source
  under test, and a frozen sheet is not that.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.development_profiles import get_development_profile
from squadops.capabilities.handlers.build_profiles import get_profile
from squadops.capabilities.handlers.cycle.qa_test import _is_test_file
from squadops.capabilities.handlers.cycle_tasks import QATestHandler
from squadops.capabilities.scaffold import _STACKS, expand, fill_slot_paths
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]


def _admitted(profile: str, contents: dict[str, str]) -> set[str]:
    inputs = {"resolved_config": {"development_profile": profile}, "artifact_contents": contents}
    return set(QATestHandler()._get_source_artifacts(inputs))


@pytest.mark.parametrize(
    ("profile", "entry", "sheet"),
    [
        ("fullstack_fastapi_react", "frontend/src/main.jsx", "frontend/src/index.css"),
        ("nextjs_ts", "app/layout.tsx", "app/globals.css"),
    ],
)
def test_the_frozen_stylesheet_reaches_the_qa_build_workspace(profile, entry, sheet):
    """The entry point and the sheet it imports must arrive TOGETHER. Either alone is a
    different broken state: the entry without the sheet is this defect; the sheet without the
    entry is dead bytes."""
    contents = {entry: "import './x.css'", sheet: "body{}", "package.json": "{}"}

    kept = _admitted(profile, contents)

    assert entry in kept
    assert sheet in kept, f"{sheet} is dropped from the QA workspace — the build cannot resolve it"


def test_an_unrelated_stylesheet_is_still_excluded():
    """The control. If `.css` had gone into `source_filter`, every stylesheet would leak into
    the workspace AND into what the qa author is shown as source under test."""
    kept = _admitted("fullstack_fastapi_react", {"frontend/src/views/Fancy.css": "a{}"})

    assert kept == set()


#: Frozen files the QA workspace leaves out, each with its reason. The guard below fails on any
#: other dropped file, so the next exception is a decision recorded here, not a silent drop.
_NOT_IN_THE_QA_WORKSPACE: dict[str, dict[str, str]] = {
    "fullstack_fastapi_react": {
        "backend/requirements.txt": (
            "dropped by the filter (`.txt` is in neither `source_filter` nor "
            "`build_support_files`) since before #1476, and named here by #1975 rather than "
            "exempted by a suffix list. Whether the QA workspace should carry the backend's "
            "dependency manifest is not this guard's question"
        ),
    },
}


@pytest.mark.parametrize("stack", sorted(_STACKS))
def test_every_frozen_file_is_admitted_or_named(stack):
    """Parametrized over the LIVE stack registry. Every frozen file the expander emits is in
    the QA workspace, except a suite (below), the scaffold's container packaging, and a file
    named in `_NOT_IN_THE_QA_WORKSPACE`. This fails on the pre-#1476 profiles (each stack's
    stylesheet), and on the next frozen file the filter drops, without anyone adding a name."""
    manifest = manifest_for_stack(stack)
    profile = get_development_profile(stack)
    fills = set(fill_slot_paths(manifest))
    frozen = {f["name"]: f["content"] for f in expand(manifest) if f["name"] not in fills}
    # Test-pattern files are excluded from the workspace by a separate, deliberate rule
    # (`_is_test_file`): a suite is the qa author's OUTPUT, not the source under test, and the
    # frozen harness proof has been excluded this way since before any stylesheet existed —
    # 1.7.4 passed with it excluded. It is not this defect and is not this guard's subject.
    packaging = set(get_profile(stack).scaffold_provided_files())
    named = set(_NOT_IN_THE_QA_WORKSPACE.get(stack, {}))
    expected = {
        p
        for p in frozen
        if not _is_test_file(p, profile.test_file_patterns) and p not in packaging | named
    }

    kept = _admitted(stack, frozen)
    dropped = sorted(expected - kept)

    assert not dropped, f"{stack}: frozen files the QA workspace drops, unnamed: {dropped}"
    # A named exception that the workspace now admits, or the scaffold no longer emits, is
    # stale: the list must say what is true.
    assert not named & kept and named <= set(frozen), sorted(named & kept or named - set(frozen))
