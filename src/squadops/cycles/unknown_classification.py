"""
Unknown classification constants for planning workloads (SIP-0078 §5.7).

Each unknown identified during planning is classified into one of five levels.
The classification drives whether planning can proceed, requires human input,
or must block until the unknown is resolved.
"""


class UnknownClassification:
    """Unknown classification level constants.

    Constants class (not enum) — matches WorkloadType / ArtifactType pattern.

    Levels (ascending severity):
        RESOLVED           — answered during planning; no action needed.
        PROTO_VALIDATED     — feasibility confirmed by prototype; acceptable.
        ACCEPTABLE_RISK     — team acknowledges risk; proceed with mitigation.
        REQUIRES_HUMAN_DECISION — needs human input before implementation.
        BLOCKER             — must be resolved before implementation can start.
    """

    RESOLVED = "resolved"
    PROTO_VALIDATED = "proto_validated"
    ACCEPTABLE_RISK = "acceptable_risk"
    REQUIRES_HUMAN_DECISION = "requires_human_decision"
    BLOCKER = "blocker"
