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
  the product met: #2815's runtime discovered its plugins from manifests that weren't there.

The product's own tests are left out, so the run judges the suite under test and nothing else. A
test is a file any stack's conventions name one or any stack's runner collects
(``test_file_patterns``, ``collected_test_patterns``), or one the product's own runners take as a
test (their ``file_pattern``, SIP-0112 H.4 point 3). Every stack's, not only the cycle's: a product
runs under its blueprint's profile or the default (H.13), which needn't be the stack its tests are
written for. Support beside a test is kept: ``is_test_file``'s ``__tests__/`` clause, which
over-matches on purpose to keep helpers out of a source set, isn't used here.

Pure: no I/O. The qa handler calls it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from squadops.capabilities.handlers.source_repository import source_backed
from squadops.capabilities.qa_prompt_contents import source_files
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
    return product_tree(inputs.get("artifact_contents") or {}, product_test_patterns(inputs))


def product_test_patterns(inputs: Mapping[str, Any]) -> tuple[str, ...]:
    """What a test file is on a product's run: what any stack calls or collects as one, and each
    file pattern the product's own runners take as a test."""
    runners = (inputs.get("source_repository") or {}).get("runners") or ()
    declared = tuple(
        str(r["file_pattern"]) for r in runners if isinstance(r, Mapping) and r.get("file_pattern")
    )
    return (*_STACK_TEST_PATTERNS, *declared)


def product_tree(
    artifact_contents: Mapping[str, str], test_patterns: tuple[str, ...]
) -> dict[str, str]:
    """Every file of the product's workspace that ``test_patterns`` don't name a test, in its
    order."""
    return {
        path: content
        for path, content in artifact_contents.items()
        if not matches_test_file_patterns(path, test_patterns)
    }
