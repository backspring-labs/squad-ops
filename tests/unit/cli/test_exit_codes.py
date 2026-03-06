"""
Unit tests for CLI exit code constants (SIP-0065 §6.6).
"""

from squadops.cli import exit_codes


class TestExitCodes:
    """Exit code constants match SIP-0065 §6.6."""

    def test_all_codes_unique(self):
        codes = [
            exit_codes.SUCCESS,
            exit_codes.GENERAL_ERROR,
            exit_codes.VALIDATION_ERROR,
            exit_codes.AUTH_ERROR,
            exit_codes.NOT_FOUND,
            exit_codes.CONFLICT,
            exit_codes.NETWORK_ERROR,
        ]
        assert len(codes) == len(set(codes))
