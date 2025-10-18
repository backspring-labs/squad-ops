"""
Contract definitions for SquadOps agent communication.

Defines structured data contracts for task specifications, build manifests,
and other inter-agent communication protocols.
"""

from .task_spec import TaskSpec
from .build_manifest import BuildManifest, FileSpec

__all__ = ['TaskSpec', 'BuildManifest', 'FileSpec']


