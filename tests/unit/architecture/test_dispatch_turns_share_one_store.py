"""A dispatch's turn and a change's are one, because the recall the executor composes with is built
over the store the routes read (#2545; SIP-0110 §5af).

The turn is the store's (``CrossCycleMemoryStorePort.dispatch_turn``). A dispatch holds it through
recall, since ``SnapshotRecall`` delegates to its store, and a change through ``state.memory_store``.
Two store objects would be two sets of turns, and nothing would order a dispatch against a change.

What bug would this catch? A second ``create_cross_cycle_store`` call in the runtime, or a recall
built over some other store, so a change and a dispatch each hold a turn of their own and the window
#2545 closed opens again with every test still passing. Tests build their own worlds and are out of
scope.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAIN = "src/squadops/api/runtime/main.py"
#: Where the recall's own factory builds it from what it's given.
FACTORY = "adapters/memory/recall.py"


def _calls(name: str) -> list[tuple[str, ast.Call]]:
    found = []
    for base in ("src", "adapters"):
        for path in sorted((ROOT / base).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                called = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
                if called == name:
                    found.append((path.relative_to(ROOT).as_posix(), node))
    return found


def test_the_runtime_builds_one_store_and_its_recall_over_it():
    stores = _calls("create_cross_cycle_store")
    recalls = [
        (path, call)
        for path, call in _calls("create_failure_recall") + _calls("SnapshotRecall")
        if path != FACTORY
    ]

    assert [path for path, _ in stores] == [MAIN]
    assert "state.memory_store = create_cross_cycle_store(" in (ROOT / MAIN).read_text()
    assert recalls, "the runtime builds no recall"
    for path, call in recalls:
        store = {k.arg: ast.unparse(k.value) for k in call.keywords}.get("store")
        assert (path, store) == (MAIN, "state.memory_store")
