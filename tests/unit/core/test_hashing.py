"""#1990: four modules share one text digest, and every digest they stored is the one they
compute now.

What bug would these catch? A shared helper that encodes differently from the four copies it
replaced (the platform default, or Latin-1). Every stored contract, bound record and edit would
stop matching the text it was taken from, and an identity mismatch reads as "the tree changed",
never as a bug. The pins below were taken from main before the copies were removed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from squadops.core.hashing import text_sha256
from squadops.cycles.bound_scaffold_record import build_bound_record
from squadops.stacks.scaffold import InterfaceManifest, expand
from squadops.stacks.verification_scaffold_emission import emit_verification_scaffold
from tests.unit.capabilities._stack_fixtures import manifest_for_stack

_REPO = Path(__file__).resolve().parents[3]
_MANIFEST = _REPO / "examples" / "03_group_run" / "interface_manifest.yaml"
_CONTRACT = (
    _REPO
    / "tests"
    / "fixtures"
    / "reference_contract"
    / "contract_v16_conftest_isolation_1598.yaml"
)


def test_the_stored_contracts_frozen_digests_are_reproduced():
    """The committed v16 contract names a digest for each of its 20 frozen files, some of them
    holding non-ASCII text, so the stored record pins the encoding as well as the hash."""
    manifest = InterfaceManifest.from_yaml(_MANIFEST.read_text(encoding="utf-8"))
    files = {f["name"]: f["content"] for f in expand(manifest)}
    frozen = yaml.safe_load(_CONTRACT.read_text(encoding="utf-8"))["frozen"]

    assert len(frozen) == 20
    assert any(not files[e["path"]].isascii() for e in frozen)
    assert {e["path"]: text_sha256(files[e["path"]]) for e in frozen} == {
        e["path"]: e["sha256"] for e in frozen
    }


def test_the_bound_record_and_the_verification_scaffold_keep_their_identities():
    """The bound record's contract hash and the Next.js scaffold's three identities, as main
    computed them with the module-local copies."""
    reference = InterfaceManifest.from_yaml(_MANIFEST.read_text(encoding="utf-8"))
    record = build_bound_record(
        reference, run_id="run_x", attempt_id="a1", created_at="2026-10-05T00:00:00Z"
    )
    scaffold = emit_verification_scaffold(manifest_for_stack("nextjs_ts")).manifest

    assert record.contract_hash == (
        "486ab73fb8cbc22c83841c2d577426a90c29f99bbe328c0236f245cf2ef262bd"
    )
    assert (
        scaffold.aggregate_spine_hash(),
        scaffold.scaffold_hash(),
        scaffold.expanded_tree_hash,
    ) == (
        "1ff59445d016f6d7385d713c5f31de7620fe3f065344db6a083bae7b1a0ab962",
        "6fc46f50369bc9afd34e40607350b2464b74f79a6a8ef62772470037f5e98854",
        # #2363 (2026-10-15): the Next.js store gained `remove`, so the expanded tree moved. The
        # spine and scaffold hashes above did not, which is the evidence the change was the
        # store's alone. #2394 (2026-10-16): the seeded vitest config gained `esbuild.jsx`, and the
        # tree moved again with the spine and scaffold hashes unmoved. #2522 (2026-10-19): each
        # route handler states its request fields and errors, so the tree moved a third time, the
        # spine and scaffold hashes again unmoved. #2531 (2026-10-19): the vitest config collects
        # `.test.tsx` too, a fourth tree-only move. #2534 (2026-10-19): the page-suite DOM harness,
        # a fifth. 2026-10-20: each route handler states its response entity's fields, a sixth.
        # #2577 (2026-10-21): the frozen route caller, `vitest.routes.ts`, a seventh.
        "fc2cc133429af09709d3d0e22ac0e4f1ed126aad18ddce152c3727d1247ded9b",
    )


def test_text_is_hashed_as_utf8_not_as_a_single_byte_encoding():
    assert text_sha256("é") == "4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c"
    assert text_sha256("é") != "de2e331d891ae267a7009cb45b4e8830f170e0c937288ea2731a1941c7a53b0d"
    assert text_sha256("") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
