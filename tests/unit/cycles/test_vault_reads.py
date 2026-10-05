"""#1990: an unreadable vault ref reads as absent with a warning naming it, never silently.

What bug would these catch? A vault fault that shows only as its consequence: the seeded
manifest "absent", a plan "missing", a criterion blocked, with nothing in the log naming the ref
that could not be read. Six reads skipped a failed retrieve with a bare ``continue``.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from squadops.cycles.contract_derivation import load_seeded_manifest_content
from squadops.cycles.vault_reads import retrieve_or_absent

_MANIFEST = SimpleNamespace(filename="interface_manifest.yaml", artifact_type="interface_manifest")
_OTHER = SimpleNamespace(filename="notes.md", artifact_type="document")


class _Vault:
    def __init__(self, stored):
        self.stored = stored

    async def retrieve(self, ref_id):
        if ref_id not in self.stored:
            raise KeyError(f"no artifact {ref_id}")
        return self.stored[ref_id]


async def test_a_readable_ref_is_returned_as_the_vault_returns_it():
    vault = _Vault({"art_1": (_OTHER, b"x")})

    assert await retrieve_or_absent(vault, "art_1") == (_OTHER, b"x")


async def test_an_unreadable_ref_is_absent_and_named(caplog):
    with caplog.at_level(logging.WARNING, logger="squadops.cycles.vault_reads"):
        got = await retrieve_or_absent(_Vault({}), "art_gone")

    assert got is None
    assert "artifact art_gone could not be read, so it reads as absent (KeyError" in caplog.text


async def test_the_seeded_manifest_lookup_reads_past_an_unreadable_ref_and_names_it(caplog):
    """Wiring, entered at ``load_seeded_manifest_content``, the create path's and the
    executor's lookup: the unreadable ref is skipped as before, and now named."""
    vault = _Vault({"art_m": (_MANIFEST, b"version: 1\n")})

    with caplog.at_level(logging.WARNING, logger="squadops.cycles.vault_reads"):
        content = await load_seeded_manifest_content(vault, ["art_gone", "art_m"])

    assert content == "version: 1\n"
    assert "art_gone" in caplog.text
    assert "art_m" not in caplog.text
