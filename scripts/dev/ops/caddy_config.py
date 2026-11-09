#!/usr/bin/env python3
"""#2960: Caddy runs the checkout's Caddyfile.

Caddy mounts ``console/Caddyfile`` as a single file. A ``git pull`` replaces that file rather
than writing into it, so the running container keeps reading the old one, and ``caddy reload``
re-reads the old one and reports success. The deploy compares the file Caddy reads with the
checkout's, and restarts Caddy when they differ.

Exit 0 when Caddy reads the checkout's file (after a restart if one was needed), 1 otherwise.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from pathlib import Path

CONTAINER = "squadops-caddy"
MOUNTED = "/etc/caddy/Caddyfile"
CHECKOUT = Path(__file__).resolve().parents[3] / "console" / "Caddyfile"
READABLE_WITHIN_S = 30.0

MATCH, DIFFERS, UNREADABLE = "match", "differs", "unreadable"


def digest(content: bytes | None) -> str:
    return "unreadable" if content is None else hashlib.sha256(content).hexdigest()[:12]


def compare(checkout: bytes, running: bytes | None) -> str:
    """Whether Caddy reads the checkout's file. An unreadable file is never taken as a match."""
    if running is None:
        return UNREADABLE
    return MATCH if running == checkout else DIFFERS


def running_caddyfile() -> bytes | None:
    """The Caddyfile the container reads, or None when it can't be read (Caddy isn't running)."""
    proc = subprocess.run(
        ["docker", "exec", CONTAINER, "cat", MOUNTED], capture_output=True, timeout=30
    )
    return proc.stdout if proc.returncode == 0 else None


def restart_caddy() -> bool:
    proc = subprocess.run(["docker", "restart", CONTAINER], capture_output=True, timeout=120)
    return proc.returncode == 0


def ensure(
    checkout: bytes, *, read=running_caddyfile, restart=restart_caddy, sleep=time.sleep
) -> int:
    running = read()
    state = compare(checkout, running)
    print(f"   Caddyfile: checkout {digest(checkout)}, Caddy reads {digest(running)}")
    if state == MATCH:
        print("   Caddy runs the checkout's Caddyfile")
        return 0
    if state == UNREADABLE:
        print(f"   Caddy's Caddyfile can't be read: is {CONTAINER} running?", file=sys.stderr)
        return 1
    print("   Caddy reads an older Caddyfile: restarting it (a reload would re-read the old file)")
    if not restart():
        print(f"   docker restart {CONTAINER} failed", file=sys.stderr)
        return 1
    deadline = time.monotonic() + READABLE_WITHIN_S
    running = read()
    while running is None and time.monotonic() < deadline:
        sleep(1.0)
        running = read()
    state = compare(checkout, running)
    print(f"   after the restart, Caddy reads {digest(running)}")
    if state != MATCH:
        print("   Caddy still doesn't read the checkout's Caddyfile", file=sys.stderr)
        return 1
    print("   Caddy runs the checkout's Caddyfile")
    return 0


def main() -> int:
    return ensure(CHECKOUT.read_bytes())


if __name__ == "__main__":
    sys.exit(main())
