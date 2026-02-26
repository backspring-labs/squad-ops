"""
Domain service for prompt assembly.

Implements the stateless logic for layering and selection (the "Winning Rule")
as defined in SIP-0057.
"""

from squadops.ports.prompts.repository import PromptRepository
from squadops.ports.prompts.service import PromptService
from squadops.prompts.exceptions import (
    HashMismatchError,
    MandatoryLayerMissingError,
)
from squadops.prompts.models import AssembledPrompt, PromptFragment


class PromptAssembler(PromptService):
    """
    Stateless domain service implementing layering and selection logic.

    This service assembles prompts by:
    1. Resolving fragments using the hierarchical search path
    2. Verifying integrity hashes before concatenation
    3. Concatenating in strict layer order
    4. Producing an immutable AssembledPrompt with lineage
    """

    # Layer ordering (bottom-up assembly)
    LAYER_ORDER = ["identity", "constraints", "lifecycle", "task_type", "recovery"]

    # Layers that must be present for valid assembly
    MANDATORY_LAYERS = ["identity", "constraints"]

    # Fragment ID patterns for each layer
    LAYER_FRAGMENT_PATTERNS = {
        "identity": "identity",
        "constraints": "constraints.global",
        "lifecycle": "lifecycle.{hook}",
        "task_type": "task_type.{task_type}",
        "recovery": "recovery",
    }

    def __init__(self, repository: PromptRepository):
        """
        Initialize assembler with a repository.

        Args:
            repository: PromptRepository implementation for fragment access
        """
        self.repository = repository
        self._manifest = None

    def _get_manifest(self):
        """Lazy-load and cache manifest."""
        if self._manifest is None:
            self._manifest = self.repository.get_manifest()
        return self._manifest

    def _resolve_fragment_id(
        self, layer: str, hook: str | None = None, task_type: str | None = None
    ) -> str:
        """
        Resolve the fragment ID for a given layer and context.

        Args:
            layer: Layer type
            hook: Lifecycle hook (for lifecycle layer)
            task_type: Task type (for task_type layer)

        Returns:
            Fragment ID string
        """
        pattern = self.LAYER_FRAGMENT_PATTERNS[layer]

        if "{hook}" in pattern and hook:
            pattern = pattern.replace("{hook}", hook)
        if "{task_type}" in pattern and task_type:
            pattern = pattern.replace("{task_type}", task_type)

        return pattern

    def _resolve_fragment(
        self,
        layer: str,
        role: str,
        hook: str | None = None,
        task_type: str | None = None,
    ) -> PromptFragment | None:
        """
        Resolve a fragment using the hierarchical search path.

        Search path (winning rule - first match wins):
        1. Role-specific: prompts/roles/{role}/{fragment_id}.md
        2. Shared: prompts/shared/{layer}/{fragment_id}.md

        Args:
            layer: Layer type to resolve
            role: Agent role ID
            hook: Lifecycle hook (for lifecycle layer)
            task_type: Task type (for task_type layer)

        Returns:
            PromptFragment if found, None otherwise
        """
        fragment_id = self._resolve_fragment_id(layer, hook, task_type)

        # Try role-specific first, then shared
        if self.repository.fragment_exists(fragment_id, role=role):
            return self.repository.get_fragment(fragment_id, role=role)
        elif self.repository.fragment_exists(fragment_id, role=None):
            return self.repository.get_fragment(fragment_id, role=None)

        return None

    def _verify_hash(self, fragment: PromptFragment) -> None:
        """
        Verify fragment integrity before use.

        Args:
            fragment: Fragment to verify

        Raises:
            HashMismatchError: If content hash doesn't match
        """
        if not fragment.verify_integrity():
            actual_hash = PromptFragment.compute_hash(fragment.content)
            raise HashMismatchError(
                fragment_id=fragment.fragment_id,
                expected=fragment.sha256_hash,
                actual=actual_hash,
            )

    def _compose(self, fragments: list[PromptFragment], role: str, hook: str) -> AssembledPrompt:
        """
        Compose fragments into final assembled prompt.

        Args:
            fragments: Ordered list of verified fragments
            role: Agent role ID
            hook: Lifecycle hook

        Returns:
            Immutable AssembledPrompt with lineage
        """
        # Concatenate content with double newline separator
        content = "\n\n".join(f.content for f in fragments)

        # Collect lineage (ordered hashes)
        fragment_hashes = tuple(f.sha256_hash for f in fragments)

        # Compute assembly hash
        assembly_hash = AssembledPrompt.compute_assembly_hash(content)

        # Get version from manifest
        manifest = self._get_manifest()

        return AssembledPrompt(
            content=content,
            fragment_hashes=fragment_hashes,
            assembly_hash=assembly_hash,
            role=role,
            hook=hook,
            version=manifest.version,
        )

    def assemble(
        self,
        role: str,
        hook: str,
        task_type: str | None = None,
        recovery: bool = False,
    ) -> AssembledPrompt:
        """
        Assemble a prompt for the given context.

        Implements the deterministic layer ordering from SIP-0057:
        1. Identity Layer: Agent role identity, tone constraints, boundaries
        2. Global Constraints: Safety, non-leakage, ACI immutability
        3. Lifecycle Layer: Hook-specific instructions (e.g., agent_start)
        4. Task Type Layer: Behavioral instructions for ACI task_type
        5. Recovery Layer: (Conditional) For failure analysis/recovery

        Args:
            role: Agent role ID (e.g., "lead", "dev", "qa")
            hook: Lifecycle hook (e.g., "agent_start", "task_complete")
            task_type: Optional ACI task type (e.g., "code_generate")
            recovery: Whether to include recovery layer

        Returns:
            AssembledPrompt with content and lineage

        Raises:
            MandatoryLayerMissingError: If required layers cannot be resolved
            HashMismatchError: If any fragment fails integrity check
        """
        fragments: list[PromptFragment] = []

        for layer in self.LAYER_ORDER:
            # Skip recovery layer unless requested
            if layer == "recovery" and not recovery:
                continue

            # Skip task_type layer if no task_type provided
            if layer == "task_type" and not task_type:
                continue

            # Resolve fragment for this layer
            fragment = self._resolve_fragment(layer, role, hook, task_type)

            if fragment:
                # Verify integrity before adding
                self._verify_hash(fragment)
                fragments.append(fragment)
            elif layer in self.MANDATORY_LAYERS:
                # Mandatory layers must exist
                raise MandatoryLayerMissingError(layer=layer, role=role)
            # Optional layers (lifecycle, task_type, recovery) can be missing

        return self._compose(fragments, role, hook)

    def get_system_prompt(self, role: str) -> AssembledPrompt:
        """
        Get assembled system prompt for agent initialization.

        Convenience method that assembles the prompt for the
        agent_start hook with no task type or recovery.

        Args:
            role: Agent role ID

        Returns:
            AssembledPrompt for system initialization
        """
        return self.assemble(role=role, hook="agent_start")

    def get_version(self) -> str:
        """
        Get the current prompt system version.

        Returns:
            Version string from the active manifest
        """
        return self._get_manifest().version
