"""ProposalFailure — structured failure record from a proposer handler (SIP-0093 RC-23).

When a role proposer fails (LLM error, retry-budget exhaustion, malformed YAML
that survives retries, brief-id mismatch), the handler emits a structured
failure record into the cycle artifact stream rather than raising an exception
that kills the cycle. The merger (PR 93.3) reads these records as "this
role's proposal is missing" and produces a `MissingProposal` entry in
`merge_decisions.yaml` accordingly.

This is distinct from `merge_decisions.MissingProposal`:

- ``ProposalFailure`` is what the *proposer* emits when it fails.
- ``MissingProposal`` is what the *merger* records about missing proposals
  in its audit artifact. The merger constructs `MissingProposal` entries
  from `ProposalFailure` artifacts it finds in the artifact stream.

The two have a structural overlap (role + failure_reason) but live at
different layers — proposer-side artifact vs merger-side audit record.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

_VALID_FAILURE_REASONS = frozenset(
    {
        "llm_error",
        "timeout",
        "malformed_yaml",
        "mismatched_brief_id",
        "schema_validation_error",
    }
)


@dataclass(frozen=True)
class ProposalFailure:
    """A proposer's structured failure record.

    Attributes:
        proposer_role: role ID of the proposer that failed
            (``development``, ``qa``, ``strategy``, ``builder``).
        failure_reason: bounded tag explaining why the proposal failed.
            One of: ``llm_error`` (transport-level LLM failure),
            ``timeout`` (call exceeded its budget), ``malformed_yaml``
            (retry budget exhausted on bad YAML), ``mismatched_brief_id``
            (parsed proposal cites a brief other than the upstream one),
            ``schema_validation_error`` (parsed but failed parser
            invariants — e.g., RC-24 integer-in-depends_on_focus).
        details: free-form diagnostic text for operators — typically the
            last error message from the retry loop or the validation
            failure description.
    """

    proposer_role: str
    failure_reason: str
    details: str = ""

    def to_yaml(self) -> str:
        """Emit the failure record as a YAML document the merger can parse."""
        return yaml.safe_dump(
            {
                "proposer_role": self.proposer_role,
                "failure_reason": self.failure_reason,
                "details": self.details,
            },
            sort_keys=False,
        )

    @classmethod
    def from_yaml(cls, content: str) -> ProposalFailure:
        """Parse a ``proposed_plan_tasks_failure.yaml`` document.

        Raises:
            ValueError: malformed YAML, missing required fields, or
                unknown ``failure_reason``.
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed ProposalFailure YAML: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("ProposalFailure must be a YAML mapping at the top level")

        for key in ("proposer_role", "failure_reason"):
            if key not in data:
                raise ValueError(f"ProposalFailure missing required field: {key}")

        proposer_role = str(data["proposer_role"]).strip()
        if not proposer_role:
            raise ValueError("ProposalFailure proposer_role must be non-empty")

        failure_reason = str(data["failure_reason"]).strip()
        if failure_reason not in _VALID_FAILURE_REASONS:
            raise ValueError(
                f"ProposalFailure failure_reason must be one of "
                f"{sorted(_VALID_FAILURE_REASONS)}, got {failure_reason!r}"
            )

        return cls(
            proposer_role=proposer_role,
            failure_reason=failure_reason,
            details=str(data.get("details", "")).strip(),
        )
