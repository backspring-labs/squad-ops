"""
Capability Contracts domain layer.

This module implements SIP-0.8.6: Declarative task contracts enabling
machine-readable delivery expectations, reference workloads composing
capabilities into DAGs, and deterministic acceptance checks.

#1985: the package re-exports nothing, so importing one of its modules loads that module and what
it imports, not the whole layer. Import from the module that defines a name.
"""
