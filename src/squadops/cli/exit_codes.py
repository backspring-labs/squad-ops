"""
CLI exit code constants (SIP-0065 §6.6).

Standard shell conventions with application-specific codes in the 10+ range.
"""

SUCCESS = 0
GENERAL_ERROR = 1
# 2 = usage/syntax error (Typer handles this automatically)
VALIDATION_ERROR = 10   # API 422
AUTH_ERROR = 11          # API 401/403
NOT_FOUND = 12           # API 404
CONFLICT = 13            # API 409
NETWORK_ERROR = 20       # Unreachable/timeout
