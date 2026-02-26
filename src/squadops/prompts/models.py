"""
Domain models for the prompt assembly system.

All models are immutable (frozen dataclasses) to ensure deterministic
behavior and prevent accidental mutation during assembly.
"""

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class PromptFragment:
    """
    Immutable unit of prompt text.

    A fragment represents a single piece of prompt content identified by
    a unique fragment_id. It must possess a SHA256 hash and metadata
    identifying its layer.

    Attributes:
        fragment_id: Unique identifier for this fragment
        layer: Layer type (identity, constraints, lifecycle, task_type, recovery)
        content: The actual prompt text content
        sha256_hash: SHA256 hash of the content for integrity verification
        roles: List of role IDs this applies to (["*"] for shared/all roles)
        version: System version this fragment belongs to
    """

    fragment_id: str
    layer: str
    content: str
    sha256_hash: str
    roles: tuple[str, ...]  # Using tuple for immutability
    version: str

    def __post_init__(self) -> None:
        """Validate fragment on creation."""
        valid_layers = {"identity", "constraints", "lifecycle", "task_type", "recovery"}
        if self.layer not in valid_layers:
            raise ValueError(f"Invalid layer '{self.layer}'. Must be one of: {valid_layers}")

    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify that the content hash matches the stored hash."""
        return self.compute_hash(self.content) == self.sha256_hash


@dataclass(frozen=True)
class AssembledPrompt:
    """
    Final immutable output of prompt assembly.

    Carries lineage of the fragment hashes used in its construction,
    enabling audit and determinism verification.

    Attributes:
        content: The final assembled prompt text
        fragment_hashes: Ordered list of fragment hashes used in assembly
        assembly_hash: SHA256 hash of the final content
        role: The agent role this prompt was assembled for
        hook: The lifecycle hook (e.g., agent_start, task_complete)
        version: System version used for assembly
    """

    content: str
    fragment_hashes: tuple[str, ...]  # Using tuple for immutability
    assembly_hash: str
    role: str
    hook: str
    version: str

    @staticmethod
    def compute_assembly_hash(content: str) -> str:
        """Compute SHA256 hash of assembled content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ManifestFragment:
    """
    Fragment entry in the manifest (metadata without content).

    Used for manifest storage - actual content is loaded separately.
    """

    fragment_id: str
    path: str
    layer: str
    roles: tuple[str, ...]
    sha256: str


@dataclass(frozen=True)
class PromptManifest:
    """
    Aggregate root - single source of truth for versioned fragments.

    The manifest anchors all fragments to a specific version and provides
    integrity validation by storing expected hashes.

    Attributes:
        version: System version this manifest represents
        updated_at: ISO timestamp of last manifest update
        fragments: Mapping of fragment_id to ManifestFragment metadata
        manifest_hash: Hash of the manifest itself for integrity
    """

    version: str
    updated_at: str
    fragments: tuple[ManifestFragment, ...]  # Using tuple for immutability
    manifest_hash: str

    def get_fragment_meta(self, fragment_id: str) -> ManifestFragment | None:
        """Get fragment metadata by ID."""
        for frag in self.fragments:
            if frag.fragment_id == fragment_id:
                return frag
        return None

    def get_fragments_by_layer(self, layer: str) -> list[ManifestFragment]:
        """Get all fragments for a specific layer."""
        return [f for f in self.fragments if f.layer == layer]

    def get_fragments_by_role(self, role: str) -> list[ManifestFragment]:
        """Get all fragments applicable to a role (including shared)."""
        return [f for f in self.fragments if role in f.roles or "*" in f.roles]

    @staticmethod
    def compute_manifest_hash(version: str, fragments: tuple[ManifestFragment, ...]) -> str:
        """Compute hash of manifest contents for integrity verification."""
        content = f"{version}:" + ",".join(
            f"{f.fragment_id}:{f.sha256}" for f in sorted(fragments, key=lambda x: x.fragment_id)
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
