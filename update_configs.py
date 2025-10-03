#!/usr/bin/env python3
"""
Script to update all config files to remove hardcoded identity names
"""

import os
import re

def update_config_file(file_path: str, role_name: str):
    """Update a config file to remove hardcoded identity names"""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Update header comment
    header_pattern = r'# [^#\n]+ Agent Configuration'
    header_replacement = f'# {role_name.title()} Role Configuration'
    content = re.sub(header_pattern, header_replacement, content)
    
    # Update description comment
    desc_pattern = r'# [^#\n]+ Agent'
    desc_replacement = f'# {role_name.title()} Role'
    content = re.sub(desc_pattern, desc_replacement, content)
    
    # Remove AGENT_NAME line
    content = re.sub(r'AGENT_NAME = "[^"]+"\n', '', content)
    
    # Add ROLE_TYPE if not present
    if 'ROLE_TYPE' not in content:
        content = content.replace('AGENT_TYPE = ', f'ROLE_TYPE = "{role_name}"\nAGENT_TYPE = ')
    
    # Write updated content
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated {file_path}")

def main():
    """Update all config files"""
    
    roles = ['audit', 'comms', 'creative', 'curator', 'data', 'dev', 'finance', 'qa', 'strat']
    
    for role in roles:
        file_path = f"agents/roles/{role}/config.py"
        if os.path.exists(file_path):
            update_config_file(file_path, role)
        else:
            print(f"❌ File not found: {file_path}")

if __name__ == "__main__":
    main()
