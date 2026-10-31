"""What a ``qa.test`` suite is materialized beside on a repository-backed product's run (#2815).

``suite_run_tree`` is the selection; the wiring through the handler and the retest is
``tests/unit/cycles/test_product_suite_run_tree.py``'s, and a sample application's tree is pinned by
``tests/unit/capabilities/handlers/test_sample_run_tree_characterization.py``.

What bugs would these catch?
- **A file the product's runtime or its test support reads left out of the run:** a manifest, a
  settings file, a fixture, a helper under ``__tests__/`` (which ``is_test_file`` excludes from a
  source set on purpose, and which a product's suites import).
- **The product's own tests run beside the suite under test:** by any stack's conventions (a
  product's stack needn't be the cycle's profile, H.13), by what a runner collects, or by a
  pattern only the product's own runner declares.
- **The marker read loosely:** a run with no repository, or one whose ``source_repository`` isn't
  a mapping, treated as a product's.
"""

from __future__ import annotations

import pytest

from squadops.capabilities.qa_prompt_contents import source_files
from squadops.capabilities.qa_run_tree import suite_run_tree
from squadops.stacks.development_profiles import get_development_profile

pytestmark = [pytest.mark.domain_capabilities]

#: An invented product's accepted workspace, as ``artifact_contents`` hands it to the qa task.
_PRODUCT = {
    "harbor/app.py": "def serve():\n    return 'ok'\n",
    "harbor/templates/dock.html": "<h1>{{ name }}</h1>\n",
    "plugins/ferry/manifest.toml": 'id = "ferry"\n',
    "config/berths.yaml": "berths: 4\n",
    "pyproject.toml": '[project]\nname = "harbor"\n',
    "tests/conftest.py": "import pytest\n",
    "tests/fixtures/berths.json": "[1, 2]\n",
    "tests/test_app.py": "def test_serve():\n    assert True\n",
    "tests/serve_test.py": "def test_more():\n    assert True\n",
    "tests/check_berths.py": "def test_berths():\n    assert True\n",
    "web/src/Dock.tsx": "export const Dock = () => null;\n",
    "web/src/Dock.test.tsx": "test('dock', () => {});\n",
    "web/src/Dock.spec.js": "test('dock', () => {});\n",
    "web/src/__tests__/render.ts": "export const render = () => null;\n",
    "README.md": "# Harbor\n",
}
_REPOSITORY = {
    "commit": "a" * 40,
    "map": "harbor/app.py",
    "runners": [
        {
            "runner": "pytest",
            "checks": ["unit"],
            "roots": ["tests"],
            "file_pattern": "check_*.py",
            "covers": ["harbor"],
        }
    ],
}
#: Never a test on any stack: the product's source, data, config and test support.
_PRODUCT_FILES = [
    "harbor/app.py",
    "harbor/templates/dock.html",
    "plugins/ferry/manifest.toml",
    "config/berths.yaml",
    "pyproject.toml",
    "tests/conftest.py",
    "tests/fixtures/berths.json",
    "web/src/Dock.tsx",
    "web/src/__tests__/render.ts",
    "README.md",
]


def _inputs(profile: str, **extra) -> dict:
    return {
        "resolved_config": {"development_profile": profile},
        "artifact_contents": dict(_PRODUCT),
        "source_repository": _REPOSITORY,
        **extra,
    }


@pytest.mark.parametrize(
    "profile", ["python_cli", "python_api", "react_app", "fullstack_fastapi_react", "nextjs_ts"]
)
def test_a_products_suite_runs_on_every_file_of_its_tree_but_its_tests(profile):
    """Every stack the product can run under (H.13 pins its blueprint's, else the default): the
    same tree, since a test is a test whichever stack the cycle names. ``web/src/Dock.test.tsx`` is
    no Python stack's test and ``tests/test_app.py`` no JavaScript stack's, and
    ``tests/check_berths.py`` is a test only by the product's own runner."""
    tree = suite_run_tree(_inputs(profile))

    assert list(tree) == _PRODUCT_FILES
    assert tree["plugins/ferry/manifest.toml"] == 'id = "ferry"\n'


def test_a_runner_with_no_declared_pattern_adds_none():
    """Edge: a runner the derived profile records without a file pattern, or a malformed entry.
    Bug caught: a ``None`` pattern read as ``"None"``, or a crash on the product's run."""
    repository = {**_REPOSITORY, "runners": [{"runner": "pytest"}, "pytest", {"file_pattern": ""}]}

    tree = suite_run_tree(_inputs("python_cli", source_repository=repository))

    assert "tests/check_berths.py" in tree
    assert "tests/test_app.py" not in tree


@pytest.mark.parametrize(
    "repository", [None, "a1b2c3", ["harbor/app.py"]], ids=["absent", "a-string", "a-list"]
)
def test_a_run_without_the_products_repository_runs_on_the_stacks_source_files(repository):
    """Edge: the marker is a mapping or nothing. Bug caught: a sample application's suite given
    the whole workspace because a key was present, or a product's because it was truthy."""
    inputs = _inputs("fullstack_fastapi_react", source_repository=repository)
    if repository is None:
        del inputs["source_repository"]

    tree = suite_run_tree(inputs)

    profile = get_development_profile("fullstack_fastapi_react")
    assert tree == source_files(_PRODUCT, profile)
    assert "plugins/ferry/manifest.toml" not in tree


def test_a_product_with_no_workspace_runs_on_nothing():
    """Edge: the executor resolved no artifact for the task."""
    assert suite_run_tree(_inputs("python_cli", artifact_contents=None)) == {}
    assert suite_run_tree(_inputs("python_cli", artifact_contents={})) == {}


def test_an_unknown_profile_is_refused():
    """Error: the handler fails fast on a profile that doesn't resolve; the selection never
    picks a default for it."""
    with pytest.raises(ValueError, match="Unknown development profile"):
        suite_run_tree(_inputs("cobol_mainframe"))
