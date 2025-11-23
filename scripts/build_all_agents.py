#!/usr/bin/env python3
"""Build all agent packages"""
from pathlib import Path
import sys
from scripts.build_agent import build_agent_package

roles = ['qa', 'lead', 'dev', 'strat', 'data', 'finance', 'comms', 'curator', 'creative', 'audit', 'devops']

def main():
    base_path = Path.cwd()
    failed = []
    
    for role in roles:
        print(f"\n{'='*60}")
        print(f"Building {role}...")
        print(f"{'='*60}")
        try:
            build_agent_package(role, base_path)
        except Exception as e:
            print(f"❌ Failed to build {role}: {e}")
            failed.append(role)
    
    print(f"\n{'='*60}")
    if failed:
        print(f"❌ Failed roles: {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"✅ All {len(roles)} agent packages built successfully")
        sys.exit(0)

if __name__ == "__main__":
    main()

