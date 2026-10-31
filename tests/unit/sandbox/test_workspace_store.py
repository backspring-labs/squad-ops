"""WorkspaceStore semantics (SIP-0102 §4.6/§7 — phase 102.1 slice b)."""

import pytest

from squadops.sandbox.models import RevisionOrigin, compute_revision_id, content_bytes
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


class TestTrackedDerivedNames:
    def test_a_checkout_that_tracks_derived_names_holds_its_pin_through_an_install(
        self, store, tmp_path
    ):
        """Bug caught (X-2, #2420): a Git checkout that tracks package-lock.json or a built
        dist/ file refused at seeding as derived state, or skipped by the live tree's read so it
        failed its own pin. Almost every Node repository commits its lockfile. Untracked state
        an install or a build writes still stays out of the pin."""
        files = {
            **FILES,
            "frontend/package-lock.json": '{"lockfileVersion": 3}\n',
            "dist/app.js": "built\n",
        }
        rev = store.seed("cyc_1", files, origin=RevisionOrigin.GIT_CHECKOUT)
        ws = store.workspace_dir("cyc_1")
        (ws / "frontend/node_modules/react").mkdir(parents=True)
        (ws / "frontend/node_modules/react/index.js").write_text("js", encoding="utf-8")
        (ws / "dist/chunk.js").write_text("untracked build output", encoding="utf-8")

        assert rev.revision_id == compute_revision_id(files)
        assert WorkspaceStore(tmp_path / "cycles").verify_pinned("cyc_1", rev.revision_id)

    def test_a_patch_may_change_a_tracked_derived_file_but_never_add_one(self, store):
        """Bug caught: an agent's dependency change refused because the lockfile it must edit
        is named like derived state, or a patch able to add derived state no revision names."""
        files = {**FILES, "frontend/package-lock.json": "{}\n"}
        seed = store.seed("cyc_1", files, origin=RevisionOrigin.GIT_CHECKOUT)
        rev, _ = store.apply_patch(
            "cyc_1",
            base_revision_id=seed.revision_id,
            files={"frontend/package-lock.json": '{"v": 2}\n'},
            origin=RevisionOrigin.AGENT_PATCH,
        )
        assert store.verify_pinned("cyc_1", rev.revision_id)

        with pytest.raises(WorkspaceEscapeError, match="derived-state"):
            store.apply_patch(
                "cyc_1",
                base_revision_id=rev.revision_id,
                files={"dist/new.js": "x"},
                origin=RevisionOrigin.AGENT_PATCH,
            )

    @pytest.mark.parametrize(
        ("origin", "path", "why"),
        [
            (RevisionOrigin.SCAFFOLD_SEED, "frontend/package-lock.json", "derived-state"),
            (RevisionOrigin.GIT_CHECKOUT, ".git/config", "never revision content"),
        ],
        ids=["a-scaffold-seeds-lockfile", "a-checkout-seeds-its-git"],
    )
    def test_derived_names_stay_refused_outside_a_checkout_and_git_always(
        self, store, origin, path, why
    ):
        """Bug caught: the checkout's exemption leaking to a scaffold seed, whose lockfile
        npm install rewrites, or a repository's .git seeded as content."""
        with pytest.raises(WorkspaceEscapeError, match=why):
            store.seed("cyc_1", {**FILES, path: "x"}, origin=origin)
        assert store.current_files("cyc_1") == {}


class TestExecutableBit:
    GRADLEW = {**FILES, "gradlew": "#!/bin/sh\necho build\n"}

    def test_an_executable_file_keeps_its_bit_and_its_pin_through_a_patch(self, store, tmp_path):
        """Bug caught (X-2, #2420): a checkout's ./gradlew seeded without its executable bit, so
        a declared command that runs it fails with Permission denied, or a patch to it dropping
        the bit."""
        seed = store.seed(
            "cyc_1", self.GRADLEW, origin=RevisionOrigin.GIT_CHECKOUT, executable={"gradlew"}
        )
        script = store.workspace_dir("cyc_1") / "gradlew"
        assert script.stat().st_mode & 0o100

        rev, _ = store.apply_patch(
            "cyc_1",
            base_revision_id=seed.revision_id,
            files={"gradlew": "#!/bin/sh\necho build two\n"},
            origin=RevisionOrigin.AGENT_PATCH,
        )
        assert store.current_executables("cyc_1") == {"gradlew"}
        assert WorkspaceStore(tmp_path / "cycles").verify_pinned("cyc_1", rev.revision_id)

    def test_a_file_that_loses_its_bit_no_longer_matches_its_pin(self, store):
        """Bug caught: the bit recorded but never compared, so a script that lost it verifies."""
        seed = store.seed(
            "cyc_1", self.GRADLEW, origin=RevisionOrigin.GIT_CHECKOUT, executable={"gradlew"}
        )
        (store.workspace_dir("cyc_1") / "gradlew").chmod(0o644)

        assert not store.verify_pinned("cyc_1", seed.revision_id)

    def test_a_scaffold_workspace_ignores_modes_as_it_always_has(self, store):
        """Bug caught: the executable bit compared in every workspace, so a scaffold tree whose
        file gains +x fails a pin it used to pass, and on a filesystem that reports every file
        executable (a Windows mount under WSL) every scaffold pin fails."""
        seed = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        (store.workspace_dir("cyc_1") / "backend/main.py").chmod(0o755)

        assert store.verify_pinned("cyc_1", seed.revision_id)
        rev, _ = store.apply_patch(
            "cyc_1",
            base_revision_id=seed.revision_id,
            files={"backend/main.py": "print('b')\n"},
            origin=RevisionOrigin.AGENT_PATCH,
        )
        assert store.verify_pinned("cyc_1", rev.revision_id)

    def test_a_scaffold_seed_cannot_declare_an_executable_file(self, store):
        """Bug caught: a mode accepted on a lineage that never compares modes, so the caller
        believes a bit is pinned that nothing checks."""
        with pytest.raises(ValueError, match="only for a repository's tracked tree"):
            store.seed(
                "cyc_1", self.GRADLEW, origin=RevisionOrigin.SCAFFOLD_SEED, executable={"gradlew"}
            )
        assert store.current_files("cyc_1") == {}

    def test_an_executable_path_the_seed_does_not_carry_is_refused(self, store):
        """Bug caught: a mode for a file that isn't there accepted and silently dropped."""
        with pytest.raises(ValueError, match="doesn't carry"):
            store.seed("cyc_1", FILES, origin=RevisionOrigin.GIT_CHECKOUT, executable={"gradlew"})
        assert store.current_files("cyc_1") == {}


class TestDisposableCopy:
    def test_a_copy_holds_exactly_the_pinned_revision_and_is_gone_after(self, store):
        """X-3a (#2421), contract 3. Bug caught: a copy that drops a binary or an executable
        bit, carries an install's untracked node_modules, outlives the command, or shares
        files with the live tree."""
        files = {**FILES, "assets/mark.png": PNG, "gradlew": "#!/bin/sh\n"}
        rev = store.seed("cyc_1", files, origin=RevisionOrigin.GIT_CHECKOUT, executable={"gradlew"})
        ws = store.workspace_dir("cyc_1")
        (ws / "node_modules").mkdir()
        (ws / "node_modules/x.js").write_text("installed", encoding="utf-8")

        with store.disposable_copy("cyc_1", rev.revision_id) as copy:
            held = {
                p.relative_to(copy).as_posix(): p.read_bytes()
                for p in copy.rglob("*")
                if p.is_file()
            }
            assert held == {p: content_bytes(c) for p, c in files.items()}
            assert (copy / "gradlew").stat().st_mode & 0o100
            (copy / "backend/main.py").write_text("changed in the copy", encoding="utf-8")

        assert not copy.exists()
        assert store.verify_pinned("cyc_1", rev.revision_id)

    def test_a_tree_that_moves_while_it_is_copied_yields_no_copy(self, store, monkeypatch):
        """Bug caught (the MacBook lane's review of #2447): a patch landing between the pin's
        check and the read, so the copy mixed two revisions and a check ran on a tree no
        revision names."""
        rev = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        read, reads = store.current_files, []

        def a_patch_lands_after_the_pin_check(cycle_id, **kw):
            reads.append(cycle_id)
            files = read(cycle_id, **kw)
            return files if len(reads) == 1 else {**files, "backend/main.py": "patched meanwhile"}

        monkeypatch.setattr(store, "current_files", a_patch_lands_after_the_pin_check)

        with pytest.raises(StaleBaseRevisionError, match="moved while"):
            with store.disposable_copy("cyc_1", rev.revision_id):
                pass
        assert not (store._cycle_dir("cyc_1") / "copies").exists() or not any(
            (store._cycle_dir("cyc_1") / "copies").iterdir()
        )

    def test_no_copy_is_taken_from_a_tree_that_left_its_pin(self, store):
        """Bug caught: a copy of whatever the live tree holds, so a command ran on content no
        revision names."""
        rev = store.seed("cyc_1", FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
        (store.workspace_dir("cyc_1") / "backend/main.py").write_text("drift", encoding="utf-8")

        with pytest.raises(StaleBaseRevisionError):
            with store.disposable_copy("cyc_1", rev.revision_id):
                pass


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

    @pytest.mark.parametrize("journalled", [False, True])
    def test_a_sweep_removes_the_stores_entries_and_keeps_the_journal(
        self, store, tmp_path, journalled
    ):
        """#2473. Bug caught: a cleanup or a lease sweep removing the cycle's whole directory, the
        operation journal's ``evidence/`` with it; or leaving an empty directory behind for every
        swept cycle, when nothing else was there."""
        from squadops.sandbox.evidence import OperationEvidenceJournal

        journal = OperationEvidenceJournal(tmp_path / "cycles")
        for cycle_id in ("cyc_1", "cyc_2"):
            store.seed(cycle_id, FILES, origin=RevisionOrigin.SCAFFOLD_SEED)
            if journalled:
                (tmp_path / "cycles" / cycle_id / "evidence").mkdir()
                (tmp_path / "cycles" / cycle_id / "evidence" / "operations.jsonl").write_text(
                    '{"operation": "run_declared_command"}\n'
                )
        store.touch_lease("cyc_2", ttl_seconds=10.0, now=1000.0)

        store.cleanup("cyc_1")
        assert store.cleanup_expired(now=1050.0) == ("cyc_2",)
        assert store.cleanup_expired(now=1050.0) == ()

        for cycle_id in ("cyc_1", "cyc_2"):
            assert store.latest_revision(cycle_id) is None
            kept = [e["operation"] for e in journal.read(cycle_id)]
            assert kept == (["run_declared_command"] if journalled else [])
            assert (tmp_path / "cycles" / cycle_id).exists() is journalled
