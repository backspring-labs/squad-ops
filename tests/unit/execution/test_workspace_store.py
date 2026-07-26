"""WorkspaceStore semantics (SIP-0102 §4.6/§7 — phase 102.1 slice b)."""

import pytest

from squadops.execution.models import RevisionOrigin
from squadops.execution.workspace import (
    AlreadySeededError,
    StaleBaseRevisionError,
    WorkspaceEscapeError,
    WorkspaceStore,
)

FILES = {"backend/main.py": "print('a')\n", "frontend/index.html": "<html></html>\n"}


@pytest.fixture
def store(tmp_path):
    return WorkspaceStore(tmp_path / "cycles")


class TestSeed:
    def test_seed_writes_tree_and_persists_head_revision(self, store):
        """Bug caught: revision recorded but content never written (or vice
        versa) — the pin would reference content that does not exist."""
        rev = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        assert store.current_files("cyc_1") == FILES
        assert store.latest_revision("cyc_1") == rev
        assert store.verify_pinned("cyc_1", rev.revision_id)

    def test_reseeding_identical_content_is_idempotent(self, store):
        """Bug caught: a crash-retry of seeding erroring out (or minting a
        second revision) instead of returning the existing one."""
        first = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        second = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        assert second.revision_id == first.revision_id

    def test_reseeding_different_content_is_rejected(self, store):
        """Bug caught: silent overwrite of a seeded workspace — evidence
        lineage would begin at content nobody recorded."""
        store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        with pytest.raises(AlreadySeededError):
            store.seed("cyc_1", {"other.py": "x"}, origin=RevisionOrigin.SCAFFOLD_SEED)


class TestPatch:
    def test_patch_applies_modify_add_delete_and_chains_lineage(self, store):
        """Bug caught: any of the three §4.6 mutation kinds not reflected on
        disk or in the new revision's hash."""
        seed = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        rev, changed = store.apply_patch(
            "cyc_1",
            base_revision_id=seed.revision_id,
            files={
                "backend/main.py": "print('b')\n",  # modify
                "backend/new.py": "x = 1\n",  # add
                "frontend/index.html": None,  # delete
            },
            origin=RevisionOrigin.AGENT_PATCH,
        )
        assert changed == ("backend/main.py", "backend/new.py", "frontend/index.html")
        assert rev.parent_revision_id == seed.revision_id
        expected = {"backend/main.py": "print('b')\n", "backend/new.py": "x = 1\n"}
        assert store.current_files("cyc_1") == expected
        assert store.verify_pinned("cyc_1", rev.revision_id)

    def test_stale_base_is_rejected(self, store):
        """Bug caught: patching over a drifted tree — the minted revision's
        content would not be derivable from base + patch, silently breaking
        replay and evidence."""
        seed = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        (store.workspace_dir("cyc_1") / "backend/main.py").write_text("drifted", encoding="utf-8")
        with pytest.raises(StaleBaseRevisionError):
            store.apply_patch(
                "cyc_1",
                base_revision_id=seed.revision_id,
                files={"backend/main.py": "print('c')\n"},
                origin=RevisionOrigin.AGENT_PATCH,
            )

    @pytest.mark.parametrize(
        "path", ["/etc/passwd", "../outside.py", "a/../../outside.py", "~/x.py"]
    )
    def test_workspace_escape_is_rejected(self, store, path):
        """Bug caught: §7 item 8 violation — a patch path reaching outside the
        cycle workspace onto the host."""
        seed = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        with pytest.raises(WorkspaceEscapeError):
            store.apply_patch(
                "cyc_1",
                base_revision_id=seed.revision_id,
                files={path: "owned"},
                origin=RevisionOrigin.AGENT_PATCH,
            )


class TestPinningAndRecovery:
    def test_verify_pinned_detects_out_of_band_mutation(self, store):
        """Bug caught: clean-room verification passing against a tree that no
        longer matches the pinned revision (the false-verdict class)."""
        rev = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        assert store.verify_pinned("cyc_1", rev.revision_id)
        (store.workspace_dir("cyc_1") / "backend/main.py").write_text("tampered", encoding="utf-8")
        assert not store.verify_pinned("cyc_1", rev.revision_id)

    def test_fresh_store_instance_recovers_state_from_disk(self, store, tmp_path):
        """Bug caught: memory-only bookkeeping — a service restart would
        forget every revision (§7 item 12 requires recoverability)."""
        rev = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        reopened = WorkspaceStore(tmp_path / "cycles")
        assert reopened.latest_revision("cyc_1") == rev
        assert reopened.verify_pinned("cyc_1", rev.revision_id)


class TestLeasesAndCleanup:
    def test_cleanup_is_idempotent(self, store):
        """Bug caught: second cleanup (crash-retry) raising on the missing
        directory instead of no-op'ing (§7 item 12)."""
        store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        store.cleanup("cyc_1")
        store.cleanup("cyc_1")
        assert store.latest_revision("cyc_1") is None

    def test_cleanup_expired_removes_only_expired_leases(self, store):
        """Bug caught: TTL sweep deleting unleased or still-live workspaces —
        an active cycle's workspace vanishing mid-run."""
        store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        store.seed("cyc_2", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        store.seed("cyc_3", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        store.touch_lease("cyc_1", ttl_seconds=100.0, now=1000.0)
        store.touch_lease("cyc_2", ttl_seconds=10.0, now=1000.0)
        # cyc_3 is unleased and must never be swept.
        removed = store.cleanup_expired(now=1050.0)
        assert removed == ("cyc_2",)
        assert store.latest_revision("cyc_1") is not None
        assert store.latest_revision("cyc_3") is not None
