"""
Cycle execution domain (SIP-0064).

Domain models, enums, exceptions, and lifecycle logic for Projects, Cycles,
Runs, Squad Profiles, Task Flow Policy, and Artifact Vault integration.

#1985: the package re-exports nothing, so importing one of its modules loads that module and what
it imports, not the whole domain. Import from the module that defines a name.
"""
