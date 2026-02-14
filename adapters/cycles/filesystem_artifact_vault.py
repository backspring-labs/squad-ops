"""
Filesystem artifact vault adapter (SIP-0064).

Stores artifact bytes to local filesystem with JSON sidecar metadata.
Vault enforces integrity (content_hash, vault_uri) but NOT business policy (T6).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from pathlib import Path

from squadops.cycles.models import ArtifactNotFoundError, ArtifactRef
from squadops.ports.cycles.artifact_vault import ArtifactVaultPort

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path("data/artifacts")


class FilesystemArtifactVault(ArtifactVaultPort):
    """Stores artifacts on the local filesystem."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else _DEFAULT_BASE_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._baselines_path = self._base_dir / ".baselines.json"

    def _artifact_dir(self, artifact_id: str) -> Path:
        return self._base_dir / artifact_id

    async def store(self, artifact: ArtifactRef, content: bytes) -> ArtifactRef:
        art_dir = self._artifact_dir(artifact.artifact_id)
        art_dir.mkdir(parents=True, exist_ok=True)

        # Compute content hash
        content_hash = hashlib.sha256(content).hexdigest()

        # Write content (ensure parent dirs exist for nested filenames like pkg/module.py)
        content_path = art_dir / artifact.filename
        content_path.parent.mkdir(parents=True, exist_ok=True)
        content_path.write_bytes(content)

        vault_uri = str(content_path)

        # Build updated artifact ref
        updated = dataclasses.replace(
            artifact,
            content_hash=content_hash,
            size_bytes=len(content),
            vault_uri=vault_uri,
        )

        # Write sidecar metadata
        meta_path = art_dir / "metadata.json"
        meta = dataclasses.asdict(updated)
        # Convert datetime to string for JSON
        for key in ("created_at",):
            if meta.get(key) is not None:
                meta[key] = str(meta[key])
        meta_path.write_text(json.dumps(meta, indent=2))

        logger.info("Stored artifact %s at %s", artifact.artifact_id, vault_uri)
        return updated

    async def retrieve(self, artifact_id: str) -> tuple[ArtifactRef, bytes]:
        art_dir = self._artifact_dir(artifact_id)
        meta_path = art_dir / "metadata.json"
        if not meta_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")

        ref = self._load_metadata(meta_path)
        content_path = art_dir / ref.filename
        content = content_path.read_bytes()
        return ref, content

    async def get_metadata(self, artifact_id: str) -> ArtifactRef:
        art_dir = self._artifact_dir(artifact_id)
        meta_path = art_dir / "metadata.json"
        if not meta_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")
        return self._load_metadata(meta_path)

    async def list_artifacts(
        self,
        *,
        project_id: str | None = None,
        cycle_id: str | None = None,
        run_id: str | None = None,
        artifact_type: str | None = None,
    ) -> list[ArtifactRef]:
        results = []
        if not self._base_dir.exists():
            return results

        for art_dir in self._base_dir.iterdir():
            if not art_dir.is_dir() or art_dir.name.startswith("."):
                continue
            meta_path = art_dir / "metadata.json"
            if not meta_path.exists():
                continue
            ref = self._load_metadata(meta_path)
            if project_id and ref.project_id != project_id:
                continue
            if cycle_id and ref.cycle_id != cycle_id:
                continue
            if run_id and ref.run_id != run_id:
                continue
            if artifact_type and ref.artifact_type != artifact_type:
                continue
            results.append(ref)
        return results

    async def set_baseline(
        self, project_id: str, artifact_type: str, artifact_id: str
    ) -> None:
        # Verify artifact exists
        art_dir = self._artifact_dir(artifact_id)
        if not (art_dir / "metadata.json").exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")

        baselines = self._load_baselines()
        baselines.setdefault(project_id, {})[artifact_type] = artifact_id
        self._save_baselines(baselines)

    async def get_baseline(
        self, project_id: str, artifact_type: str
    ) -> ArtifactRef | None:
        baselines = self._load_baselines()
        artifact_id = baselines.get(project_id, {}).get(artifact_type)
        if artifact_id is None:
            return None
        try:
            return await self.get_metadata(artifact_id)
        except ArtifactNotFoundError:
            return None

    async def list_baselines(self, project_id: str) -> dict[str, ArtifactRef]:
        baselines = self._load_baselines()
        project_baselines = baselines.get(project_id, {})
        result = {}
        for art_type, artifact_id in project_baselines.items():
            try:
                ref = await self.get_metadata(artifact_id)
                result[art_type] = ref
            except ArtifactNotFoundError:
                continue
        return result

    # --- Internal helpers ---

    def _load_metadata(self, meta_path: Path) -> ArtifactRef:
        data = json.loads(meta_path.read_text())
        from datetime import datetime

        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return ArtifactRef(**data)

    def _load_baselines(self) -> dict:
        if self._baselines_path.exists():
            return json.loads(self._baselines_path.read_text())
        return {}

    def _save_baselines(self, baselines: dict) -> None:
        self._baselines_path.write_text(json.dumps(baselines, indent=2))
