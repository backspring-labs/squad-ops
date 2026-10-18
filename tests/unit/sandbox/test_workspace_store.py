"""WorkspaceStore semantics (SIP-0102 §4.6/§7 — phase 102.1 slice b)."""

import pytest

from squadops.sandbox.models import RevisionOrigin, content_bytes
from squadops.sandbox.workspace import (
    AlreadySeededError,
    StaleBaseRevisionError,
    WorkspaceEscapeError,
    WorkspaceStore,
)

FILES = {"backend/main.py": "print('a')\n", "frontend/index.html": "<html></html>\n"}
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"  # a PNG's header: not UTF-8


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

    def test_a_refused_seed_leaves_no_file_for_the_next_seed_to_inherit(self, store):
        """Bug caught: a seed refused at its revision (an unknown origin) after its files were
        written. The next seed's tree then holds files its revision doesn't name, and it fails
        its own pin."""
        with pytest.raises(ValueError, match="unknown revision origin"):
            store.seed("cyc_1", {"stray.py": "x = 1\n"}, origin="git_clone")
        assert store.current_files("cyc_1") == {}

        rev = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        assert store.current_files("cyc_1") == FILES
        assert store.verify_pinned("cyc_1", rev.revision_id)


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

    @pytest.mark.parametrize(
        ("files", "origin", "error"),
        [
            # the first path is applied before the second escapes
            (
                {"backend/main.py": "print('b')\n", "../outside.py": "x"},
                RevisionOrigin.AGENT_PATCH,
                WorkspaceEscapeError,
            ),
            ({"backend/main.py": "print('b')\n", "frontend/index.html": None}, "warm", ValueError),
        ],
    )
    def test_a_refused_patch_leaves_the_live_tree_on_its_base(self, store, files, origin, error):
        """Bug caught: a patch refused part-way after some paths were written or deleted. The
        live tree no longer matches its base, so every later patch is refused as stale."""
        seed = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        with pytest.raises(error):
            store.apply_patch(
                "cyc_1", base_revision_id=seed.revision_id, files=files, origin=origin
            )

        assert store.current_files("cyc_1") == FILES
        rev, _ = store.apply_patch(
            "cyc_1",
            base_revision_id=seed.revision_id,
            files={"backend/main.py": "print('c')\n"},
            origin=RevisionOrigin.AGENT_PATCH,
        )
        assert store.verify_pinned("cyc_1", rev.revision_id)


class TestContentAsBytes:
    @pytest.mark.parametrize(
        "files",
        [
            {"assets/mark.png": PNG, "app.py": "x = 1\n"},
            {"run.bat": "@echo off\r\necho hi\r\n"},
            {"legacy.txt": "one\rtwo\r"},
        ],
        ids=["binary-asset", "crlf-line-endings", "cr-line-endings"],
    )
    def test_a_seeded_file_reads_back_as_its_bytes_and_holds_its_pin(self, store, tmp_path, files):
        """Bug caught (X-2, #2420): a file that isn't UTF-8 crashing the read, or text read in
        universal-newline mode, so a seeded \\r\\n file read back as \\n and failed its own pin.
        Both are ordinary in a product's Git checkout."""
        rev = store.seed("cyc_1", files, origin=RevisionOrigin.GIT_CHECKOUT)

        on_disk = {p: (store.workspace_dir("cyc_1") / p).read_bytes() for p in files}
        assert on_disk == {p: content_bytes(c) for p, c in files.items()}
        read_back = store.current_files("cyc_1")
        assert {p: content_bytes(c) for p, c in read_back.items()} == on_disk
        assert WorkspaceStore(tmp_path / "cycles").verify_pinned("cyc_1", rev.revision_id)

    def test_a_patch_replaces_a_binary_file_byte_for_byte(self, store):
        """Bug caught: patch content written as text, so a changed image is refused or mangled."""
        seed = store.seed("cyc_1", {"assets/mark.png": PNG}, origin=RevisionOrigin.GIT_CHECKOUT)
        rev, changed = store.apply_patch(
            "cyc_1",
            base_revision_id=seed.revision_id,
            files={"assets/mark.png": PNG + b"\xff"},
            origin=RevisionOrigin.AGENT_PATCH,
        )
        assert changed == ("assets/mark.png",)
        assert (store.workspace_dir("cyc_1") / "assets/mark.png").read_bytes() == PNG + b"\xff"
        assert store.verify_pinned("cyc_1", rev.revision_id)


class TestDerivedStateExclusion:
    def test_installed_dependencies_do_not_break_the_pin(self, store):
        """Bug caught: the first install (venv/node_modules into the
        bind-mounted workspace, §4.7) breaking pin verification and every
        subsequent stale-base check — the sandbox would refuse to build
        anything it had just installed dependencies for."""
        seed = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        ws = store.workspace_dir("cyc_1")
        (ws / "frontend/node_modules/react").mkdir(parents=True)
        (ws / "frontend/node_modules/react/index.js").write_text("js", encoding="utf-8")
        (ws / ".sandbox-venv/bin").mkdir(parents=True)
        (ws / ".sandbox-venv/bin/python").write_text("bin", encoding="utf-8")
        (ws / "backend/__pycache__").mkdir(parents=True)
        (ws / "backend/__pycache__/main.pyc").write_text("pyc", encoding="utf-8")
        # npm install generates a lockfile (live-smoke-proven) — derived, not pinned.
        (ws / "frontend/package-lock.json").write_text("{}", encoding="utf-8")
        assert store.verify_pinned("cyc_1", seed.revision_id)
        rev, _ = store.apply_patch(
            "cyc_1",
            base_revision_id=seed.revision_id,
            files={"backend/main.py": "print('b')\n"},
            origin=RevisionOrigin.AGENT_PATCH,
        )
        assert store.verify_pinned("cyc_1", rev.revision_id)

    def test_stack_two_build_output_including_binaries_does_not_break_the_pin(self, store):
        """Bug caught (SIP-0104 window roll 1, 2026-08-15): `.next/` — stack #2's build
        output, the analogue of `dist` — was not excluded, and `current_files` reads
        every unexcluded file as UTF-8. A webpack cache byte (0xa1) raised
        UnicodeDecodeError, so pin verification CRASHED and the audited app never
        reached boot. The binary content is the point of this test: the pre-existing
        exclusion test wrote its derived state as text and could not catch it."""
        seed = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        ws = store.workspace_dir("cyc_1")
        (ws / ".next/cache/webpack").mkdir(parents=True)
        (ws / ".next/cache/webpack/0.pack").write_bytes(b"\x00\xa1\xff binary chunk")
        (ws / ".next/BUILD_ID").write_text("abc123", encoding="utf-8")

        assert store.verify_pinned("cyc_1", seed.revision_id)

    def test_patching_derived_state_paths_is_rejected(self, store):
        """Bug caught: a patch writing into node_modules/dist — content that
        would exist on disk but never in any revision, silently diverging the
        tree from every pin."""
        seed = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        with pytest.raises(WorkspaceEscapeError, match="derived-state"):
            store.apply_patch(
                "cyc_1",
                base_revision_id=seed.revision_id,
                files={"frontend/node_modules/evil.js": "x"},
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
