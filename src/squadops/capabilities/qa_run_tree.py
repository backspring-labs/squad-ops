"""The tree a ``qa.test`` suite is built and run against (#2815).

Split from what the task's prompt shows (``qa_prompt_contents``, #2805, #2810): the composer counts
the prompt's files in the task's budget, so they and the estimate stay as they are. This module says
only what the suite runner materializes beside the suite, on every path of the handler that runs
one (the emission, the execute-only retest, the contract probes and the lint reading).

- **A sample application's suite** runs on the stack's source and build-support files
  (``qa_prompt_contents.source_files``), as it always has. Its tree is all source and support files.
- **A repository-backed product's suite** (a source-backed run's task, which carries the product's
  repository, SIP-0112 E.4.3) runs on the product's tree as the task sees it: every file of its
  accepted workspace (``artifact_contents``) that isn't a test. That is its source, the data and
  config its runtime reads (a plugin manifest, a template, a settings file), and its own test
  support (a ``conftest.py``, a fixture file, a helper under ``__tests__/``). A product reads files
  the stack's filter doesn't call source, so its suite on the source files alone failed a criterion
  the product met: #2815's runtime discovered its plugins from manifests that weren't there. An
  increment's page loaders (#2799), which its test scope names, are laid in too: the framework's
  files, which a page criterion's test imports and delivery writes only into the candidate.

The product's own tests are left out, so the run judges the suite under test and nothing else. A
test is either of two things:
- a file any stack's conventions call a test, or that any stack's runner collects
  (``test_file_patterns``, ``collected_test_patterns``). Every stack's counts, not only the cycle's,
  because a product runs under its blueprint's profile or the default (H.13), and that needn't be
  the stack its tests are written for;
- a file one of the product's own runners holds as a test: its ``file_pattern``, matched **only
  under that runner's roots** (``Runner.holds``, SIP-0112 H.4 point 3; #2817). Matched anywhere,
  unittest's ``test*.py`` rooted at ``tests`` would drop a source module ``orchard/testing.py``,
  and a runner's ``*.py`` would drop the whole Python tree.

Support beside a test is kept. ``is_test_file``'s ``__tests__/`` clause, which over-matches on
purpose to keep helpers out of a source set, isn't used here.

**Known limits** (#2817 item 3, not built):
- The stack patterns are path-blind. A product helper named like a test (``tests/test_utils.py``)
  or a source named like one (``ab_test.py``) is left out, as the qa image's ``pytest .`` would
  collect it.
- A product with no derived profile has only the stacks' JavaScript extensions, so a ``.test.mjs``
  stays in its run tree.
- Past the executor's 512 KB ``artifact_contents`` limit, the run can lack a file the product holds.

Pure: no I/O. The qa handler calls it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.capabilities.handlers.source_repository import source_backed
from squadops.capabilities.qa_prompt_contents import source_files
from squadops.projects.derived_profile import runner_holds
from squadops.stacks.development_profiles import (
    DEVELOPMENT_PROFILES,
    effective_development_profile,
    get_development_profile,
    matches_test_file_patterns,
)

#: What any stack calls a test, or collects as one.
_STACK_TEST_PATTERNS: tuple[str, ...] = tuple(
    dict.fromkeys(
        pattern
        for profile in DEVELOPMENT_PROFILES.values()
        for pattern in (*profile.test_file_patterns, *profile.collected_test_patterns)
    )
)


def suite_run_tree(inputs: Mapping[str, Any]) -> dict[str, str]:
    """The files the task's suite is materialized beside, by path: the product's tree on a
    repository-backed product's run, the stack's source files on a sample application's.
    Raises ``ValueError`` for a development profile that doesn't resolve, as the handler does."""
    profile = get_development_profile(effective_development_profile(inputs.get("resolved_config")))
    if not source_backed(inputs):
        return source_files(inputs.get("artifact_contents", {}), profile)
    # deferred (cycle): campaigns.increment_tree loads the capabilities package
    from squadops.campaigns.increment_tree import scope_page_loader_files

    return {
        **product_tree(inputs.get("artifact_contents") or {}, product_runners(inputs)),
        **scope_page_loader_files(inputs.get("increment_test_scope")),
    }


def product_runners(inputs: Mapping[str, Any]) -> tuple[tuple[tuple[str, ...], str], ...]:
    """Each of the product's own runners as ``(roots, file_pattern)``, from the task's
    ``source_repository`` (``checkout.RunnerView``; contract 8 requires its roots)."""
    runners = (inputs.get("source_repository") or {}).get("runners") or ()
    return tuple(
        (tuple(str(r) for r in runner.get("roots") or ()), str(runner["file_pattern"]))
        for runner in runners
        if isinstance(runner, Mapping) and runner.get("file_pattern")
    )


def product_tree[C: (str, bytes)](
    artifact_contents: Mapping[str, C],
    runners: tuple[tuple[tuple[str, ...], str], ...] = (),
) -> dict[str, C]:
    """Every file of the product's workspace that is no test, in its order: no stack calls it
    one, and none of ``runners`` (``(roots, file_pattern)``) holds it. Text from a run's artifacts,
    or bytes from the product's clone (the product runner's base tree, #2900)."""
    return {
        path: content
        for path, content in artifact_contents.items()
        if not matches_test_file_patterns(path, _STACK_TEST_PATTERNS)
        and not any(runner_holds(roots, pattern, path) for roots, pattern in runners)
    }
