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
  asks, for every frozen file the expander actually emits whose suffix the profile itself
  declares in `expected_extensions`, whether the QA workspace admits it. That is a rule over
  the profile's own declarations, not a list of filenames — a frozen `.json` fixture or a
  second stylesheet is covered the day it lands;
- **the filter widening past its purpose.** The control asserts an unrelated stylesheet that
  no frozen file imports is still excluded — the fix is two basenames, not `.css` in
  `source_filter`, because `source_filter` also decides what the qa author is SHOWN as source
  under test, and a frozen sheet is not that.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.development_profiles import get_development_profile
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


@pytest.mark.parametrize("stack", sorted(_STACKS))
def test_every_frozen_file_the_profile_expects_is_admitted(stack):
    """Parametrized over the LIVE stack registry. For each frozen file the expander emits
    whose suffix the profile declares in `expected_extensions`, the QA workspace must admit
    it. `.css` is declared on both stacks, so this fails on the pre-fix profiles — and it
    covers the next frozen non-source file without anyone adding a name."""
    manifest = manifest_for_stack(stack)
    profile = get_development_profile(stack)
    fills = set(fill_slot_paths(manifest))
    frozen = {f["name"]: f["content"] for f in expand(manifest) if f["name"] not in fills}
    # Test-pattern files are excluded from the workspace by a separate, deliberate rule
    # (`_is_test_file`): a suite is the qa author's OUTPUT, not the source under test, and the
    # frozen harness proof has been excluded this way since before any stylesheet existed —
    # 1.7.4 passed with it excluded. It is not this defect and is not this guard's subject.
    expected = {
        p
        for p in frozen
        if p.endswith(tuple(profile.expected_extensions))
        and not _is_test_file(p, profile.test_file_patterns)
    }

    kept = _admitted(stack, frozen)
    dropped = sorted(expected - kept)

    assert not dropped, (
        f"{stack}: frozen files the profile expects but the QA workspace drops: {dropped}"
    )
