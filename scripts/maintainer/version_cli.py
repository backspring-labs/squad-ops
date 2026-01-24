#!/usr/bin/env python3
"""
SquadOps Version Management CLI
Manages framework and agent versions, configurations, and rollbacks
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Add repo root to Python path
script_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(script_dir))
sys.path.insert(0, str(script_dir / "_v0_legacy"))

from config.version import (
    AGENT_VERSIONS,
    CONFIG_VERSIONS,
    get_agent_config,
    get_agent_version,
    get_framework_version,
    get_version_history,
    rollback_agent,
)


def show_framework_version():
    """Show current framework version"""
    print(f"🚀 SquadOps Framework Version: {get_framework_version()}")
    print()

def list_agents():
    """List all agents and their current versions"""
    print(f"🚀 SquadOps Framework v{get_framework_version()}")
    print()
    print("🤖 Agent Versions")
    print("=" * 50)
    for agent, version in AGENT_VERSIONS.items():
        config = CONFIG_VERSIONS.get(agent, {})
        print(f"{agent.upper():<8} | v{version:<8} | {config.get('llm', 'unknown'):<20} | {config.get('config', 'unknown')}")
    print()

def show_agent_details(agent_name):
    """Show detailed information for a specific agent"""
    version = get_agent_version(agent_name)
    config = get_agent_config(agent_name)
    history = get_version_history(agent_name)
    
    print(f"🤖 {agent_name.upper()} Agent Details")
    print("=" * 50)
    print(f"Current Version: {version}")
    print(f"LLM Model: {config.get('llm', 'unknown')}")
    print(f"Configuration: {config.get('config', 'unknown')}")
    print()
    
    print("📋 Version History:")
    for entry in reversed(history[-5:]):  # Show last 5 versions
        print(f"  v{entry['version']:<8} | {entry['date']:<12} | {entry['llm']:<20} | {entry['notes']}")
    print()

def update_version(agent_name, new_version, llm=None, config=None, notes=""):
    """Update agent version in config/version.py"""
    version_file = Path("_v0_legacy/config/version.py")
    
    if not version_file.exists():
        print("❌ config/version.py not found")
        return False
    
    # Read the file
    content = version_file.read_text()
    agent_key = agent_name.lower()
    
    # Update AGENT_VERSIONS
    pattern = rf'"{agent_key}":\s*"[^"]+"'
    replacement = f'"{agent_key}": "{new_version}"'
    
    if not re.search(pattern, content):
        print(f"❌ Could not find agent '{agent_key}' in AGENT_VERSIONS")
        return False
    
    new_content = re.sub(pattern, replacement, content)
    
    # Update VERSION_HISTORY if notes are provided
    if notes:
        # Find the VERSION_HISTORY section and add new entry
        history_pattern = rf'"{agent_key}":\s*\[\s*(.*?)\s*\]'
        match = re.search(history_pattern, new_content, re.DOTALL)
        
        if match:
            existing_history = match.group(1).strip()
            new_entry = f'{{"version": "{new_version}", "date": "{datetime.now().strftime("%Y-%m-%d")}", "llm": "{llm or "unknown"}", "notes": "{notes}"}}'
            
            # Remove trailing comma if present to avoid double comma
            if existing_history and existing_history.endswith(','):
                existing_history = existing_history[:-1]
            
            if existing_history:
                # Properly format with newlines and indentation
                updated_history = f'\n        {existing_history},\n        {new_entry}\n    '
            else:
                updated_history = f'\n        {new_entry}\n    '
            
            new_content = re.sub(history_pattern, f'"{agent_key}": [{updated_history}]', new_content, flags=re.DOTALL)
        else:
            # Add new history entry if agent not in VERSION_HISTORY yet
            history_end_pattern = r'(VERSION_HISTORY = \{.*?)(\n\})'
            new_entry = f'    "{agent_key}": [\n        {{"version": "{new_version}", "date": "{datetime.now().strftime("%Y-%m-%d")}", "llm": "{llm or "unknown"}", "notes": "{notes}"}}\n    ],\n'
            new_content = re.sub(history_end_pattern, rf'\1\n{new_entry}\2', new_content, flags=re.DOTALL)
    
    # Write back
    version_file.write_text(new_content)
    
    print(f"✅ Updated {agent_name} to version {new_version}")
    if llm:
        print(f"   LLM: {llm}")
    if config:
        print(f"   Config: {config}")
    if notes:
        print(f"   Notes: {notes}")
    print("   Updated: config/version.py")
    print()
    print("⚠️  Remember to commit this change:")
    print('   git add config/version.py')
    print(f'   git commit -m "chore: bump {agent_name} to {new_version}"')
    
    return True

def rollback_to_version(agent_name, target_version):
    """Rollback agent to a previous version"""
    success = rollback_agent(agent_name, target_version)
    if success:
        print(f"✅ Rolled back {agent_name} to version {target_version}")
    else:
        print(f"❌ Failed to rollback {agent_name} to version {target_version}")
        print("   Version not found in history")

def update_framework_version(new_version, notes=""):
    """Update the framework version in config/version.py"""
    version_file = Path("_v0_legacy/config/version.py")
    
    if not version_file.exists():
        print("❌ config/version.py not found")
        return False
    
    # Read the file
    content = version_file.read_text()
    
    # Update SQUADOPS_VERSION
    pattern = r'SQUADOPS_VERSION = "[^"]+"'
    replacement = f'SQUADOPS_VERSION = "{new_version}"'
    
    if not re.search(pattern, content):
        print("❌ Could not find SQUADOPS_VERSION in config/version.py")
        return False
    
    new_content = re.sub(pattern, replacement, content)
    
    # Update the status comment
    status_pattern = r'# Current status: .*'
    status_replacement = f'# Current status: {new_version} ({notes})' if notes else f'# Current status: {new_version}'
    new_content = re.sub(status_pattern, status_replacement, new_content)
    
    # Write back
    version_file.write_text(new_content)
    
    print(f"✅ Updated framework version to {new_version}")
    if notes:
        print(f"   Notes: {notes}")
    print("   Updated: config/version.py")
    print()
    print("⚠️  Remember to commit this change:")
    print('   git add config/version.py')
    print(f'   git commit -m "chore: bump version to {new_version}"')
    
    return True

def export_versions():
    """Export current version configuration"""
    config = {
        "framework_version": get_framework_version(),
        "agent_versions": AGENT_VERSIONS,
        "config_versions": CONFIG_VERSIONS,
        "export_date": datetime.now().isoformat()
    }
    
    with open("version_config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print("✅ Exported version configuration to version_config.json")

def import_versions(filename):
    """Import version configuration from file"""
    try:
        with open(filename) as f:
            config = json.load(f)
        
        # Update global variables
        AGENT_VERSIONS.update(config.get("agent_versions", {}))
        CONFIG_VERSIONS.update(config.get("config_versions", {}))
        
        print(f"✅ Imported version configuration from {filename}")
    except FileNotFoundError:
        print(f"❌ File {filename} not found")
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in {filename}")

def main():
    if len(sys.argv) < 2:
        print("SquadOps Version Management CLI")
        print()
        print("Framework Version Commands:")
        print("  python scripts/maintainer/version_cli.py version                       # Show framework version")
        print("  python scripts/maintainer/version_cli.py bump <version> [notes]        # Update framework version")
        print()
        print("Agent Version Commands:")
        print("  python scripts/maintainer/version_cli.py list                          # List all agents")
        print("  python scripts/maintainer/version_cli.py show <agent>                  # Show agent details")
        print("  python version_cli.py update <agent> <version> [llm] [config] [notes]")
        print("  python version_cli.py rollback <agent> <version>    # Rollback agent version")
        print()
        print("Export/Import Commands:")
        print("  python version_cli.py export                        # Export config")
        print("  python version_cli.py import <file>                 # Import config")
        return
    
    command = sys.argv[1].lower()
    
    if command == "version":
        show_framework_version()
    
    elif command == "bump":
        if len(sys.argv) < 3:
            print("❌ Usage: bump <version> [notes]")
            print("   Example: python version_cli.py bump 0.3.0 'Multi-agent expansion'")
            return
        version = sys.argv[2]
        notes = sys.argv[3] if len(sys.argv) > 3 else ""
        update_framework_version(version, notes)
    
    elif command == "list":
        list_agents()
    
    elif command == "show":
        if len(sys.argv) < 3:
            print("❌ Please specify agent name")
            return
        show_agent_details(sys.argv[2])
    
    elif command == "update":
        if len(sys.argv) < 4:
            print("❌ Usage: update <agent> <version> [llm] [config] [notes]")
            return
        
        agent = sys.argv[2]
        version = sys.argv[3]
        llm = sys.argv[4] if len(sys.argv) > 4 else None
        config = sys.argv[5] if len(sys.argv) > 5 else None
        notes = sys.argv[6] if len(sys.argv) > 6 else ""
        
        update_version(agent, version, llm, config, notes)
    
    elif command == "rollback":
        if len(sys.argv) < 4:
            print("❌ Usage: rollback <agent> <version>")
            return
        
        agent = sys.argv[2]
        version = sys.argv[3]
        rollback_to_version(agent, version)
    
    elif command == "export":
        export_versions()
    
    elif command == "import":
        if len(sys.argv) < 3:
            print("❌ Please specify filename")
            return
        import_versions(sys.argv[2])
    
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()
