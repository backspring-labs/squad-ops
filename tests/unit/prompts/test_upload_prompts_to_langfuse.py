"""Tests for scripts/maintainer/upload_prompts_to_langfuse.py (SIP-0084 Phase 6).

Each test answers "what bug would this catch?" — see docstrings.
"""

from __future__ import annotations

import hashlib
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Import helpers — the script lives outside the package tree, so we add it
# to sys.path and import the module directly.
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "maintainer"


@pytest.fixture(autouse=True)
def _import_upload_module(monkeypatch):
    """Make the upload script importable for every test."""
    monkeypatch.syspath_prepend(str(SCRIPT_DIR))


def _import():
    """Import the module fresh (after sys.path is patched)."""
    # Remove cached import if present so monkeypatch changes take effect
    sys.modules.pop("upload_prompts_to_langfuse", None)
    import upload_prompts_to_langfuse

    return upload_prompts_to_langfuse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_fragments_dir(tmp_path):
    """Create a minimal manifest + fragment files for testing."""
    frags_dir = tmp_path / "fragments"
    frags_dir.mkdir()

    role_dir = frags_dir / "roles" / "dev"
    role_dir.mkdir(parents=True)
    (role_dir / "identity.md").write_text("You are the dev agent.")

    shared_dir = frags_dir / "shared"
    shared_dir.mkdir()
    (shared_dir / "constraints.global.md").write_text("Global constraints.")

    manifest = {
        "version": "0.9.18",
        "fragments": [
            {
                "fragment_id": "identity",
                "path": "roles/dev/identity.md",
                "roles": ["dev"],
            },
            {
                "fragment_id": "constraints.global",
                "path": "shared/constraints.global.md",
                # No roles key → defaults to ["*"] (shared)
            },
            {
                "fragment_id": "missing_fragment",
                "path": "nonexistent.md",
            },
        ],
    }
    (frags_dir / "manifest.yaml").write_text(yaml.dump(manifest))
    return frags_dir


@pytest.fixture()
def fake_templates_dir(tmp_path):
    """Create minimal request templates for testing."""
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir()

    # Template WITH frontmatter template_id
    (tpl_dir / "request.cycle_task_base.md").write_text(
        textwrap.dedent("""\
        ---
        template_id: request.cycle_task_base
        version: "1"
        ---
        # Cycle Task Base
        Do the thing.
        """)
    )

    # Template WITHOUT frontmatter (falls back to stem)
    (tpl_dir / "request.plain.md").write_text("No frontmatter here.")

    return tpl_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCollectFragments:
    """Bug: wrong Langfuse naming convention breaks prompt resolution at runtime."""

    def test_role_specific_fragment_gets_role_suffix(self, fake_fragments_dir, monkeypatch):
        """Role-specific fragments must use `{id}--{role}` naming (SIP §9).
        Bug caught: if the suffix is missing or uses wrong delimiter, the
        LangfuseAssetAdapter cannot resolve the fragment by role.
        """
        mod = _import()
        monkeypatch.setattr(mod, "FRAGMENTS_DIR", fake_fragments_dir)
        monkeypatch.setattr(mod, "MANIFEST_PATH", fake_fragments_dir / "manifest.yaml")
        monkeypatch.setattr(mod, "REPO_ROOT", fake_fragments_dir.parent)

        entries = mod.collect_fragments()
        names = [e.name for e in entries]

        assert "identity--dev" in names, "Role-specific fragment must have --role suffix"
        # Shared fragment should NOT have a suffix
        assert "constraints.global" in names, "Shared fragment must use bare fragment_id"

    def test_missing_fragment_file_skipped_not_crash(self, fake_fragments_dir, monkeypatch, capsys):
        """Bug caught: if a manifest references a deleted file, the script crashes
        instead of warning and continuing with the remaining fragments.
        """
        mod = _import()
        monkeypatch.setattr(mod, "FRAGMENTS_DIR", fake_fragments_dir)
        monkeypatch.setattr(mod, "MANIFEST_PATH", fake_fragments_dir / "manifest.yaml")
        monkeypatch.setattr(mod, "REPO_ROOT", fake_fragments_dir.parent)

        entries = mod.collect_fragments()
        stderr = capsys.readouterr().err

        # Should still collect the 2 valid fragments (identity--dev + constraints.global)
        assert len(entries) == 2
        assert "WARNING" in stderr
        assert "nonexistent.md" in stderr

    def test_content_hash_matches_file_content(self, fake_fragments_dir, monkeypatch):
        """Bug caught: hash computed from wrong content (e.g. name instead of body)
        would break cache invalidation — stale prompts served after update.
        """
        mod = _import()
        monkeypatch.setattr(mod, "FRAGMENTS_DIR", fake_fragments_dir)
        monkeypatch.setattr(mod, "MANIFEST_PATH", fake_fragments_dir / "manifest.yaml")
        monkeypatch.setattr(mod, "REPO_ROOT", fake_fragments_dir.parent)

        entries = mod.collect_fragments()
        shared = next(e for e in entries if e.name == "constraints.global")

        expected = hashlib.sha256("Global constraints.".encode()).hexdigest()
        assert shared.content_hash == expected


class TestCollectTemplates:
    """Bug: template_id extraction from frontmatter fails → wrong Langfuse name."""

    def test_extracts_template_id_from_frontmatter(self, fake_templates_dir, monkeypatch):
        """Bug caught: if frontmatter parsing breaks, the template gets uploaded
        under the filename stem instead of the governed template_id.
        """
        mod = _import()
        monkeypatch.setattr(mod, "TEMPLATES_DIR", fake_templates_dir)
        monkeypatch.setattr(mod, "REPO_ROOT", fake_templates_dir.parent)

        entries = mod.collect_templates()
        names = {e.name for e in entries}

        assert "request.cycle_task_base" in names
        # Verify the full content is captured (not just the body after frontmatter)
        base = next(e for e in entries if e.name == "request.cycle_task_base")
        assert "# Cycle Task Base" in base.content

    def test_falls_back_to_stem_without_frontmatter(self, fake_templates_dir, monkeypatch):
        """Bug caught: templates without frontmatter should still be collected
        using the filename stem as the name.
        """
        mod = _import()
        monkeypatch.setattr(mod, "TEMPLATES_DIR", fake_templates_dir)
        monkeypatch.setattr(mod, "REPO_ROOT", fake_templates_dir.parent)

        entries = mod.collect_templates()
        names = {e.name for e in entries}

        assert "request.plain" in names


class TestUploadToLangfuse:
    """Bug: SDK called with wrong args → silent upload of garbage."""

    def test_calls_create_prompt_with_correct_args(self, monkeypatch):
        """Bug caught: wrong kwarg names, missing labels, wrong type parameter
        would cause Langfuse to reject or misclassify the prompt.
        """
        mod = _import()

        fake_client = MagicMock()
        fake_langfuse_cls = MagicMock(return_value=fake_client)
        fake_langfuse_mod = MagicMock()
        fake_langfuse_mod.Langfuse = fake_langfuse_cls
        monkeypatch.setitem(sys.modules, "langfuse", fake_langfuse_mod)

        entries = [
            mod.UploadEntry(
                name="constraints.global",
                content="Global constraints.",
                content_hash="abc123",
                asset_type="fragment",
                source_path="src/squadops/prompts/fragments/shared/constraints.global.md",
            ),
        ]

        success, errors = mod.upload_to_langfuse(
            entries, "http://localhost:3001", "pk-test", "sk-test", "staging"
        )

        assert success == 1
        assert errors == 0
        fake_client.create_prompt.assert_called_once_with(
            name="constraints.global",
            prompt="Global constraints.",
            labels=["staging"],
            type="text",
        )
        fake_client.flush.assert_called_once()

    def test_counts_errors_on_sdk_exception(self, monkeypatch):
        """Bug caught: if create_prompt raises, script must count the error
        and continue uploading remaining entries (not crash).
        """
        mod = _import()

        fake_client = MagicMock()
        fake_client.create_prompt.side_effect = RuntimeError("API 500")
        fake_langfuse_cls = MagicMock(return_value=fake_client)
        fake_langfuse_mod = MagicMock()
        fake_langfuse_mod.Langfuse = fake_langfuse_cls
        monkeypatch.setitem(sys.modules, "langfuse", fake_langfuse_mod)

        entries = [
            mod.UploadEntry(
                name="bad_entry",
                content="x",
                content_hash="h",
                asset_type="fragment",
                source_path="x.md",
            ),
            mod.UploadEntry(
                name="bad_entry_2",
                content="y",
                content_hash="h2",
                asset_type="fragment",
                source_path="y.md",
            ),
        ]

        success, errors = mod.upload_to_langfuse(
            entries, "http://localhost:3001", "pk", "sk", "production"
        )

        assert success == 0
        assert errors == 2
        # Both entries were attempted despite first failure
        assert fake_client.create_prompt.call_count == 2
        fake_client.flush.assert_called_once()


class TestDryRunLiveAssets:
    """Integration-level: verify dry-run against real repo assets."""

    def test_dry_run_collects_all_live_assets(self):
        """Bug caught: if the manifest or template directory structure changes
        and the script can no longer find assets, we'd upload an empty set.
        This test ensures the script finds a non-trivial number of real assets.
        """
        mod = _import()
        fragments = mod.collect_fragments()
        templates = mod.collect_templates()

        # We know from the dry-run output there are 21 fragments and 9 templates
        assert len(fragments) >= 15, f"Expected ≥15 fragments, got {len(fragments)}"
        assert len(templates) >= 5, f"Expected ≥5 templates, got {len(templates)}"

        # Every entry must have non-empty content and a 64-char hex hash
        for entry in fragments + templates:
            assert entry.content, f"{entry.name} has empty content"
            assert len(entry.content_hash) == 64, f"{entry.name} hash is not sha256"
