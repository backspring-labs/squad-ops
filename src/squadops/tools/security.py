"""Path security policy for tool operations.

Shared path validation for all tool ports (SIP §7.2).
Part of SIP-0.8.7 Infrastructure Ports Migration.
"""

from pathlib import Path


class PathSecurityError(Exception):
    """Raised when path validation fails."""

    pass


class PathSecurityPolicy:
    """Shared path validation for all tool ports.

    Validates that paths are:
    1. Absolute (no implicit cwd resolution)
    2. No '..' segments (path traversal prevention)
    3. Under allowed roots after symlink resolution
    """

    def __init__(self, allowed_roots: tuple[Path, ...]):
        """Initialize with allowed root directories.

        Args:
            allowed_roots: Tuple of allowed root paths. Must be explicitly configured.

        Raises:
            ValueError: If allowed_roots is empty
        """
        # REQUIRED: Must be explicitly configured, no default cwd
        if not allowed_roots:
            raise ValueError("allowed_roots must be explicitly configured")
        # Resolve roots once at construction (normalize for comparison)
        self._allowed_roots = tuple(root.resolve() for root in allowed_roots)

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        """Get the allowed root directories."""
        return self._allowed_roots

    def validate(self, path: Path) -> Path:
        """Validate and resolve path.

        Args:
            path: Path to validate (must be absolute)

        Returns:
            Resolved path (symlinks followed)

        Raises:
            PathSecurityError: If validation fails
        """
        # Rule 0: Input MUST be absolute (no implicit cwd resolution)
        if not path.is_absolute():
            raise PathSecurityError(f"Path must be absolute, got relative: {path}")

        # Rule 1: No '..' segments in original path (before resolution)
        if ".." in path.parts:
            raise PathSecurityError(f"Path traversal not allowed: {path}")

        # Rule 2: Resolve symlinks for security check
        resolved = path.resolve()

        # Rule 3: Must be under allowed roots (symlinks resolved first)
        if not any(self._is_under(resolved, root) for root in self._allowed_roots):
            raise PathSecurityError(f"Path outside allowed roots: {path}")

        return resolved

    def _is_under(self, path: Path, root: Path) -> bool:
        """Check if path is under root.

        Both must be resolved absolute paths.

        Args:
            path: Path to check
            root: Root to check against

        Returns:
            True if path is under root
        """
        # Use relative_to which raises ValueError if not relative
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
