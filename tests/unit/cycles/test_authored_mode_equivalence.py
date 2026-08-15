"""Guard 1b — same manifest, same downstream bytes, different provenance.

Guard 1a proves nothing *branches* on authoring mode. That is not the same as proving
the transformation is identical, and the distinction is the whole reason Guard 1 has two
halves: a fork can also be introduced by a field that only authored manifests carry
leaking into a hash, an expansion, or a derived contract. Then no code branches and the
outputs still diverge.

So this is the output half. Feed the **reference manifest** — the same instance the 1.4
Functional App Yield window was measured against — through both provenances and require
byte-identical downstream artifacts: the expanded skeleton, the derived verification
contract, and the manifest's own structural hash.

``Provenance`` already states the invariant in its docstring ("Deliberately NOT part of
the structural projection … a manifest whose only change is *how it was written* must
expand to the same skeleton and keep the contract bound to it valid"). Stating an
invariant is not holding it: the block is five fields, and adding a sixth to
``_canonical`` — or rendering provenance into an expanded file for traceability, which
is a genuinely tempting change — would move every bind-mode cycle's manifest hash and
break the contract binding, with authored mode as the only mode that shows it.

What this does NOT claim: that authored and seeded cycles produce the same *manifest*.
They obviously do not — that is the release's point. It claims that once a manifest
exists, everything downstream is blind to who wrote it.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from squadops.capabilities.scaffold import InterfaceManifest, Provenance, expand
from squadops.capabilities.scaffold_contract import emit_contract_yaml

pytestmark = [pytest.mark.domain_cycles]

_REPO = Path(__file__).resolve().parents[3]
#: The same reference instance M0a pins the deriver against (art_8becd104e9fc).
_REFERENCE = _REPO / "examples" / "03_group_run" / "interface_manifest.yaml"

#: A realistic authored-mode provenance block: mode, the cycle and task that wrote it,
#: a non-trivial attempt count. Values chosen to be the kind that WOULD show up in a
#: hash if the block ever entered the structural projection.
_AUTHORED = Provenance(
    mode="authored",
    cycle_id="cyc_b20f58cc7cbc",
    task_id="task-run_1a81279d51aa-m001-development.author_manifest",
    attempts=2,
)


def _seeded() -> InterfaceManifest:
    return InterfaceManifest.from_yaml(_REFERENCE.read_text(encoding="utf-8"))


def _authored() -> InterfaceManifest:
    return dataclasses.replace(_seeded(), provenance=_AUTHORED)


def test_the_expanded_skeleton_is_byte_identical():
    """Bug caught: provenance leaks into an emitted file.

    Rendering "authored by cycle X" into a header comment for traceability is a plausible
    and well-intentioned change. It would make every authored cycle's skeleton differ
    from the seeded one it is supposed to be identical to, and the frozen-file
    enforcement compares content — so authored mode would start failing enforcement for
    a reason that has nothing to do with the work.
    """
    seeded = {f["name"]: f["content"] for f in expand(_seeded())}
    authored = {f["name"]: f["content"] for f in expand(_authored())}

    assert authored.keys() == seeded.keys()
    differing = [name for name in seeded if authored[name] != seeded[name]]
    assert differing == [], f"provenance reached the expanded skeleton: {differing}"


def test_the_derived_contract_is_byte_identical():
    """Bug caught: the contract emitter starts reading provenance.

    The contract is what every downstream check is judged against. If authored and seeded
    manifests derive different contracts from the same design, the release's yield number
    is not comparable to the 1.4 window it is meant to extend.
    """
    assert emit_contract_yaml(_authored()) == emit_contract_yaml(_seeded())


def test_the_structural_hash_is_unmoved():
    """Bug caught: provenance enters ``_canonical``.

    This is the expensive one. The manifest hash binds the verification contract; moving
    it invalidates that binding for every bind-mode cycle, and #783 already had to pin
    ``decisions`` out of the projection for exactly this reason. Authored mode is the
    only mode carrying provenance, so the damage would appear to be authored mode's
    fault rather than the projection's.
    """
    assert _authored().content_hash() == _seeded().content_hash()


def test_the_reference_instance_still_carries_no_provenance():
    """The seeded side of the comparison must genuinely be seeded.

    If the reference file ever gained a provenance block, every assertion above would be
    comparing two authored manifests and would pass while proving nothing.
    """
    seeded = _seeded()
    assert seeded.provenance is None or not seeded.provenance.mode


@pytest.mark.parametrize(
    "mutate,label",
    [
        (lambda m: dataclasses.replace(m, stack="nextjs_ts"), "stack"),
        (lambda m: dataclasses.replace(m, persistence="postgres"), "persistence"),
    ],
)
def test_a_structural_change_does_move_the_hash(mutate, label):
    """The tripwire, without which the three assertions above are unfalsifiable.

    "Byte-identical" is trivially true of a comparison that cannot detect difference. A
    real structural edit must move the hash, or these tests would keep passing after
    ``_canonical`` was gutted.
    """
    assert mutate(_seeded()).content_hash() != _seeded().content_hash(), (
        f"changing {label} did not move the manifest hash — the structural projection is "
        f"not measuring what these equivalence tests assume it measures"
    )
