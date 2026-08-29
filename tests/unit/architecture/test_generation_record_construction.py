"""Every LLM generation record is built at one seam (#1171).

`GenerationRecord`'s docstring has named `build_generation_record()` as the required
construction path since SIP-0061, but the function did not exist: five call sites
hand-rolled the record with field sets that drifted apart. The planning handlers
omitted all four token fields, so every framing generation reached LangFuse costed at
zero tokens with no decode rate — on both engines — while the cycle handlers next door
populated them. This test is the guard that a sixth handler cannot reintroduce the drift.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.domain_telemetry]

REPO_ROOT = Path(__file__).resolve().parents[3]
#: The one module allowed to call the constructor: the seam itself.
OWNER = REPO_ROOT / "src" / "squadops" / "telemetry" / "models.py"
SEARCH_ROOTS = (REPO_ROOT / "src" / "squadops", REPO_ROOT / "adapters")


def _direct_constructions(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "GenerationRecord"
    ]


def test_generation_records_are_built_only_through_the_seam():
    offenders: list[str] = []
    for root in SEARCH_ROOTS:
        for path in root.rglob("*.py"):
            if path == OWNER:
                continue
            for line in _direct_constructions(path):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line}")
    assert not offenders, (
        "GenerationRecord constructed directly instead of via build_generation_record(): "
        + ", ".join(offenders)
        + ". The seam exists so a call site cannot silently omit token usage (#1171)."
    )
