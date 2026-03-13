"""
Filesystem artifact vault adapter (SIP-0064).

Stores artifact bytes to local filesystem with JSON sidecar metadata.
Vault enforces integrity (content_hash, vault_uri) but NOT business policy (T6).

Layout:
  <base_dir>/
    <project_id>/<cycle_id>/<run_id>/<artifact_id>/metadata.json + <filename>
    <project_id>/.baselines.json
    <project_id>/_unattached/<artifact_id>/metadata.json + <filename>
    _index.json   (artifact_id → relative path)
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import tempfile
from pathlib import Path

from squadops.cycles.models import ArtifactNotFoundError, ArtifactRef
from squadops.ports.cycles.artifact_vault import ArtifactVaultPort

logger = logging.getLogger(__name__)

_DEFAULT_BASE_DIR = Path("data/artifacts")


class FilesystemArtifactVault(ArtifactVaultPort):
    """Stores artifacts on the local filesystem in a hierarchical layout."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self._base_dir = Path(base_dir) if base_dir else _DEFAULT_BASE_DIR
        self._base_dir.mkdir(parents=True, exist_ok=True)
        if not self._index_path.exists():
            self._rebuild_index()

    # --- Index management ---

    @property
    def _index_path(self) -> Path:
        return self._base_dir / "_index.json"

    def _load_index(self) -> dict[str, str]:
        if self._index_path.exists():
            return json.loads(self._index_path.read_text())
        return {}

    def _save_index(self, index: dict[str, str]) -> None:
        # Atomic write via temp file + rename
        fd, tmp = tempfile.mkstemp(dir=self._base_dir, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                json.dump(index, f, indent=2)
            Path(tmp).replace(self._index_path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def _update_index(self, artifact_id: str, rel_path: str) -> None:
        index = self._load_index()
        index[artifact_id] = rel_path
        self._save_index(index)

    def _rebuild_index(self) -> None:
        index: dict[str, str] = {}
        for meta_path in self._base_dir.rglob("metadata.json"):
            art_dir = meta_path.parent
            rel = str(art_dir.relative_to(self._base_dir))
            # The artifact_id is the last component of the path
            artifact_id = art_dir.name
            index[artifact_id] = rel
        self._save_index(index)

    # --- Path helpers ---

    def _artifact_dir_for_ref(self, ref: ArtifactRef) -> Path:
        if ref.cycle_id and ref.run_id:
            return self._base_dir / ref.project_id / ref.cycle_id / ref.run_id / ref.artifact_id
        return self._base_dir / ref.project_id / "_unattached" / ref.artifact_id

    def _baselines_path_for_project(self, project_id: str) -> Path:
        return self._base_dir / project_id / ".baselines.json"

    # --- Port implementation ---

    async def store(self, artifact: ArtifactRef, content: bytes) -> ArtifactRef:
        art_dir = self._artifact_dir_for_ref(artifact)
        art_dir.mkdir(parents=True, exist_ok=True)

        content_hash = hashlib.sha256(content).hexdigest()

        content_path = art_dir / artifact.filename
        content_path.parent.mkdir(parents=True, exist_ok=True)
        content_path.write_bytes(content)

        vault_uri = str(content_path)

        updated = dataclasses.replace(
            artifact,
            content_hash=content_hash,
            size_bytes=len(content),
            vault_uri=vault_uri,
        )

        meta_path = art_dir / "metadata.json"
        meta = dataclasses.asdict(updated)
        for key in ("created_at",):
            if meta.get(key) is not None:
                meta[key] = str(meta[key])
        meta_path.write_text(json.dumps(meta, indent=2))

        rel_path = str(art_dir.relative_to(self._base_dir))
        self._update_index(artifact.artifact_id, rel_path)

        logger.info("Stored artifact %s at %s", artifact.artifact_id, vault_uri)
        return updated

    async def retrieve(self, artifact_id: str) -> tuple[ArtifactRef, bytes]:
        art_dir = self._resolve_artifact_dir(artifact_id)
        meta_path = art_dir / "metadata.json"
        if not meta_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")

        ref = self._load_metadata(meta_path)
        content_path = art_dir / ref.filename
        content = content_path.read_bytes()
        return ref, content

    async def get_metadata(self, artifact_id: str) -> ArtifactRef:
        art_dir = self._resolve_artifact_dir(artifact_id)
        meta_path = art_dir / "metadata.json"
        if not meta_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")
        return self._load_metadata(meta_path)

    async def promote_artifact(self, artifact_id: str) -> ArtifactRef:
        art_dir = self._resolve_artifact_dir(artifact_id)
        meta_path = art_dir / "metadata.json"
        if not meta_path.exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")

        ref = self._load_metadata(meta_path)
        if ref.promotion_status == "promoted":
            return ref  # Idempotent

        updated = dataclasses.replace(ref, promotion_status="promoted")
        meta = dataclasses.asdict(updated)
        for key in ("created_at",):
            if meta.get(key) is not None:
                meta[key] = str(meta[key])
        meta_path.write_text(json.dumps(meta, indent=2))
        return updated

    async def list_artifacts(
        self,
        *,
        project_id: str | None = None,
        cycle_id: str | None = None,
        run_id: str | None = None,
        artifact_type: str | None = None,
        promotion_status: str | None = None,
    ) -> list[ArtifactRef]:
        results: list[ArtifactRef] = []
        if not self._base_dir.exists():
            return results

        # Determine narrowest scan directory
        if project_id and cycle_id and run_id:
            scan_dir = self._base_dir / project_id / cycle_id / run_id
        elif project_id and cycle_id:
            scan_dir = self._base_dir / project_id / cycle_id
        elif project_id:
            scan_dir = self._base_dir / project_id
        else:
            scan_dir = self._base_dir

        self._collect_artifacts(
            scan_dir, results, project_id, cycle_id, run_id, artifact_type, promotion_status
        )

        return results

    async def set_baseline(self, project_id: str, artifact_type: str, artifact_id: str) -> None:
        # Verify artifact exists via index
        art_dir = self._resolve_artifact_dir(artifact_id)
        if not (art_dir / "metadata.json").exists():
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")

        baselines = self._load_baselines(project_id)
        baselines[artifact_type] = artifact_id
        self._save_baselines(project_id, baselines)

    async def get_baseline(self, project_id: str, artifact_type: str) -> ArtifactRef | None:
        baselines = self._load_baselines(project_id)
        artifact_id = baselines.get(artifact_type)
        if artifact_id is None:
            return None
        try:
            return await self.get_metadata(artifact_id)
        except ArtifactNotFoundError:
            return None

    async def list_baselines(self, project_id: str) -> dict[str, ArtifactRef]:
        baselines = self._load_baselines(project_id)
        result = {}
        for art_type, artifact_id in baselines.items():
            try:
                ref = await self.get_metadata(artifact_id)
                result[art_type] = ref
            except ArtifactNotFoundError:
                continue
        return result

    # --- Internal helpers ---

    def _resolve_artifact_dir(self, artifact_id: str) -> Path:
        """Look up artifact_id in the index and return its directory."""
        index = self._load_index()
        rel_path = index.get(artifact_id)
        if rel_path is None:
            raise ArtifactNotFoundError(f"Artifact not found: {artifact_id}")
        return self._base_dir / rel_path

    def _collect_artifacts(
        self,
        scan_dir: Path,
        results: list[ArtifactRef],
        project_id: str | None,
        cycle_id: str | None,
        run_id: str | None,
        artifact_type: str | None,
        promotion_status: str | None = None,
    ) -> None:
        if not scan_dir.exists():
            return
        for meta_path in scan_dir.rglob("metadata.json"):
            ref = self._load_metadata(meta_path)
            if project_id and ref.project_id != project_id:
                continue
            if cycle_id and ref.cycle_id != cycle_id:
                continue
            if run_id and ref.run_id != run_id:
                continue
            if artifact_type and ref.artifact_type != artifact_type:
                continue
            if promotion_status and ref.promotion_status != promotion_status:
                continue
            results.append(ref)

    def _load_metadata(self, meta_path: Path) -> ArtifactRef:
        data = json.loads(meta_path.read_text())
        from datetime import datetime

        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        # D19: Legacy artifacts without promotion_status default to "working" at read time
        if "promotion_status" not in data:
            data["promotion_status"] = "working"
        # SIP-0084: JSON arrays → tuples for provenance tuple fields
        for key in (
            "system_fragment_ids",
            "system_fragment_versions",
            "capability_supplement_ids",
        ):
            if isinstance(data.get(key), list):
                data[key] = tuple(data[key])
        return ArtifactRef(**data)

    def _load_baselines(self, project_id: str) -> dict:
        path = self._baselines_path_for_project(project_id)
        if path.exists():
            return json.loads(path.read_text())
        return {}

    def _save_baselines(self, project_id: str, baselines: dict) -> None:
        path = self._baselines_path_for_project(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(baselines, indent=2))
