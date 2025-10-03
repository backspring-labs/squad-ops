#!/usr/bin/env python3
"""
Script to update all agent files to use generic role-based classes
"""

import os
import re
from pathlib import Path

def update_agent_file(file_path: str, role_name: str, class_name: str):
    """Update an agent file to use generic role-based structure"""
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Update class name
    old_class_pattern = rf'class\s+\w+Agent\s*\(BaseAgent\):'
    new_class = f'class {class_name}(BaseAgent):'
    content = re.sub(old_class_pattern, new_class, content)
    
    # Update __init__ method to accept identity parameter
    init_pattern = r'def __init__\(self\):'
    init_replacement = 'def __init__(self, identity: str):'
    content = re.sub(init_pattern, init_replacement, content)
    
    # Update super().__init__ call
    super_pattern = r'super\(\)\.__init__\(\s*name="[^"]+",'
    super_replacement = 'super().__init__(\n            name=identity,'
    content = re.sub(super_pattern, super_replacement, content)
    
    # Update main function
    main_pattern = r'async def main\(\):\s*\n\s*"""Main entry point for [^"]+ agent"""\s*\n\s*agent = \w+Agent\(\)\s*\n\s*await agent\.run\(\)'
    main_replacement = f'''async def main():
    """Main entry point for {role_name.title()} agent"""
    import os
    identity = os.getenv('AGENT_ID', '{role_name}_agent')
    agent = {class_name}(identity=identity)
    await agent.run()'''
    content = re.sub(main_pattern, main_replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    # Update docstring
    docstring_pattern = r'"""[^"]+ - [^"]+ Agent[^"]*"""'
    docstring_replacement = f'"""{role_name.title()} Agent - {role_name.title()} Role"""'
    content = re.sub(docstring_pattern, docstring_replacement, content)
    
    # Write updated content
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Updated {file_path}")

def main():
    """Update all agent files"""
    
    roles = {
        'audit': 'AuditAgent',
        'comms': 'CommsAgent', 
        'creative': 'CreativeAgent',
        'curator': 'CuratorAgent',
        'data': 'DataAgent',
        'dev': 'DevAgent',
        'finance': 'FinanceAgent',
        'qa': 'QAAgent',
        'strat': 'StratAgent'
    }
    
    for role, class_name in roles.items():
        file_path = f"agents/roles/{role}/agent.py"
        if os.path.exists(file_path):
            update_agent_file(file_path, role, class_name)
        else:
            print(f"❌ File not found: {file_path}")

if __name__ == "__main__":
    main()
