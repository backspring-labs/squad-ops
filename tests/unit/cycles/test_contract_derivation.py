"""Deriving a verification contract from a seeded manifest (#779, M0b).

Bug classes guarded:

- a seeded manifest with no ``contract_ref`` running **unbound** — the operator asked
  for contract verification and silently gets a green carrying none of the criteria;
- a supplied ``contract_ref`` being overridden, which would break replay (compatibility
  keys on it) and quietly discard a deliberately-pinned contract;
- an unusable manifest falling through to author mode instead of rejecting;
- the derived contract diverging from what the expander emits — the equality #777 pins;
- the seeded-manifest selection rule drifting between the create path and the executor.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadops.capabilities.scaffold import InterfaceManifest
from squadops.capabilities.scaffold_contract import emit_contract_yaml
from squadops.cycles.contract_derivation import (
    CONTRACT_ARTIFACT_TYPE,
    ContractDerivationError,
    derive_and_store_contract,
    derive_contract_bytes,
    is_interface_manifest,
    load_seeded_manifest_content,
)

_REFERENCE_MANIFEST = (
    Path(__file__).resolve().parents[3] / "examples" / "03_group_run" / "interface_manifest.yaml"
)


class _Ref:
    def __init__(self, filename: str, artifact_type: str = "document"):
        self.filename = filename
        self.artifact_type = artifact_type
        self.artifact_id = "art_stub"


class _Vault:
    """Minimal vault double: retrieve by id, record what was stored."""

    def __init__(self, items: dict[str, tuple[_Ref, bytes]] | None = None):
        self._items = items or {}
        self.stored: list[tuple[object, bytes]] = []

    async def retrieve(self, artifact_id: str):
        if artifact_id not in self._items:
            raise KeyError(artifact_id)
        return self._items[artifact_id]

    async def store(self, ref, content: bytes):
        self.stored.append((ref, content))
        return ref


def _manifest_text() -> str:
    return _REFERENCE_MANIFEST.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("filename", "artifact_type", "expected"),
    [
        ("interface_manifest.yaml", "document", True),
        ("anything.yaml", "interface_manifest", True),
        ("implementation_plan.yaml", "document", False),
        ("verification_contract.yaml", "verification_contract", False),
    ],
)
def test_seeded_manifest_selection_matches_both_rails(filename, artifact_type, expected):
    """Both rails exist in the wild; a rule that knows only one silently picks nothing."""
    assert is_interface_manifest(_Ref(filename, artifact_type)) is expected


async def test_derived_contract_equals_what_the_expander_emits():
    """The invariant #777 pins, exercised through the derivation entry point."""
    derived = derive_contract_bytes(_manifest_text())

    expected = emit_contract_yaml(InterfaceManifest.from_yaml(_manifest_text()))
    assert derived.decode("utf-8") == expected


def test_unparseable_manifest_raises_rather_than_returning_nothing():
    """Falling through would run the cycle unbound while the operator believed
    otherwise — the failure mode this whole item exists to prevent."""
    with pytest.raises(ContractDerivationError) as exc:
        derive_contract_bytes("this: is: not: a: manifest\n\t- broken")

    assert "did not parse" in str(exc.value)


def test_manifest_that_parses_but_cannot_expand_still_raises():
    """A structurally-valid YAML that is not a manifest must not yield a contract."""
    with pytest.raises(ContractDerivationError):
        derive_contract_bytes("title: not a manifest\nrandom_key: 3\n")


async def test_load_seeded_manifest_finds_it_among_unrelated_refs():
    vault = _Vault(
        {
            "art_plan": (_Ref("implementation_plan.yaml"), b"plan"),
            "art_manifest": (_Ref("interface_manifest.yaml"), _manifest_text().encode()),
        }
    )

    content = await load_seeded_manifest_content(vault, ["art_plan", "art_manifest"])

    assert content == _manifest_text()


async def test_unreadable_refs_are_skipped_not_fatal():
    """A dangling ref alongside a good one must not hide the manifest."""
    vault = _Vault({"art_manifest": (_Ref("interface_manifest.yaml"), _manifest_text().encode())})

    content = await load_seeded_manifest_content(vault, ["art_missing", "art_manifest"])

    assert content == _manifest_text()


async def test_no_manifest_among_refs_returns_none():
    vault = _Vault({"art_plan": (_Ref("implementation_plan.yaml"), b"plan")})

    assert await load_seeded_manifest_content(vault, ["art_plan"]) is None
    assert await load_seeded_manifest_content(vault, None) is None


async def test_stored_contract_is_indistinguishable_from_an_ingested_one():
    """Same artifact type as the manual `artifacts ingest` path — a divergent type
    would make every downstream consumer learn about derivation.
    """
    vault = _Vault()

    artifact_id = await derive_and_store_contract(vault, "proj", _manifest_text())

    (ref, content) = vault.stored[0]
    assert ref.artifact_type == CONTRACT_ARTIFACT_TYPE
    assert ref.filename == "verification_contract.yaml"
    assert ref.artifact_id == artifact_id
    assert ref.project_id == "proj"
    # provenance is recorded on the record, not in the type
    assert ref.metadata["derived_from"] == "interface_manifest"
    assert content == derive_contract_bytes(_manifest_text())
    assert ref.size_bytes == len(content)
