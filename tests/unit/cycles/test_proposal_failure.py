"""Tests for ``ProposalFailure`` (SIP-0093 PR 93.2 RC-23 record)."""

from __future__ import annotations

import pytest

from squadops.cycles.proposal_failure import ProposalFailure

pytestmark = [pytest.mark.domain_orchestration]


class TestRoundTrip:
    """The merger (PR 93.3) reads ProposalFailure artifacts from the cycle
    stream. The to_yaml → from_yaml round-trip must preserve the three
    fields the merger cares about — proposer_role, failure_reason,
    details — so the merger's MissingProposal construction has its
    inputs intact."""

    def test_round_trip_preserves_fields(self):
        original = ProposalFailure(
            proposer_role="qa",
            failure_reason="malformed_yaml",
            details="retry budget exhausted after 2 attempts",
        )
        parsed = ProposalFailure.from_yaml(original.to_yaml())
        assert parsed == original

    def test_round_trip_with_empty_details(self):
        original = ProposalFailure(
            proposer_role="strategy",
            failure_reason="timeout",
        )
        parsed = ProposalFailure.from_yaml(original.to_yaml())
        assert parsed == original
        assert parsed.details == ""


class TestParserErrors:
    @pytest.mark.parametrize(
        "missing_field",
        ["proposer_role", "failure_reason"],
    )
    def test_missing_required_field_rejected(self, missing_field):
        full = {
            "proposer_role": "development",
            "failure_reason": "llm_error",
        }
        full.pop(missing_field)
        yaml_doc = "\n".join(f"{k}: {v}" for k, v in full.items()) + "\n"
        with pytest.raises(ValueError, match=missing_field):
            ProposalFailure.from_yaml(yaml_doc)

    def test_empty_proposer_role_rejected(self):
        with pytest.raises(ValueError, match="proposer_role"):
            ProposalFailure.from_yaml('proposer_role: ""\nfailure_reason: llm_error\n')

    @pytest.mark.parametrize(
        "bad_reason",
        ["unknown", "BAD_REASON", "user_quit", "manual_override"],
    )
    def test_unknown_failure_reason_rejected(self, bad_reason):
        yaml_doc = f"proposer_role: development\nfailure_reason: {bad_reason}\n"
        with pytest.raises(ValueError, match="failure_reason"):
            ProposalFailure.from_yaml(yaml_doc)

    def test_malformed_yaml_rejected(self):
        with pytest.raises(ValueError, match="Malformed"):
            ProposalFailure.from_yaml("proposer_role: [unclosed")

    def test_non_mapping_rejected(self):
        with pytest.raises(ValueError, match="mapping"):
            ProposalFailure.from_yaml("- just\n- a\n- list\n")

    @pytest.mark.parametrize(
        "valid_reason",
        [
            "llm_error",
            "timeout",
            "malformed_yaml",
            "mismatched_brief_id",
            "schema_validation_error",
        ],
    )
    def test_every_valid_reason_parses(self, valid_reason):
        """Each bounded reason must round-trip cleanly. Tracks the
        vocabulary against accidental shrinkage in the parser."""
        yaml_doc = f"proposer_role: development\nfailure_reason: {valid_reason}\ndetails: ok\n"
        parsed = ProposalFailure.from_yaml(yaml_doc)
        assert parsed.failure_reason == valid_reason
