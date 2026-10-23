"""The proposal's outcome evidence stays on the proposal task (SIP-0113 §4.5; §10t ruling 1).

A goal's statement is held-out material. It may reach the strategy role's proposal and nothing
else: not a framing or build role, and not the cycle's resolved config, which is stored in the
registry, served by the API, copied into retries and repairs by ``bound_launch`` and carried into
the campaign's records that a cut attaches to the public Release. The wiring test
(``tests/unit/cycles/test_proposal_evidence_wiring.py``) shows where the executor puts it. This
holds the code to it: only the executor's composer writes the key and only the proposal's handler
reads it, so no launch request builder, config writer or correction round's forwarded keys can
name it, and loading the executor or the handler loads none of the held-out store the evidence is
read from.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from squadops.tasks.task_types import TaskType

pytestmark = [pytest.mark.domain_contracts]

ROOT = Path(__file__).resolve().parents[3]
_KEY = "proposal_evidence"
_CONSTANT = "PROPOSAL_EVIDENCE_INPUT"
#: Where the key is defined, the one module that writes it onto a task's inputs, and the one
#: handler that reads it.
_DEFINED = "src/squadops/outcomes/proposal_evidence.py"
_COMPOSER = "src/squadops/execution/proposal_evidence.py"
_READER = "src/squadops/capabilities/handlers/planning/proposal.py"
_HELD_OUT = ("squadops.scenarios", "squadops.ports.scenarios", "adapters.scenarios")


def _sources():
    for top in ("src", "adapters"):
        for path in (ROOT / top).rglob("*.py"):
            yield path.relative_to(ROOT).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def _naming(tree: ast.AST) -> tuple[bool, bool]:
    """Whether ``tree`` spells the key as a string, and whether it names the constant."""
    spelled = named = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == _KEY:
            spelled = True
        elif isinstance(node, ast.Name) and node.id == _CONSTANT:
            named = True
        elif isinstance(node, ast.Attribute) and node.attr == _CONSTANT:
            named = True
        elif isinstance(node, ast.ImportFrom) and any(a.name == _CONSTANT for a in node.names):
            named = True
    return spelled, named


def test_only_the_composer_writes_the_evidence_key_and_only_the_proposal_reads_it():
    """Bugs caught: a launch request builder, a resolved-config writer or a correction round's
    forwarded keys naming the key, by its string or its constant, so the evidence reaches every
    role of the cycle, its stored config or a repair; or another handler reading it."""
    spelling, naming = set(), set()
    for rel, tree in _sources():
        spelled, named = _naming(tree)
        if spelled:
            spelling.add(rel)
        if named:
            naming.add(rel)

    assert spelling == {_DEFINED}
    assert naming == {_DEFINED, _COMPOSER, _READER}


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ('inputs["proposal_evidence"] = evidence\n', (True, False)),
        (
            "from squadops.outcomes.proposal_evidence import PROPOSAL_EVIDENCE_INPUT\n",
            (False, True),
        ),
        ("keys = (pe.PROPOSAL_EVIDENCE_INPUT,)\n", (False, True)),
        # A parameter or keyword of the same name is wiring, not the key.
        ("def f(proposal_evidence):\n    g(proposal_evidence=proposal_evidence)\n", (False, False)),
    ],
)
def test_the_guard_reads_every_way_of_naming_the_key(source, found):
    """Bug caught: a form the guard above can't see (an attribute, an import), so a new writer
    passes it, or the executor's keyword refused as though it were the key."""
    assert _naming(ast.parse(source)) == found


def test_only_the_proposal_is_shown_its_campaigns_outcomes():
    """Bug caught: the property widened to the strategy role's family or to every authoring task,
    so a framing step is shown the goals."""
    assert [t for t in TaskType if t.shown_outcome_evidence] == [
        TaskType.STRATEGY_PROPOSE_INCREMENT
    ]


def test_loading_the_executor_or_the_proposal_loads_none_of_the_held_out_store():
    """In a fresh interpreter: the runtime's executor and the strategy agent's proposal handler.
    Bug caught: the store-backed reader imported into either, or into a module one reaches, which
    the per-file import guard (``test_held_out_scenarios_stay_out_of_the_squads_reach.py``) can't
    see."""
    code = (
        "import sys\n"
        "import squadops.execution.dispatched_flow_executor\n"
        "import squadops.execution.proposal_evidence\n"
        "import squadops.capabilities.handlers.planning.proposal\n"
        f"print(sorted(m for m in sys.modules if m.startswith({_HELD_OUT!r})))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONPATH": f"{ROOT / 'src'}:{ROOT}"},
    ).stdout.strip()

    assert loaded == "[]", f"loading the executor or the proposal loads: {loaded}"


def test_no_role_is_handed_the_stored_change_request_as_an_artifact():
    """The request names the goals it means to move (SIP-0109 §24by), and the framing is shown it
    only through ``role_view``. Bug caught: a context contract's filter selecting the stored
    ``change_request.yaml``, by its type or by the proposal that produced it, so a build role's
    artifact contents carry the goals whole (the MacBook lane's review of #2686)."""
    from squadops.capabilities import context_assembly
    from squadops.capabilities.context_assembly import CONTEXT_CONTRACTS, ArtifactFilter
    from squadops.capabilities.handlers.planning.proposal import CHANGE_REQUEST_ARTIFACT_TYPE

    filters = {
        f"contract {task_type}": c.artifact_filter
        for task_type, c in CONTEXT_CONTRACTS.items()
        if c.artifact_filter is not None
    } | {
        name: value
        for name, value in vars(context_assembly).items()
        if isinstance(value, ArtifactFilter)
    }
    selecting = sorted(
        name
        for name, f in filters.items()
        if CHANGE_REQUEST_ARTIFACT_TYPE in (*f.by_type, *f.by_type_fallback)
        or TaskType.STRATEGY_PROPOSE_INCREMENT in f.by_producing_task
    )

    assert len(filters) > 5  # the contracts were read
    assert selecting == []
