"""SquadOps - Multi-agent orchestration framework.

A hexagonal architecture (ports & adapters) framework for
orchestrating AI agent squads in software development workflows.
``docs/architecture/overview.md`` maps every package.

#1985: this package root imports nothing but the version. It used to re-export the agents, the
bootstrap and the task models, so importing any ``squadops`` module, even a leaf, loaded about 144
of them and hid the real dependency graph. Import from the module that defines a name.
"""

from squadops._version import resolve_version as _resolve_version

__version__ = _resolve_version()
