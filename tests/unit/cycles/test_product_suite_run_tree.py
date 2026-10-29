"""A repository-backed product's ``qa.test`` suite runs on the product's tree (#2815).

The 2.5 main demonstration's increments failed in-cycle twice on a criterion the product meets
(``run_9520f92ee9f2``, ``run_89b95f35891f``): the product discovers its plugins from a manifest file
at startup, and the qa task's suite ran on the stack's source files only, so no manifest was there
and the runtime registered none. The acceptance, in the sandbox on the full tree, never got a turn.

These tests enter where the live cycle does, on an invented product whose app reads
``plugins/<id>/manifest.toml`` in its startup, with a criterion test that needs it and the product's
own test support (a ``conftest.py`` and a fixture file):
- **the emission:** the product is seeded as provisioning seeds it, the qa task enriched by the
  executor's ``_enrich_envelope``, and its suite generated and run by ``QATestHandler.handle``
  through the real runner, real pytest;
- **the retest:** the correction runner composes the retest of a repaired suite
  (``reexecute_repaired_suite``) from that task's enriched envelope, and the qa handler runs it as
  the qa agent does, real pytest again.

Both fail before #2815 (the manifest and the fixture never reach the run) and pass after. The
product's own test, which needs a harness the qa image doesn't carry, is never run beside the suite.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from adapters.prompts.filesystem_asset_adapter import FilesystemPromptAssetAdapter
from squadops.capabilities.handlers.cycle.qa_test import QATestHandler
from squadops.cycles.implementation_plan import ImplementationPlan
from squadops.cycles.task_plan import generate_task_plan
from squadops.execution.source_checkout import seed_checkout_artifacts
from squadops.llm.models import ChatMessage
from squadops.prompts.renderer import RequestTemplateRenderer
from squadops.tasks.models import TaskResult
from tests.unit.campaigns.test_product_increment_seams import STORED
from tests.unit.cycles._product_increment import (
    CONTEXT,
    Vault,
    executor,
    increment_cycle,
    pinned_recall,
    projects,
    repository,
    run,
    squad,
)

pytestmark = [pytest.mark.domain_capabilities]

_PROMPTS = Path(__file__).resolve().parents[3] / "src" / "squadops" / "prompts"

#: The invented product: an app that registers each plugin its ``plugins/<id>/manifest.toml``
#: declares when it starts, and serves them; its test support; and one test of its own that needs
#: a harness only the product's own runner has.
_PRODUCT = {
    "pyproject.toml": '[project]\nname = "beacon"\nversion = "0.3.0"\n',
    "beacon/__init__.py": "",
    "beacon/discovery.py": (
        "import tomllib\n"
        "from pathlib import Path\n\n"
        "PLUGINS = Path(__file__).resolve().parent.parent / 'plugins'\n\n\n"
        "def discover(root: Path = PLUGINS) -> dict[str, dict]:\n"
        "    found = {}\n"
        "    for manifest in sorted(root.glob('*/manifest.toml')):\n"
        "        declared = tomllib.loads(manifest.read_text())\n"
        "        found[declared['id']] = declared\n"
        "    return found\n"
    ),
    "beacon/app.py": (
        "from contextlib import asynccontextmanager\n\n"
        "from fastapi import FastAPI, HTTPException\n\n"
        "from beacon.discovery import discover\n\n\n"
        "@asynccontextmanager\n"
        "async def lifespan(app):\n"
        "    app.state.plugins = discover()\n"
        "    yield\n\n\n"
        "app = FastAPI(lifespan=lifespan)\n\n\n"
        "@app.get('/plugins')\n"
        "def plugins():\n"
        "    return sorted(app.state.plugins)\n\n\n"
        "@app.get('/plugins/{plugin_id}')\n"
        "def plugin(plugin_id: str):\n"
        "    if plugin_id not in app.state.plugins:\n"
        "        raise HTTPException(404, f'no plugin {plugin_id}')\n"
        "    return app.state.plugins[plugin_id]\n"
    ),
    "plugins/tides/manifest.toml": 'id = "tides"\ntitle = "Tide table"\n',
    "beacon/static/badge.js": "export const badge = (id) => `<b>${id}</b>`;\n",
    "tests/conftest.py": (
        "import json\n"
        "from pathlib import Path\n\n"
        "import pytest\n"
        "from fastapi.testclient import TestClient\n\n"
        "from beacon.app import app\n\n\n"
        "@pytest.fixture\n"
        "def client():\n"
        "    with TestClient(app) as running:\n"
        "        yield running\n\n\n"
        "@pytest.fixture\n"
        "def shipped_plugins():\n"
        "    return json.loads((Path(__file__).parent / 'fixtures' / 'shipped.json').read_text())\n"
    ),
    "tests/fixtures/shipped.json": '["tides"]\n',
    "tests/test_discovery.py": (
        "from beacon_harness import fresh_root\n\n\n"
        "def test_discovery_reads_every_manifest():\n"
        "    assert fresh_root()\n"
    ),
}
#: What the increment's develop task wrote: the plugin the change adds.
_ADDED = {"plugins/clock/manifest.toml": 'id = "clock"\ntitle = "Clock"\n'}
#: The criterion's suite, as the qa author emits it.
_SUITE_PATH = "tests/test_criterion_clock.py"
_SUITE = (
    "def test_the_clock_plugin_is_served_once_the_app_starts(client):\n"
    "    response = client.get('/plugins/clock')\n"
    "    assert response.status_code == 200\n"
    "    assert response.json()['title'] == 'Clock'\n\n\n"
    "def test_every_plugin_the_product_shipped_is_still_served(client, shipped_plugins):\n"
    "    assert set(shipped_plugins) <= set(client.get('/plugins').json())\n"
)


def _plan() -> ImplementationPlan:
    return ImplementationPlan.from_yaml(
        yaml.safe_dump(
            {
                "version": 1, "project_id": CONTEXT.project_id, "cycle_id": "cyc_tally_inc",
                "prd_hash": "abc",
                "summary": {"total_dev_tasks": 1, "total_qa_tasks": 1, "total_tasks": 2},
                "tasks": [
                    {"task_index": 0, "task_type": "development.develop", "role": "dev",
                     "focus": "the clock plugin", "description": "Add the clock plugin.",
                     "expected_artifacts": list(_ADDED), "acceptance_criteria": []},
                    {"task_index": 1, "task_type": "qa.test", "role": "qa",
                     "focus": "the clock criterion", "description": "Check the clock is served.",
                     "expected_artifacts": [_SUITE_PATH], "acceptance_criteria": [],
                     "depends_on": [0]},
                ],
            }
        )
    )  # fmt: skip


def _context() -> MagicMock:
    """The qa agent's ports: its model emits the criterion's suite, its renderer the real one."""

    async def _chat(messages, **kwargs):
        return ChatMessage(
            role="assistant", content=f"```python:{_SUITE_PATH}\n{_SUITE}```\n",
            completion_tokens=60,
        )  # fmt: skip

    ctx = MagicMock()
    ctx.task_id = "task-run_impl0000001-m001-qa.test"
    ctx.ports.llm.chat_stream_with_usage = AsyncMock(side_effect=_chat)
    ctx.ports.llm.default_model = "test-model"
    ctx.ports.prompt_service.get_system_prompt.return_value = MagicMock(
        content="system", assembly_hash="h"
    )
    ctx.ports.llm_observability = None
    ctx.ports.request_renderer = RequestTemplateRenderer(
        FilesystemPromptAssetAdapter(_PROMPTS / "fragments", _PROMPTS / "request_templates")
    )
    ctx.correlation_context = None
    ctx.disputed_checks = []
    return ctx


class _QAAgent:
    """The task dispatcher, as the qa agent answers a retest: its handler runs the envelope."""

    def __init__(self) -> None:
        self.sent: list[Any] = []
        self.results: list[Any] = []

    async def dispatch_task(self, envelope, run_id, **_kwargs) -> TaskResult:
        self.sent.append(envelope)
        result = await QATestHandler().handle(_context(), dict(envelope.inputs))
        self.results.append(result)
        return TaskResult(
            task_id=envelope.task_id,
            status="SUCCEEDED" if result.success else "FAILED",
            outputs=result.outputs,
            error=result.error,
        )

    async def create_task_run_if_enabled(self, _flow_run_id, _envelope):
        return None


async def _composed(development_profile: str | None):
    """The product's increment seeded, and its qa task enriched by the executor, as the live
    implementation run composes it."""
    cycle = increment_cycle()
    if development_profile:
        # SIP-0112 H.13: a product made from a blueprint runs under its development profile.
        cycle = dataclasses.replace(
            cycle,
            execution_overrides={
                **cycle.execution_overrides,
                "development_profile": development_profile,
            },
        )
    implementation = run("implementation")
    recall, _store = await pinned_recall(cycle)
    vault, agent = Vault(), _QAAgent()
    built, _registry = executor(vault, recall, agent)
    tree = {path: content.encode() for path, content in _PRODUCT.items()}
    await seed_checkout_artifacts(
        cycle, implementation.run_id, vault=vault, repository=repository(tree),
        registry=projects(),
    )  # fmt: skip
    for path, content in _ADDED.items():
        vault.produced(path, content, "development.develop", "config")
    [envelope] = [
        e
        for e in generate_task_plan(
            cycle, implementation, squad(), plan=_plan(), change_request=STORED
        )
        if e.task_type == "qa.test"
    ]
    enriched = await built._enrich_envelope(envelope, {}, [], vault.refs())
    return cycle, implementation, built, vault, agent, enriched


_PROFILES = pytest.mark.parametrize(
    "development_profile",
    [None, "fullstack_fastapi_react"],
    ids=["default-profile", "blueprint-profile"],
)


@_PROFILES
async def test_a_products_criterion_that_needs_its_manifest_passes_in_cycle(development_profile):
    """Entered at the qa handler's ``handle()`` on the envelope the executor composed, the suite
    run by real pytest. Bug caught: the suite run on the stack's source files alone, where the
    manifest the app reads at startup and the fixture its conftest reads are absent, so a correct
    build fails its criterion (#2815: "Expected exactly one entry …, got 0")."""
    *_rest, enriched = await _composed(development_profile)
    assert isinstance(enriched.inputs.get("source_repository"), dict)
    assert "plugins/clock/manifest.toml" in enriched.inputs["artifact_contents"]

    result = await QATestHandler().handle(_context(), dict(enriched.inputs))

    report = next(a for a in result.outputs["artifacts"] if a["name"] == "test_report.md")
    assert result.outputs["test_result"]["tests_passed"] is True, report["content"]
    assert result.success, result.error
    assert "2 passed" in report["content"]
    # The product's own test, which needs a harness the qa image lacks, was not run beside it.
    assert "beacon_harness" not in report["content"]
    # The lint reading reads the tree the run evaluated: the product's script, which no Python
    # stack calls source, is linted beside its Python (#1937).
    assert result.outputs["lint_findings"]["files_linted"] == {"python": 4, "js": 1}


@_PROFILES
async def test_a_products_repaired_suite_is_retested_on_the_products_tree(development_profile):
    """Entered at the correction runner's ``reexecute_repaired_suite``, which composes the retest
    from the failed qa task's enriched envelope; the qa agent's handler runs it, real pytest. Bug
    caught: the retest forwarded without the marker that makes the run a product's, so a suite that
    passed at its emission fails its retest on the source files alone, and a correct repair is
    refused."""
    cycle, implementation, built, vault, agent, enriched = await _composed(development_profile)
    repaired = [{"name": _SUITE_PATH, "content": _SUITE, "type": "test"}]

    retest = await built._correction_runner.reexecute_repaired_suite(
        implementation.run_id, cycle, enriched, repaired, 1,
        prior_outputs={}, all_artifact_refs=[], stored_artifacts=vault.refs(),
        completed_task_ids=[], plan_delta_refs=[], profile=squad(),
    )  # fmt: skip

    [sent] = agent.sent
    assert sent.metadata.get("retest") is True
    assert sent.inputs["source_repository"] == enriched.inputs["source_repository"]
    [handled] = agent.results
    report = next(a for a in handled.outputs["artifacts"] if a["name"] == "test_report.md")
    assert handled.outputs["test_result"]["tests_passed"] is True, report["content"]
    assert retest.status == "SUCCEEDED"
