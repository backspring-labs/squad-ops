"""Execution sandbox domain (SIP-0102 — Ephemeral Application Sandbox).

#2062: the package re-exports nothing (#1985's rule). It re-exported the no-op sandbox and the
service, which import ``squadops.ports.sandbox``; the port imports ``squadops.sandbox.models``, which
runs this root first. So a process whose first import was the port failed on a partially initialized
module. Import from the module that defines a name.
"""
