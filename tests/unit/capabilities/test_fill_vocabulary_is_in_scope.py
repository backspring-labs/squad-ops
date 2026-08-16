"""#936 — every helper the fill appendix teaches must already be imported by the shell.

Fills are forbidden from importing ("Assertions only. NO imports"), so a helper the
appendix demonstrates and the spine does not import is a slot that **cannot run**. Not
"often fails" — fails every time, for every author, on every roll.

That was live from P1 until 2026-08-16. The appendix's two worked examples both call
``all('runs')``; all seven generated shells imported ``reset`` alone. Window roll 6
(``cyc_5544c63d1f9c``) produced a *complete* emission — seven of seven slots filled,
22,409 chars — and died on ``ReferenceError: all is not defined``. The fill protocol
worked perfectly and the roll was lost anyway.

The two artifacts are edited by different people for different reasons — one is a
prompt asset, the other a code generator — and nothing connected them. This is the
connection, asserted against the real emission rather than a copy of it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from squadops.capabilities.verification_scaffold_emission import emit_verification_scaffold
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

pytestmark = [pytest.mark.domain_capabilities]

_APPENDIX = (
    Path(__file__).resolve().parents[3]
    / "src/squadops/prompts/request_templates/request.qa_test_fill_mode_appendix.md"
)

#: Identifiers a fill body may use that are NOT store helpers — the spine's own
#: vocabulary and standard matcher surface. Anything else called inside a worked
#: example has to come from an import the shell makes.
_NOT_STORE = {"expect", "toBe", "toHaveLength", "toBeTruthy", "toEqual", "it", "describe"}


def _helpers_taught_by_the_appendix() -> set[str]:
    """Bare function calls inside the appendix's ```fill:``` examples."""
    text = _APPENDIX.read_text(encoding="utf-8")
    taught: set[str] = set()
    for block in re.findall(r"```fill:slot-[^\n]*\n(.*?)```", text, re.S):
        for name in re.findall(r"(?<![.\w])([a-z][A-Za-z0-9_]*)\(", block):
            if name not in _NOT_STORE:
                taught.add(name)
    return taught


def _names_imported_from_the_store() -> set[str]:
    """What the generated shells actually pull in from the store module."""
    emission = emit_verification_scaffold(manifest_for_stack("nextjs_ts"))
    imported: set[str] = set()
    for f in emission.files:
        for clause in re.findall(r"import \{([^}]*)\} from '@/lib/store'", f["content"]):
            imported.update(n.strip() for n in clause.split(",") if n.strip())
    return imported


def test_every_helper_the_appendix_teaches_is_imported_by_the_shell():
    """Bug caught: the appendix demonstrates a call that cannot resolve at runtime.

    The #936 defect exactly. An author copying the worked example — which is what worked
    examples are for — emits a slot that throws before asserting anything.
    """
    taught = _helpers_taught_by_the_appendix()
    imported = _names_imported_from_the_store()

    assert taught, "no helper calls found in the appendix examples — the extractor drifted"

    missing = sorted(taught - imported)
    assert missing == [], (
        f"the fill appendix teaches {missing} but the shell imports {sorted(imported)}; "
        f"a fill may not add an import, so every slot following the example fails with "
        f"ReferenceError"
    )


def test_the_store_actually_exports_what_the_shell_imports():
    """Bug caught: the shell imports a name the scaffolded store does not export.

    Fixing the assertion above by importing more is only correct if the store provides
    it — otherwise the shell itself stops compiling, which is worse: it takes the whole
    suite down instead of one slot.
    """
    from squadops.capabilities.scaffold import expand

    expanded = {f["name"]: f["content"] for f in expand(manifest_for_stack("nextjs_ts"))}
    store = next((c for n, c in expanded.items() if n.endswith("lib/store.ts")), None)
    assert store, "the nextjs_ts skeleton no longer emits lib/store.ts"

    exported = set(re.findall(r"export function (\w+)", store))
    missing = sorted(_names_imported_from_the_store() - exported)
    assert missing == [], (
        f"the shell imports {missing} from the store, which exports {sorted(exported)} — "
        f"the generated suite would not compile"
    )
