"""Tests for scripts/dev/ops/lib/derive_binding.sh (#327 Step 4b).

The deploy script derives the host-side LangFuse address from the
`docker compose port` binding instead of hardcoding it. This parsing is
easy to get subtly wrong — the bug classes below are each realistic:

- dual-stack hosts emit TWO lines (IPv4 + IPv6); naive parameter expansion
  over the whole string yields a garbage address (found while writing
  these tests);
- IPv6 wildcard `[::]:3001` must split on the LAST colon and still map to
  loopback;
- an interface-pinned binding must be used as-is, not overridden to
  loopback;
- empty/garbage input must fail (rc 1) so the caller skips loudly rather
  than syncing to a default address.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_HELPER = Path(__file__).resolve().parents[3] / "scripts" / "dev" / "ops" / "derive_binding.sh"


def _derive(binding: str) -> tuple[int, str]:
    """Run derive_binding in a bash subprocess; returns (rc, stdout)."""
    proc = subprocess.run(
        ["bash", "-c", f'source "{_HELPER}" && derive_binding "$1"', "_", binding],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.returncode, proc.stdout.strip()


class TestDeriveBinding:
    @pytest.mark.parametrize(
        ("binding", "expected"),
        [
            # Standard single IPv4 wildcard binding → loopback
            ("0.0.0.0:3001", "127.0.0.1 3001"),
            # IPv6 wildcard: split on the LAST colon, map to loopback —
            # both the compose form ([::]:3001) and the classic docker
            # port form (:::3001)
            ("[::]:3001", "127.0.0.1 3001"),
            (":::3001", "127.0.0.1 3001"),
            # Dual-stack hosts emit both bindings — first line wins,
            # the second must not corrupt the parse
            ("0.0.0.0:3001\n[::]:3001", "127.0.0.1 3001"),
            # Interface-pinned binding is used as-is (never loopback)
            ("192.168.1.50:3001", "192.168.1.50 3001"),
            ("127.0.0.1:9999", "127.0.0.1 9999"),
        ],
    )
    def test_derives_connectable_address(self, binding: str, expected: str) -> None:
        rc, out = _derive(binding)
        assert rc == 0
        assert out == expected

    @pytest.mark.parametrize(
        "binding",
        [
            "",  # service down / port unpublished
            "garbage-no-colon",  # not a binding at all
            "0.0.0.0:",  # missing port
            "0.0.0.0:notaport",  # non-numeric port
        ],
    )
    def test_underivable_input_fails_loudly(self, binding: str) -> None:
        """rc 1 + empty output → the deploy script's skip-LOUDLY branch;
        a silent default address here would recreate the drift #327 fixed."""
        rc, out = _derive(binding)
        assert rc == 1
        assert out == ""
