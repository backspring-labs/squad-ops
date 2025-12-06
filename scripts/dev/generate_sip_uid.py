#!/usr/bin/env python3
"""
ULID Generation Utility for SIPs
Generates ULIDs for new or existing SIPs.
"""

import sys

try:
    import ulid
except ImportError:
    print("Error: ulid library not installed. Install with: pip install ulid-py")
    sys.exit(1)


def generate_ulid() -> str:
    """Generate a new ULID."""
    return str(ulid.new())


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
        for _ in range(count):
            print(generate_ulid())
    else:
        print(generate_ulid())


if __name__ == "__main__":
    main()

