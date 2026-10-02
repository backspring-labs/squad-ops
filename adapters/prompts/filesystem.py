"""
Filesystem-based prompt repository for local development.

Implements the PromptRepository port using the macOS/POSIX filesystem.
"""

import logging
from pathlib import Path

import yaml

from squadops.ports.prompts.repository import PromptRepository
from squadops.prompts.exceptions import (
    FragmentNotFoundError,
    HashMismatchError,
    ManifestValidationError,
)
from squadops.prompts.fragment_stamp import (
    STAMP_FILENAME,
    FragmentStamp,
    fragment_body,
    hash_fragment_file,
    read_stamp,
)
from squadops.prompts.frontmatter import read_frontmatter
from squadops.prompts.models import ManifestFragment, PromptFragment, PromptManifest

logger = logging.getLogger(__name__)


class FileSystemPromptRepository(PromptRepository):
    """
    Filesystem-based prompt storage for local development.

    Directory structure:
    {base_path}/
    ├── manifest.yaml
    ├── shared/
    │   ├── identity/
    │   ├── constraints/
    │   └── lifecycle/
    └── roles/
        ├── lead/
        ├── dev/
        ├── strat/
        └── qa/
    """

    def __init__(self, base_path: Path, manifest_path: Path | None = None):
        """
        Initialize filesystem repository.

        Args:
            base_path: Root directory containing prompts
            manifest_path: Optional explicit manifest path (defaults to {base_path}/manifest.yaml)
        """
        self.base_path = Path(base_path)
        self.manifest_path = manifest_path or self.base_path / "manifest.yaml"
        self._manifest: PromptManifest | None = None
        # The build stamp (#353): present in an image, absent in a source checkout.
        self._stamp: FragmentStamp | None = None
        self._fragment_cache: dict[str, PromptFragment] = {}

    def _load_manifest(self) -> PromptManifest:
        """Load and parse the manifest file."""
        if not self.manifest_path.exists():
            raise ManifestValidationError(
                f"Manifest not found: {self.manifest_path}",
                {"path": str(self.manifest_path)},
            )

        try:
            with open(self.manifest_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ManifestValidationError(f"Invalid manifest YAML: {e}") from e

        if not data:
            raise ManifestValidationError("Empty manifest file")

        # Parse fragments
        fragments = []
        for frag_data in data.get("fragments", []):
            fragments.append(
                ManifestFragment(
                    fragment_id=frag_data["fragment_id"],
                    path=frag_data["path"],
                    layer=frag_data["layer"],
                    roles=tuple(frag_data.get("roles", ["*"])),
                )
            )

        manifest = PromptManifest(
            version=data.get("version", "0.0.0"),
            updated_at=data.get("updated_at", ""),
            fragments=tuple(fragments),
        )

        # #327: fail hard — a warn-and-continue here means agents silently run a prompt set
        # that is not the one they shipped with. #353: the reference is the build stamp, and
        # the check reads the fragments themselves, not a hash column kept beside them.
        stamp = read_stamp(self.manifest_path)
        if stamp is not None:
            self._verify_pack_against_stamp(manifest, stamp)
        self._stamp = stamp

        return manifest

    def _verify_pack_against_stamp(self, manifest: PromptManifest, stamp: FragmentStamp) -> None:
        """Every registered fragment reads as the build stamped it.

        Raises:
            ManifestValidationError: the stamp describes a different manifest.
            HashMismatchError: a fragment's content changed after the build.
        """
        stamp_path = self.manifest_path.parent / STAMP_FILENAME
        registered = {meta.path for meta in manifest.fragments}
        if stamp.version != manifest.version or set(stamp.hashes) != registered:
            raise ManifestValidationError(
                f"{stamp_path} does not describe this manifest: it stamped pack "
                f"{stamp.version} with {len(stamp.hashes)} fragments, the manifest is "
                f"{manifest.version} with {len(registered)} (only in the stamp: "
                f"{sorted(set(stamp.hashes) - registered)}, only in the manifest: "
                f"{sorted(registered - set(stamp.hashes))}). The image build writes the stamp; "
                f"a source checkout needs none.",
                {"path": str(stamp_path)},
            )
        for meta in manifest.fragments:
            path = self.base_path / meta.path
            actual = hash_fragment_file(path) if path.is_file() else "<file missing>"
            if actual != stamp.hashes[meta.path]:
                raise HashMismatchError(
                    fragment_id=f"{meta.fragment_id} ({meta.path})",
                    expected=stamp.hashes[meta.path],
                    actual=actual,
                )

    def get_manifest(self) -> PromptManifest:
        """Load the prompt manifest (cached)."""
        if self._manifest is None:
            self._manifest = self._load_manifest()
        return self._manifest

    def _resolve_path(self, fragment_id: str, role: str | None = None) -> Path | None:
        """
        Resolve the filesystem path for a fragment.

        Search order:
        1. Role-specific: {base_path}/roles/{role}/{fragment_id}.md
        2. Shared: Use path from manifest

        Args:
            fragment_id: Fragment identifier
            role: Optional role for role-specific lookup

        Returns:
            Path if found, None otherwise
        """
        # Try role-specific first
        if role:
            role_path = self.base_path / "roles" / role / f"{fragment_id}.md"
            if role_path.exists():
                return role_path

        # Fall back to manifest path
        manifest = self.get_manifest()
        meta = manifest.get_fragment_meta(fragment_id)
        if meta:
            shared_path = self.base_path / meta.path
            if shared_path.exists():
                return shared_path

        return None

    def _parse_fragment_file(
        self, path: Path, manifest_meta: ManifestFragment | None = None
    ) -> PromptFragment:
        """
        Parse a fragment file, extracting header and content.

        Fragment files have a YAML header block:
        ---
        fragment_id: identity.base_agent
        layer: identity
        version: 0.8.5
        roles: ["*"]
        ---
        <content>

        Args:
            path: Path to the fragment file
            manifest_meta: Optional manifest metadata for validation

        Returns:
            Parsed PromptFragment
        """
        with open(path, encoding="utf-8") as f:
            raw_content = f.read()

        header, _ = read_frontmatter(raw_content)

        # Content (and its hash) come from the shared canonical extractor.
        content = fragment_body(raw_content)

        # Extract metadata (prefer file header, fall back to manifest)
        fragment_id = header.get("fragment_id") or (
            manifest_meta.fragment_id if manifest_meta else path.stem
        )
        layer = header.get("layer") or (manifest_meta.layer if manifest_meta else "identity")
        version = header.get("version") or (self.get_manifest().version)
        roles = tuple(header.get("roles", manifest_meta.roles if manifest_meta else ["*"]))

        # Compute actual hash
        actual_hash = PromptFragment.compute_hash(content)

        # SIP-0057 §8.3: in an image, a fragment read after the manifest loaded is still the
        # one the build stamped. The manifest load is what reads the stamp.
        self.get_manifest()
        if self._stamp is not None:
            expected = self._stamp.hashes.get(path.relative_to(self.base_path).as_posix())
            if expected != actual_hash:
                raise HashMismatchError(
                    fragment_id=f"{fragment_id} ({path})",
                    expected=expected or "<not in the build stamp>",
                    actual=actual_hash,
                )

        return PromptFragment(
            fragment_id=fragment_id,
            layer=layer,
            content=content,
            sha256_hash=actual_hash,
            roles=roles,
            version=version,
        )

    def get_fragment(self, fragment_id: str, role: str | None = None) -> PromptFragment:
        """
        Get a fragment by ID, optionally with role-specific override.

        Args:
            fragment_id: Unique identifier for the fragment
            role: Optional role ID for role-specific override lookup

        Returns:
            The resolved PromptFragment

        Raises:
            FragmentNotFoundError: If fragment cannot be found
        """
        # Check cache
        cache_key = f"{fragment_id}:{role or 'shared'}"
        if cache_key in self._fragment_cache:
            return self._fragment_cache[cache_key]

        # Resolve path
        path = self._resolve_path(fragment_id, role)
        if path is None:
            raise FragmentNotFoundError(fragment_id, role)

        # Get manifest metadata for validation
        manifest = self.get_manifest()
        manifest_meta = manifest.get_fragment_meta(fragment_id)

        # Parse and cache
        fragment = self._parse_fragment_file(path, manifest_meta)
        self._fragment_cache[cache_key] = fragment

        return fragment

    def list_fragments(
        self, layer: str | None = None, role: str | None = None
    ) -> list[PromptFragment]:
        """
        List available fragments, optionally filtered.

        Args:
            layer: Optional layer filter
            role: Optional role filter

        Returns:
            List of matching PromptFragment objects
        """
        manifest = self.get_manifest()
        fragments = []

        for meta in manifest.fragments:
            # Apply filters
            if layer and meta.layer != layer:
                continue
            if role and role not in meta.roles and "*" not in meta.roles:
                continue

            try:
                fragment = self.get_fragment(meta.fragment_id, role)
                fragments.append(fragment)
            except FragmentNotFoundError:
                logger.warning(f"Fragment in manifest not found on disk: {meta.fragment_id}")

        return fragments

    def validate_integrity(self) -> bool:
        """
        Verify every fragment still reads as the image build stamped it (#353).

        A source checkout has no stamp: its files are the reference, and there is nothing
        shipped to verify against.

        Returns:
            True if every fragment matches the stamp, or there is no stamp

        Raises:
            ManifestValidationError: If the stamp describes a different manifest
            HashMismatchError: If any fragment fails integrity check
        """
        manifest = self.get_manifest()
        if self._stamp is None:
            logger.info("No prompt build stamp: the source fragments are the reference")
            return True
        self._verify_pack_against_stamp(manifest, self._stamp)
        logger.info("All fragment hashes verified against the build stamp")
        return True

    def fragment_exists(self, fragment_id: str, role: str | None = None) -> bool:
        """
        Check if a fragment exists without loading it.

        Args:
            fragment_id: Unique identifier for the fragment
            role: Optional role for role-specific check

        Returns:
            True if the fragment exists
        """
        return self._resolve_path(fragment_id, role) is not None
