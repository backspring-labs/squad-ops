"""Tests for SIP-0084 Phase 5: prompt provenance on ArtifactRef.

Covers model round-trip, vault serialization, DTO mapping, and
handler provenance recording.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from squadops.cycles.models import ArtifactRef

pytestmark = [pytest.mark.domain_contracts]


NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)


def _base_artifact(**overrides) -> ArtifactRef:
    defaults = {
        "artifact_id": "art_prov_001",
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
    defaults.update(overrides)
    return ArtifactRef(**defaults)


# ---------------------------------------------------------------------------
# ArtifactRef provenance fields
# ---------------------------------------------------------------------------


class TestArtifactRefProvenance:
    def test_provenance_fields_default_none(self):
        ref = _base_artifact()
        assert ref.system_prompt_bundle_hash is None
        assert ref.system_fragment_ids is None
        assert ref.system_fragment_versions is None
        assert ref.request_template_id is None
        assert ref.request_template_version is None
        assert ref.request_render_hash is None
        assert ref.capability_supplement_ids is None
        assert ref.full_invocation_bundle_hash is None
        assert ref.prompt_environment is None

    def test_provenance_fields_populated(self):
        ref = _base_artifact(
            system_prompt_bundle_hash="sha256:sys001",
            system_fragment_ids=("frag.identity", "frag.constraints"),
            system_fragment_versions=("v1", "v2"),
            request_template_id="request.cycle_task_base",
            request_template_version="v3",
            request_render_hash="sha256:rend001",
            capability_supplement_ids=("cap.python_cli",),
            full_invocation_bundle_hash="sha256:full001",
            prompt_environment="production",
        )
        assert ref.system_prompt_bundle_hash == "sha256:sys001"
        assert ref.system_fragment_ids == ("frag.identity", "frag.constraints")
        assert ref.system_fragment_versions == ("v1", "v2")
        assert ref.request_template_id == "request.cycle_task_base"
        assert ref.request_template_version == "v3"
        assert ref.request_render_hash == "sha256:rend001"
        assert ref.capability_supplement_ids == ("cap.python_cli",)
        assert ref.full_invocation_bundle_hash == "sha256:full001"
        assert ref.prompt_environment == "production"

    def test_replace_adds_provenance_to_existing(self):
        ref = _base_artifact()
        updated = dataclasses.replace(
            ref,
            system_prompt_bundle_hash="sha256:abc",
            request_template_id="request.test",
            request_template_version="v1",
            request_render_hash="sha256:rend",
            prompt_environment="staging",
        )
        assert updated.system_prompt_bundle_hash == "sha256:abc"
        assert updated.request_template_id == "request.test"
        assert updated.prompt_environment == "staging"
        # Original unchanged (frozen)
        assert ref.system_prompt_bundle_hash is None

    def test_dataclasses_asdict_includes_provenance(self):
        ref = _base_artifact(
            request_template_id="request.dev",
            request_template_version="v2",
            request_render_hash="sha256:rr",
        )
        d = dataclasses.asdict(ref)
        assert d["request_template_id"] == "request.dev"
        assert d["request_template_version"] == "v2"
        assert d["request_render_hash"] == "sha256:rr"
        assert d["system_prompt_bundle_hash"] is None


# ---------------------------------------------------------------------------
# Vault round-trip
# ---------------------------------------------------------------------------


class TestVaultProvenanceRoundTrip:
    @pytest.fixture
    def vault(self, tmp_path):
        from adapters.cycles.filesystem_artifact_vault import FilesystemArtifactVault

        return FilesystemArtifactVault(base_dir=tmp_path)

    async def test_store_and_retrieve_preserves_provenance(self, vault):
        ref = _base_artifact(
            system_prompt_bundle_hash="sha256:sys",
            system_fragment_ids=("frag.identity", "frag.task"),
            system_fragment_versions=("v1", "v2"),
            request_template_id="request.cycle_task_base",
            request_template_version="v5",
            request_render_hash="sha256:render",
            capability_supplement_ids=("cap.python_cli",),
            full_invocation_bundle_hash="sha256:full",
            prompt_environment="production",
        )
        stored = await vault.store(ref, b"print('hello')")
        retrieved_ref, _ = await vault.retrieve(stored.artifact_id)

        assert retrieved_ref.system_prompt_bundle_hash == "sha256:sys"
        assert retrieved_ref.system_fragment_ids == ("frag.identity", "frag.task")
        assert retrieved_ref.system_fragment_versions == ("v1", "v2")
        assert retrieved_ref.request_template_id == "request.cycle_task_base"
        assert retrieved_ref.request_template_version == "v5"
        assert retrieved_ref.request_render_hash == "sha256:render"
        assert retrieved_ref.capability_supplement_ids == ("cap.python_cli",)
        assert retrieved_ref.full_invocation_bundle_hash == "sha256:full"
        assert retrieved_ref.prompt_environment == "production"

    async def test_store_and_retrieve_without_provenance(self, vault):
        """Legacy artifact without provenance fields round-trips cleanly."""
        ref = _base_artifact()
        stored = await vault.store(ref, b"print('hello')")
        retrieved_ref, _ = await vault.retrieve(stored.artifact_id)

        assert retrieved_ref.system_prompt_bundle_hash is None
        assert retrieved_ref.request_template_id is None
        assert retrieved_ref.prompt_environment is None

    async def test_tuple_fields_survive_json_serialization(self, vault):
        """JSON serializes tuples as arrays; vault must restore them as tuples."""
        ref = _base_artifact(
            system_fragment_ids=("a", "b", "c"),
            capability_supplement_ids=("x",),
        )
        stored = await vault.store(ref, b"code")
        retrieved_ref, _ = await vault.retrieve(stored.artifact_id)

        assert isinstance(retrieved_ref.system_fragment_ids, tuple)
        assert isinstance(retrieved_ref.capability_supplement_ids, tuple)
        assert retrieved_ref.system_fragment_ids == ("a", "b", "c")


# ---------------------------------------------------------------------------
# DTO mapping
# ---------------------------------------------------------------------------


class TestDTOProvenanceMapping:
    def test_artifact_to_response_maps_provenance(self):
        from squadops.api.routes.cycles.mapping import artifact_to_response

        ref = _base_artifact(
            system_prompt_bundle_hash="sha256:sys",
            system_fragment_ids=("frag.id",),
            system_fragment_versions=("v1",),
            request_template_id="request.test",
            request_template_version="v2",
            request_render_hash="sha256:rend",
            prompt_environment="staging",
        )
        dto = artifact_to_response(ref)

        assert dto.system_prompt_bundle_hash == "sha256:sys"
        assert dto.system_fragment_ids == ("frag.id",)
        assert dto.request_template_id == "request.test"
        assert dto.request_template_version == "v2"
        assert dto.request_render_hash == "sha256:rend"
        assert dto.prompt_environment == "staging"

    def test_artifact_to_response_none_provenance(self):
        from squadops.api.routes.cycles.mapping import artifact_to_response

        ref = _base_artifact()
        dto = artifact_to_response(ref)

        assert dto.system_prompt_bundle_hash is None
        assert dto.request_template_id is None
        assert dto.prompt_environment is None
