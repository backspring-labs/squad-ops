"""Project Lifecycle Management (SIP-0112): the Project Record and its lifecycle.

The registry's read model stays ``squadops.cycles.models.Project``. This package holds the
record's parts and the decisions the lifecycle makes about them, and imports nothing from the
cycle domain, which reads it.
"""
