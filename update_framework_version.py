#!/usr/bin/env python3
"""
SquadOps Framework Version Update Script
Updates the framework version across all files
"""

import os
import re
import sys
from config.version import get_framework_version

def update_dockerfile_version(new_version):
    """Update Dockerfile with new version"""
    dockerfile_path = "warm-boot/apps/hello-squad/Dockerfile"
    if os.path.exists(dockerfile_path):
        with open(dockerfile_path, 'r') as f:
            content = f.read()
        
        # Update ARG SQUADOPS_VERSION
        content = re.sub(
            r'ARG SQUADOPS_VERSION=\d+\.\d+\.\d+',
            f'ARG SQUADOPS_VERSION={new_version}',
            content
        )
        
        with open(dockerfile_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Updated Dockerfile: {dockerfile_path}")

def update_server_version(new_version):
    """Update server index.js with new version"""
    server_path = "warm-boot/apps/hello-squad/server/index.js"
    if os.path.exists(server_path):
        with open(server_path, 'r') as f:
            content = f.read()
        
        # Update default version in API response
        content = re.sub(
            r"framework_version: process\.env\.SQUADOPS_VERSION \|\| '\d+\.\d+\.\d+'",
            f"framework_version: process.env.SQUADOPS_VERSION || '{new_version}'",
            content
        )
        
        with open(server_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Updated server: {server_path}")

def update_config_version(new_version):
    """Update config/version.py with new version"""
    config_path = "config/version.py"
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Update SQUADOPS_VERSION
        content = re.sub(
            r'SQUADOPS_VERSION = "\d+\.\d+\.\d+"',
            f'SQUADOPS_VERSION = "{new_version}"',
            content
        )
        
        with open(config_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Updated config: {config_path}")

def main():
    if len(sys.argv) < 2:
        current_version = get_framework_version()
        print(f"Current SquadOps Framework Version: {current_version}")
        print("Usage: python update_framework_version.py <new_version>")
        print("Example: python update_framework_version.py 0.1.5")
        return
    
    new_version = sys.argv[1]
    
    # Validate version format
    if not re.match(r'^\d+\.\d+\.\d+$', new_version):
        print("❌ Invalid version format. Use semantic versioning (e.g., 0.1.5)")
        return
    
    print(f"🔄 Updating SquadOps Framework from {get_framework_version()} to {new_version}")
    
    # Update all files
    update_config_version(new_version)
    update_dockerfile_version(new_version)
    update_server_version(new_version)
    
    print(f"✅ Framework version updated to {new_version}")
    print("📝 Next steps:")
    print("   1. Commit the changes")
    print("   2. Create Git tag: v{new_version}")
    print("   3. Rebuild Docker images with new version")

if __name__ == "__main__":
    main()
