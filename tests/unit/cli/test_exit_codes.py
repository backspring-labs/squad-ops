"""
Unit tests for CLI exit code constants (SIP-0065 §6.6).
"""

from squadops.cli import exit_codes


class TestExitCodes:
    """Exit code constants match SIP-0065 §6.6."""

    def test_success(self):
        assert exit_codes.SUCCESS == 0

    def test_general_error(self):
        assert exit_codes.GENERAL_ERROR == 1

    def test_validation_error(self):
        assert exit_codes.VALIDATION_ERROR == 10

    def test_auth_error(self):
        assert exit_codes.AUTH_ERROR == 11

    def test_not_found(self):
        assert exit_codes.NOT_FOUND == 12

    def test_conflict(self):
        assert exit_codes.CONFLICT == 13

    def test_network_error(self):
        assert exit_codes.NETWORK_ERROR == 20

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
