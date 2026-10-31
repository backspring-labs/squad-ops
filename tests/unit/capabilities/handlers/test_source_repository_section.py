"""The product's repository in an authoring prompt (SIP-0112 E.4.3), with the real renderer and
the shipped assets: a renamed placeholder or an undeclared variable fails here, rather than
rendering an empty section in production."""

from __future__ import annotations

from typing import Any

from adapters.prompts.factory import DEFAULT_TEMPLATES_PATH, create_prompt_asset_source
from squadops.capabilities.handlers.cycle.develop import DevelopmentDevelopHandler
from squadops.capabilities.handlers.source_repository import source_repository_section
from squadops.prompts.renderer import RequestTemplateRenderer

COMMIT = "962858eb0e321ed084463637c9faf661c179a41e"
REPOSITORY = {
    "commit": COMMIT,
    "map": "- `tally/__main__.py` (700 bytes)\n- `CONTRIBUTING.md` (500 bytes)",
    "checks": [{"id": "parse", "argv": ["python3", "-m", "unittest", "discover", "-s", "checks"]}],
    "instructions": {"CONTRIBUTING.md": "Build first: `python3 tools/build.py`."},
    "existing_files": {"tally/__main__.py": "import argparse\n"},
}


def _renderer():
    return RequestTemplateRenderer(
        asset_source=create_prompt_asset_source(
            provider="filesystem", templates_path=DEFAULT_TEMPLATES_PATH
        )
    )


def _handler() -> DevelopmentDevelopHandler:
    handler = DevelopmentDevelopHandler()
    handler._resolved_config = {}  # as handle() sets it before the prompt is built
    return handler


def _inputs(**extra: Any) -> dict[str, Any]:
    return {
        "prd": "Add a --json flag to the counters listing.",
        "subtask_focus": "--json output",
        "subtask_description": "Print the counters as JSON when --json is given.",
        "expected_artifacts": ["tally/__main__.py"],
        "acceptance_criteria": [],
        "artifact_contents": {},
        "resolved_config": {},
        **extra,
    }


async def test_the_developer_is_shown_the_product_its_instructions_and_the_file_it_changes():
    prompt = await _handler()._build_focused_prompt(
        _inputs(source_repository=REPOSITORY), _renderer()
    )

    assert "THE PRODUCT YOU ARE CHANGING" in prompt and COMMIT in prompt
    assert "- `tally/__main__.py` (700 bytes)" in prompt
    assert "Build first: `python3 tools/build.py`." in prompt
    assert "**tally/__main__.py:**\n```\nimport argparse\n" in prompt
    # the live run's framing authored a command criterion twice for want of this (#2410)
    assert "- `parse`: `python3 -m unittest discover -s checks`" in prompt
    assert "{{" not in prompt


async def test_the_qa_author_is_shown_where_the_products_runners_find_a_test():
    """SIP-0112 H.4 point 3. Bug caught: a test written where no runner of the product looks, or
    named as none takes it, which the product's checks never run, so it verifies nothing."""
    runner = {
        "runner": "unittest",
        "checks": ["parse", "ledger"],
        "roots": ["checks"],
        "file_pattern": "check_*.py",
        "covers": ["tally/**"],
    }

    section = await source_repository_section(
        _renderer(), {"source_repository": {**REPOSITORY, "runners": [runner]}}
    )

    assert (
        "- `unittest`, run by `parse`, `ledger`: a file named `check_*.py` under `checks`, "
        "testing `tally/**`"
    ) in section
    assert "is never run, and verifies\nnothing" in section and "{{" not in section


async def test_a_run_without_a_product_renders_no_section():
    """Bug caught: every scaffolded run's prompt carrying an empty product heading."""
    prompt = await _handler()._build_focused_prompt(_inputs(), _renderer())

    assert "THE PRODUCT YOU ARE CHANGING" not in prompt
    assert await source_repository_section(_renderer(), {}) == ""
    assert await source_repository_section(None, {"source_repository": REPOSITORY}) == ""


async def test_only_the_parts_a_task_has_are_rendered():
    section = await source_repository_section(
        _renderer(), {"source_repository": {**REPOSITORY, "instructions": {}, "existing_files": {}}}
    )

    assert "instructions for contributors" not in section
    assert "current content of the files" not in section
    # a run seeded with no derived profile is shown the checks alone, as in 2.4
    assert "its own runners" not in section and "{{" not in section
    assert "- `CONTRIBUTING.md` (500 bytes)" in section
