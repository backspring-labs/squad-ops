"""Tests for SIP-0076 artifact promotion (Phase 3).

Covers ACs 11, 12, 16, 19.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault
from squadops.cycles.models import ArtifactNotFoundError, ArtifactRef

pytestmark = [pytest.mark.domain_orchestration]

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)


def _make_artifact(**kwargs) -> ArtifactRef:
    defaults = {
        "artifact_id": "art_001",
        "project_id": "proj_001",
        "artifact_type": "code",
        "filename": "main.py",
        "content_hash": "sha256:abc",
        "size_bytes": 100,
        "media_type": "text/plain",
        "created_at": NOW,
        "cycle_id": "cyc_001",
        "run_id": "run_001",
    }
    defaults.update(kwargs)
    return ArtifactRef(**defaults)


@pytest.fixture
def vault(tmp_path):
    return FilesystemArtifactVault(base_dir=tmp_path)


@pytest.fixture
async def stored_artifact(vault):
    """Store a working artifact and return it."""
    ref = _make_artifact()
    stored = await vault.store(ref, b"print('hello')")
    return stored


# ---------------------------------------------------------------------------
# promote_artifact() (ACs 11, 12)
# ---------------------------------------------------------------------------


class TestPromoteArtifact:
    async def test_promote_changes_status(self, vault, stored_artifact):
        assert stored_artifact.promotion_status == "working"
        promoted = await vault.promote_artifact("art_001")
        assert promoted.promotion_status == "promoted"

    async def test_promote_is_idempotent(self, vault, stored_artifact):
        first = await vault.promote_artifact("art_001")
        second = await vault.promote_artifact("art_001")
        assert first.promotion_status == "promoted"
        assert second.promotion_status == "promoted"

    async def test_promote_unknown_raises(self, vault):
        with pytest.raises(ArtifactNotFoundError):
            await vault.promote_artifact("nonexistent")

    async def test_promoted_persists_across_reads(self, vault, stored_artifact):
        await vault.promote_artifact("art_001")
        ref = await vault.get_metadata("art_001")
        assert ref.promotion_status == "promoted"


# ---------------------------------------------------------------------------
# list_artifacts with promotion_status filter (AC 16)
# ---------------------------------------------------------------------------


class TestListArtifactsPromotionFilter:
    async def test_filter_working(self, vault, stored_artifact):
        results = await vault.list_artifacts(
            project_id="proj_001", promotion_status="working"
        )
        assert len(results) == 1
        assert results[0].promotion_status == "working"

    async def test_filter_promoted_empty_initially(self, vault, stored_artifact):
        results = await vault.list_artifacts(
            project_id="proj_001", promotion_status="promoted"
        )
        assert len(results) == 0

    async def test_filter_promoted_after_promote(self, vault, stored_artifact):
        await vault.promote_artifact("art_001")
        results = await vault.list_artifacts(
            project_id="proj_001", promotion_status="promoted"
        )
        assert len(results) == 1
        assert results[0].promotion_status == "promoted"

    async def test_no_filter_returns_all(self, vault, stored_artifact):
        # Store a second artifact and promote it
        ref2 = _make_artifact(artifact_id="art_002", filename="util.py")
        await vault.store(ref2, b"# util")
        await vault.promote_artifact("art_002")

        results = await vault.list_artifacts(project_id="proj_001")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Baseline rejects working artifacts (AC 19)
# ---------------------------------------------------------------------------


class TestBaselineRejectsWorking:
    """D6: set_baseline only succeeds for promoted artifacts.

    Note: This is tested at the route level (in test_artifact_promotion_api.py),
    because the baseline promotion check is a route-level concern (T6 pattern).
    Here we verify vault-level promotion state integrity.
    """

    async def test_working_artifact_has_correct_status(self, vault, stored_artifact):
        ref = await vault.get_metadata("art_001")
        assert ref.promotion_status == "working"

    async def test_promoted_artifact_has_correct_status(self, vault, stored_artifact):
        await vault.promote_artifact("art_001")
        ref = await vault.get_metadata("art_001")
        assert ref.promotion_status == "promoted"
