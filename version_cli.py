#!/usr/bin/env python3
"""
SquadOps Version Management CLI
Manages agent versions, configurations, and rollbacks
"""

import sys
import json
from datetime import datetime
from config.version import (
    AGENT_VERSIONS, CONFIG_VERSIONS, VERSION_HISTORY,
    get_agent_version, get_agent_config, update_agent_version,
    get_version_history, rollback_agent
)

def list_agents():
    """List all agents and their current versions"""
    print("🤖 SquadOps Agent Versions")
    print("=" * 50)
    for agent, version in AGENT_VERSIONS.items():
        config = CONFIG_VERSIONS.get(agent, {})
        print(f"{agent.upper():<8} | v{version:<8} | {config.get('llm', 'unknown'):<20} | {config.get('config', 'unknown')}")
    print()

def show_agent_details(agent_name):
    """Show detailed information for a specific agent"""
    agent_key = agent_name.lower()
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
    """Update agent version"""
    update_agent_version(agent_name, new_version, llm, config, notes)
    print(f"✅ Updated {agent_name} to version {new_version}")
    if llm:
        print(f"   LLM: {llm}")
    if config:
        print(f"   Config: {config}")
    if notes:
        print(f"   Notes: {notes}")

def rollback_to_version(agent_name, target_version):
    """Rollback agent to a previous version"""
    success = rollback_agent(agent_name, target_version)
    if success:
        print(f"✅ Rolled back {agent_name} to version {target_version}")
    else:
        print(f"❌ Failed to rollback {agent_name} to version {target_version}")
        print("   Version not found in history")

def export_versions():
    """Export current version configuration"""
    config = {
        "framework_version": "1.0.0",
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
        with open(filename, "r") as f:
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
        print("Usage:")
        print("  python version_cli.py list                    # List all agents")
        print("  python version_cli.py show <agent>            # Show agent details")
        print("  python version_cli.py update <agent> <version> [llm] [config] [notes]")
        print("  python version_cli.py rollback <agent> <version>")
        print("  python version_cli.py export                  # Export config")
        print("  python version_cli.py import <file>           # Import config")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
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
