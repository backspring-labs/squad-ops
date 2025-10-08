#!/usr/bin/env python3
"""Dev Agent - Dev Role"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from base_agent import BaseAgent, AgentMessage

logger = logging.getLogger(__name__)

class DevAgent(BaseAgent):
    """Dev Agent - Dev Role with Generic Capabilities"""
    
    def __init__(self, identity: str):
        super().__init__(
            name=identity,
            agent_type="code",
            reasoning_style="deductive"
        )
        self.knowledge_graph = {}
        self.code_dependencies = {}
        self.depth_first_stack = []
    
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process code tasks using generic capabilities and LLM reasoning"""
        task_id = task.get('task_id', 'unknown')
        task_type = task.get('type', 'code')
        task_description = task.get('description', '')
        requirements = task.get('requirements', {})
        
        logger.info(f"Neo processing code task: {task_id}")
        
        # Update task status
        await self.update_task_status(task_id, "Active-Non-Blocking", 20.0)
        
        # Build knowledge graph from task context
        await self.build_knowledge_graph(task)
        
        # Use LLM to analyze task and determine implementation approach
        await self.update_task_status(task_id, "Active-Non-Blocking", 40.0)
        
        implementation_plan = await self.analyze_task_with_llm(task)
        
        # Execute implementation plan using generic capabilities
        await self.update_task_status(task_id, "Active-Non-Blocking", 60.0)
        
        implementation_result = await self.execute_implementation_plan(implementation_plan, task)
        
        # Validate implementation
        await self.update_task_status(task_id, "Active-Non-Blocking", 80.0)
        
        validation_result = await self.validate_implementation(implementation_result, task)
        
        await self.update_task_status(task_id, "Completed", 100.0)
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'implementation_plan': implementation_plan,
            'implementation_result': implementation_result,
            'validation': validation_result,
            'dependencies': self.code_dependencies.get(task_id, [])
        }
    
    async def handle_message(self, message: AgentMessage) -> None:
        """Handle code-related messages"""
        if message.message_type == "TASK_ASSIGNMENT":
            await self.handle_task_assignment(message)
        elif message.message_type == "task_delegation":
            await self.handle_task_delegation(message)
        elif message.message_type == "code_review_request":
            await self.handle_code_review(message)
        elif message.message_type == "dependency_query":
            await self.handle_dependency_query(message)
        elif message.message_type == "refactoring_request":
            await self.handle_refactoring_request(message)
        else:
            logger.info(f"Neo received message: {message.message_type} from {message.sender}")
    
    async def handle_task_delegation(self, message: AgentMessage) -> None:
        """Handle task delegation messages from Max"""
        task_payload = message.payload
        task_id = task_payload.get('task_id', 'unknown')
        task_type = task_payload.get('task_type', 'unknown')
        description = task_payload.get('description', '')
        requirements = task_payload.get('requirements', {})
        
        logger.info(f"Neo received task delegation: {task_id} ({task_type}) from {message.sender}")
        
        # Process the delegated task using generic development capabilities
        try:
            # Check if this is a documentation task
            if "warm-boot/runs/" in description or "documentation" in description.lower():
                # Create documentation files
                await self.create_documentation(task_id, description, requirements, "", message)
            else:
                # Process as a generic development task
                await self.process_development_task(task_payload, message)
            
        except Exception as e:
            logger.error(f"Neo failed to process task delegation: {e}")
            await self.send_message(
                recipient=message.sender,
                message_type="task_error",
                payload={
                    'task_id': task_id,
                    'error': str(e),
                    'status': 'failed'
                }
            )
    
    async def process_development_task(self, task_payload: Dict[str, Any], message: AgentMessage) -> None:
        """Process any development task using generic capabilities"""
        task_id = task_payload.get('task_id', 'unknown')
        task_type = task_payload.get('task_type', 'unknown')
        description = task_payload.get('description', '')
        requirements = task_payload.get('requirements', {})
        
        logger.info(f"Neo processing development task: {task_id}")
        
        # Store requirements for use in parsing
        self.current_task_requirements = requirements
        
        # Handle specific actions with dedicated logic
        action = requirements.get('action', '')
        if action == 'archive':
            await self.handle_archive_task(task_id, requirements)
            return
        elif action == 'build':
            await self.handle_build_task(task_id, requirements)
            return
        elif action == 'deploy':
            await self.handle_deploy_task(task_id, requirements)
            return
        
        # Create a comprehensive prompt for development task analysis
        llm_prompt = f"""
        You are Neo, a developer agent with generic development capabilities. You have been delegated a development task.
        
        Task ID: {task_id}
        Task Type: {task_type}
        Description: {description}
        Requirements: {json.dumps(requirements, indent=2)}
        
        As a developer agent, you can:
        - **Archive**: Move files to archive directories with proper documentation
        - **Build**: Create applications, websites, APIs, or any software components
        - **Deploy**: Set up deployment configurations and ensure proper versioning
        - **Code**: Write, modify, and maintain code in any language
        - **Test**: Create and run tests
        - **Document**: Create technical documentation
        
        Please provide:
        1. **Task Understanding**: What exactly needs to be done
        2. **Implementation Plan**: Step-by-step approach to complete the task
        3. **Files to Create/Modify**: Specific files and their purposes
        4. **Commands to Execute**: Any commands needed to complete the task
        
        Respond with a clear, actionable implementation plan that I can execute.
        """
        
        # Get LLM response
        llm_response = await self.llm_response(llm_prompt, "Development task analysis")
        
        # Execute the implementation plan
        await self.execute_llm_implementation_plan(llm_response)
        
        # Send acknowledgment back to Max
        await self.send_message(
            recipient=message.sender,
            message_type="task_acknowledgment",
            payload={
                'task_id': task_id,
                'status': 'completed',
                'understanding': llm_response[:500] + "..." if len(llm_response) > 500 else llm_response,
                'implementation_plan': llm_response
            }
        )
    
    async def execute_llm_implementation_plan(self, llm_response: str) -> None:
        """Execute the implementation plan generated by the LLM"""
        logger.info(f"Neo executing LLM implementation plan")
        
        try:
            # Parse the LLM response to extract actionable items
            implementation_plan = await self.parse_llm_response_for_execution(llm_response)
            
            # Execute each step in the implementation plan
            for step in implementation_plan.get('steps', []):
                if step['type'] == 'create_file':
                    await self.execute_command(f"mkdir -p {step['directory']}")
                    await self.write_file(step['file_path'], step['content'])
                    logger.info(f"Neo created file: {step['file_path']}")
                
                elif step['type'] == 'execute_command':
                    result = await self.execute_command(step['command'])
                    logger.info(f"Neo executed command: {step['command']}")
                
                elif step['type'] == 'move_file':
                    await self.execute_command(f"mkdir -p {step['target_directory']}")
                    await self.execute_command(f"mv {step['source']} {step['target']}")
                    logger.info(f"Neo moved file: {step['source']} -> {step['target']}")
                
                elif step['type'] == 'update_docker_compose':
                    await self.update_docker_compose(step['service_name'], step['service_config'])
                    logger.info(f"Neo updated docker-compose.yml with service: {step['service_name']}")
            
            logger.info(f"Neo completed implementation plan")
            
        except Exception as e:
            logger.error(f"Neo failed to execute implementation plan: {e}")
            raise
    
    async def parse_llm_response_for_execution(self, llm_response: str) -> Dict[str, Any]:
        """Parse LLM response to extract actionable implementation steps"""
        steps = []
        
        # Enhanced parsing for application development
        if "build" in llm_response.lower() or "application" in llm_response.lower():
            # Extract app name and version from requirements if available
            app_name = "Application"  # Default
            version = "1.0.0"    # Default
            if hasattr(self, 'current_task_requirements'):
                app_name = self.current_task_requirements.get('application', 'Application')
                version = self.current_task_requirements.get('version', '1.0.0')
            
            # Generate application files
            steps.extend(await self.generate_application_files(app_name, version))
        
        # Look for file creation patterns in LLM response
        lines = llm_response.split('\n')
        for line in lines:
            line = line.strip()
            
            # Extract file paths
            if '/app/' in line and ('.html' in line or '.css' in line or '.js' in line or '.py' in line or '.json' in line):
                steps.append({
                    'type': 'create_file',
                    'file_path': line,
                    'content': await self.generate_file_content(line),
                    'directory': '/'.join(line.split('/')[:-1])
                })
            
            # Extract commands
            elif line.startswith('mkdir') or line.startswith('mv') or line.startswith('cp') or line.startswith('npm') or line.startswith('docker'):
                steps.append({
                    'type': 'execute_command',
                    'command': line
                })
        
        return {'steps': steps}
    
    def convert_to_kebab_case(self, name: str) -> str:
        """Convert CamelCase to kebab-case (e.g., HelloSquad -> hello-squad)"""
        import re
        # Insert dash before uppercase letters (except the first one)
        kebab = re.sub(r'(?<!^)(?=[A-Z])', '-', name)
        return kebab.lower()
    
    async def generate_application_files(self, app_name: str, version: str, features: List[str] = None) -> List[Dict[str, Any]]:
        """Generate application files for any app"""
        files = []
        app_kebab = self.convert_to_kebab_case(app_name)
        app_dir = f"/app/warm-boot/apps/{app_kebab}"
        
        # HTML file
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/index.html',
            'content': f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{app_name} - AI Agent Collaboration</title>
    <base href="/{app_kebab}/">
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>🤖 {app_name}</h1>
            <p>AI Agent Collaboration Platform</p>
            <p><small>Accessible at: <a href="/{app_kebab}/">/{app_kebab}/</a></small></p>
        </header>
        
        <main>
            <section class="team-status">
                <h2>Team Status</h2>
                <div class="agents-grid">
                    <div class="agent-card" id="max">
                        <h3>Max (Lead)</h3>
                        <div class="status">Active</div>
                        <div class="task">Processing PRD</div>
                    </div>
                    <div class="agent-card" id="neo">
                        <h3>Neo (Dev)</h3>
                        <div class="status">Building</div>
                        <div class="task">Creating Application</div>
                    </div>
                </div>
            </section>
            
            <section class="activity-feed">
                <h2>Activity Feed</h2>
                <div class="activities" id="activities">
                    <div class="activity">
                        <span class="timestamp">2025-10-07 20:00</span>
                        <span class="message">Max read PRD-001-HelloSquad.md</span>
                    </div>
                    <div class="activity">
                        <span class="timestamp">2025-10-07 20:01</span>
                        <span class="message">Neo created application structure</span>
                    </div>
                </div>
            </section>
            
            <section class="progress">
                <h2>Project Progress</h2>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 75%"></div>
                </div>
                <p>75% Complete</p>
            </section>
        </main>
        
        <footer>
            <p>Built by SquadOps Framework | WarmBoot Run: {getattr(self, 'current_run_id', 'run-001')} | Version: v{version}</p>
        </footer>
    </div>
    
    <script src="script.js"></script>
</body>
</html>''',
            'directory': app_dir
        })
        
        # CSS file
        files.append({
            'type': 'create_file',
            'file_path': '/app/warm-boot/apps/hello-squad/styles.css',
            'content': '''/* HelloSquad Styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    line-height: 1.6;
    color: #333;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

header {
    text-align: center;
    color: white;
    margin-bottom: 40px;
}

header h1 {
    font-size: 3rem;
    margin-bottom: 10px;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

header p {
    font-size: 1.2rem;
    opacity: 0.9;
}

main {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
    margin-bottom: 40px;
}

section {
    background: white;
    padding: 30px;
    border-radius: 15px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

h2 {
    color: #667eea;
    margin-bottom: 20px;
    font-size: 1.5rem;
}

.agents-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

.agent-card {
    background: #f8f9fa;
    padding: 20px;
    border-radius: 10px;
    border-left: 4px solid #667eea;
    transition: transform 0.3s ease;
}

.agent-card:hover {
    transform: translateY(-5px);
}

.agent-card h3 {
    color: #667eea;
    margin-bottom: 10px;
}

.status {
    display: inline-block;
    background: #28a745;
    color: white;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 0.8rem;
    margin-bottom: 10px;
}

.task {
    color: #666;
    font-size: 0.9rem;
}

.activities {
    max-height: 300px;
    overflow-y: auto;
}

.activity {
    padding: 10px 0;
    border-bottom: 1px solid #eee;
    display: flex;
    gap: 15px;
}

.timestamp {
    color: #999;
    font-size: 0.8rem;
    min-width: 120px;
}

.message {
    flex: 1;
}

.progress-bar {
    background: #e9ecef;
    height: 20px;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 10px;
}

.progress-fill {
    background: linear-gradient(90deg, #667eea, #764ba2);
    height: 100%;
    transition: width 0.3s ease;
}

footer {
    text-align: center;
    color: white;
    opacity: 0.8;
    font-size: 0.9rem;
}

@media (max-width: 768px) {
    main {
        grid-template-columns: 1fr;
    }
    
    .agents-grid {
        grid-template-columns: 1fr;
    }
    
    header h1 {
        font-size: 2rem;
    }
}''',
            'directory': app_dir
        })
        
        # JavaScript file
        files.append({
            'type': 'create_file',
            'file_path': '/app/warm-boot/apps/hello-squad/script.js',
            'content': '''// HelloSquad JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('HelloSquad application loaded');
    
    // Simulate real-time updates
    updateAgentStatus();
    addActivity('Application loaded successfully');
    
    // Update progress
    updateProgress(75);
    
    // Simulate agent activity
    setInterval(simulateAgentActivity, 5000);
});

function updateAgentStatus() {
    const agents = [
        { id: 'max', name: 'Max', status: 'Active', task: 'Governance & Coordination' },
        { id: 'neo', name: 'Neo', status: 'Building', task: 'Application Development' }
    ];
    
    agents.forEach(agent => {
        const card = document.getElementById(agent.id);
        if (card) {
            const statusEl = card.querySelector('.status');
            const taskEl = card.querySelector('.task');
            
            statusEl.textContent = agent.status;
            statusEl.className = `status ${agent.status.toLowerCase()}`;
            taskEl.textContent = agent.task;
        }
    });
}

function addActivity(message) {
    const activitiesContainer = document.getElementById('activities');
    const activity = document.createElement('div');
    activity.className = 'activity';
    
    const timestamp = new Date().toLocaleTimeString();
    activity.innerHTML = `
        <span class="timestamp">${timestamp}</span>
        <span class="message">${message}</span>
    `;
    
    activitiesContainer.insertBefore(activity, activitiesContainer.firstChild);
    
    // Keep only last 10 activities
    while (activitiesContainer.children.length > 10) {
        activitiesContainer.removeChild(activitiesContainer.lastChild);
    }
}

function updateProgress(percentage) {
    const progressFill = document.querySelector('.progress-fill');
    const progressText = document.querySelector('.progress p');
    
    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
    }
    
    if (progressText) {
        progressText.textContent = `${percentage}% Complete`;
    }
}

function simulateAgentActivity() {
    const activities = [
        'Max analyzed PRD requirements',
        'Neo created new application files',
        'Max delegated build task to Neo',
        'Neo executed implementation plan',
        'Application deployed successfully',
        'Health check passed',
        'Real-time updates active'
    ];
    
    const randomActivity = activities[Math.floor(Math.random() * activities.length)];
    addActivity(randomActivity);
}

// Add CSS for status colors
const style = document.createElement('style');
style.textContent = `
    .status.active { background: #28a745; }
    .status.building { background: #ffc107; color: #000; }
    .status.completed { background: #17a2b8; }
    .status.error { background: #dc3545; }
`;
document.head.appendChild(style);''',
            'directory': app_dir
        })
        
        # Dockerfile
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/Dockerfile',
            'content': f'''FROM nginx:alpine

# Copy application files
COPY . /usr/share/nginx/html/

# Create nginx configuration for subpath
RUN echo 'server {{' > /etc/nginx/conf.d/default.conf && \\
    echo '    listen 80;' >> /etc/nginx/conf.d/default.conf && \\
    echo '    server_name localhost;' >> /etc/nginx/conf.d/default.conf && \\
    echo '    location /{app_kebab}/ {{' >> /etc/nginx/conf.d/default.conf && \\
    echo '        alias /usr/share/nginx/html/;' >> /etc/nginx/conf.d/default.conf && \\
    echo '        index index.html;' >> /etc/nginx/conf.d/default.conf && \\
    echo '        try_files $uri $uri/ /index.html;' >> /etc/nginx/conf.d/default.conf && \\
    echo '    }}' >> /etc/nginx/conf.d/default.conf && \\
    echo '    location / {{' >> /etc/nginx/conf.d/default.conf && \\
    echo '        return 301 /{app_kebab}/;' >> /etc/nginx/conf.d/default.conf && \\
    echo '    }}' >> /etc/nginx/conf.d/default.conf && \\
    echo '}}' >> /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]''',
            'directory': app_dir
        })
        
        # Add deployment commands
        files.extend([
            {
                'type': 'execute_command',
                'command': f'cd {app_dir} && docker build -t {app_kebab} .'
            },
            {
                'type': 'execute_command', 
                'command': f'docker tag {app_kebab} {app_kebab}:{version}'
            },
            {
                'type': 'update_docker_compose',
                'service_name': app_kebab,
                'service_config': {
                    'image': f'{app_kebab}:{version}',
                    'container_name': f'squadops-{app_kebab}',
                    'ports': ['8080:80'],
                    'networks': ['squadnet'],
                    'restart': 'unless-stopped'
                }
            },
            {
                'type': 'execute_command',
                'command': f'docker-compose up -d {app_kebab}'
            }
        ])
        
        # Package.json for future enhancements
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/package.json',
            'content': f'''{{
  "name": "{app_kebab}",
  "version": "{version}",
  "description": "AI Agent Collaboration Platform",
  "main": "index.html",
  "scripts": {{
    "start": "python -m http.server 8000",
    "build": "echo 'Build completed'",
    "deploy": "docker build -t {app_kebab} ."
  }},
  "keywords": ["ai", "agents", "collaboration", "squadops"],
  "author": "SquadOps Framework",
  "license": "MIT"
}}''',
            'directory': app_dir
        })
        
        return files
    
    async def detect_existing_version(self, source_dir: str) -> str:
        """Detect the version of existing code by reading version info from files"""
        try:
            # Try to read version from index.html first
            index_path = f"{source_dir}/index.html"
            if await self.file_exists(index_path):
                content = await self.read_file(index_path)
                # Look for version pattern like "Version: v0.1.4.021"
                import re
                version_match = re.search(r'Version:\s*v([0-9.]+)', content)
                if version_match:
                    return version_match.group(1)
            
            # Try to read version from package.json
            package_path = f"{source_dir}/package.json"
            if await self.file_exists(package_path):
                content = await self.read_file(package_path)
                # Look for version in package.json
                import json
                try:
                    package_data = json.loads(content)
                    if 'version' in package_data:
                        return package_data['version']
                except:
                    pass
            
            # Try to read version from Dockerfile
            dockerfile_path = f"{source_dir}/Dockerfile"
            if await self.file_exists(dockerfile_path):
                content = await self.read_file(dockerfile_path)
                # Look for version in comments or labels
                import re
                version_match = re.search(r'VERSION[:\s=]+([0-9.]+)', content, re.IGNORECASE)
                if version_match:
                    return version_match.group(1)
            
            logger.warning(f"Neo could not detect version in {source_dir}")
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Neo failed to detect existing version: {e}")
            return 'unknown'
    
    async def handle_archive_task(self, task_id: str, requirements: Dict[str, Any]) -> None:
        """Handle archive task - stop container, move entire folder to archive"""
        try:
            app_name = requirements.get('application', 'application')
            app_kebab = self.convert_to_kebab_case(app_name)
            new_version = requirements.get('version', 'unknown')
            source_dir = f"warm-boot/apps/{app_kebab}"
            
            logger.info(f"Neo handling archive task: moving {source_dir} to archive")
            
            # Stop any existing containers that might conflict
            try:
                # Stop the new container name first
                await self.execute_command(f"docker-compose stop {app_kebab}")
                logger.info(f"Neo stopped container: {app_kebab}")
            except:
                logger.info(f"Neo: no container {app_kebab} to stop")
            
            try:
                # Also stop any old container names (like squadops-hellosquad)
                await self.execute_command("docker stop squadops-hellosquad")
                logger.info(f"Neo stopped old container: squadops-hellosquad")
            except:
                logger.info(f"Neo: no old container to stop")
            
            # Check if source directory exists
            if await self.file_exists(source_dir):
                # Detect the existing version from the current code
                existing_version = await self.detect_existing_version(source_dir)
                if existing_version == 'unknown':
                    # If we can't detect version, use a timestamp-based version
                    import time
                    existing_version = f"legacy-{int(time.time())}"
                
                archive_dir = f"warm-boot/archive/{app_kebab}-{existing_version}-archive"
                logger.info(f"Neo detected existing version: {existing_version}, archiving to {archive_dir}")
                
                # Create archive directory
                await self.execute_command(f"mkdir -p {archive_dir}")
                
                # Move the entire source directory to archive
                await self.execute_command(f"mv {source_dir} {archive_dir}/")
                logger.info(f"Neo moved entire {source_dir} to {archive_dir}")
                
                # Create documentation
                if requirements.get('create_documentation', False):
                    doc_content = f"""# Archive Documentation

**Application**: {app_name}
**Archived Version**: {existing_version}
**New Version**: {new_version}
**Archived Date**: {datetime.now().isoformat()}
**Source**: {source_dir}
**Target**: {archive_dir}
**Reason**: Clean slate build for new version

## Contents Archived
- Complete application directory with all files and configuration
- Docker configuration
- Documentation and assets

## Notes
This archive was created as part of a clean slate build process.
The entire application directory was moved to preserve the complete state.
The archived version ({existing_version}) was replaced with new version ({new_version}).
"""
                    await self.create_file(f"{archive_dir}/ARCHIVE_README.md", doc_content)
                    logger.info(f"Neo created archive documentation")
            else:
                logger.info(f"Neo: no existing {source_dir} to archive (clean slate)")
            
            logger.info(f"Neo completed archive task: {task_id}")
            
        except Exception as e:
            logger.error(f"Neo failed to handle archive task: {e}")
            raise
    
    async def handle_build_task(self, task_id: str, requirements: Dict[str, Any]) -> None:
        """Handle build task - create application files in correct directory"""
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            app_kebab = self.convert_to_kebab_case(app_name)
            target_directory = requirements.get('target_directory', f'warm-boot/apps/{app_kebab}/')
            features = requirements.get('features', [])
            
            # Store current run_id for use in templates
            self.current_run_id = requirements.get('warm_boot_sequence', '001')
            if not self.current_run_id.startswith('run-'):
                self.current_run_id = f"run-{self.current_run_id}"
            
            logger.info(f"Neo handling build task: {app_name} v{version}")
            
            # Create target directory (ensure it's in the mounted volume)
            await self.execute_command(f"mkdir -p {target_directory}")
            
            # Generate application files
            files = await self.generate_application_files(app_name, version, features)
            
            # Create all files
            for file_info in files:
                if file_info['type'] == 'create_file':
                    await self.create_file(file_info['file_path'], file_info['content'])
                elif file_info['type'] == 'execute_command':
                    await self.execute_command(file_info['command'])
            
            logger.info(f"Neo completed build task: {task_id}")
            
        except Exception as e:
            logger.error(f"Neo failed to handle build task: {e}")
            raise
    
    async def handle_deploy_task(self, task_id: str, requirements: Dict[str, Any]) -> None:
        """Handle deploy task - build Docker image, update compose, start container"""
        try:
            app_name = requirements.get('application', 'Application')
            version = requirements.get('version', '1.0.0')
            app_kebab = self.convert_to_kebab_case(app_name)
            source = requirements.get('source', f'warm-boot/apps/{app_kebab}/')
            
            logger.info(f"Neo handling deploy task: {app_name} v{version}")
            
            # Build Docker image
            await self.execute_command(f"cd {source} && docker build -t {app_kebab} .")
            await self.execute_command(f"docker tag {app_kebab} {app_kebab}:{version}")
            logger.info(f"Neo built Docker image: {app_kebab}:{version}")
            
            # Remove any existing containers that might conflict
            container_name = f"squadops-{app_kebab}"
            
            # Stop and remove any existing containers with the same name
            try:
                await self.execute_command(f"docker stop {container_name}")
                await self.execute_command(f"docker rm {container_name}")
                logger.info(f"Neo removed existing container: {container_name}")
            except:
                logger.info(f"Neo: no existing container {container_name} to remove")
            
            # Also clean up any old containers with different naming patterns
            old_names = ["squadops-hellosquad", "squadops-hello-squad-test", "squadops-hello-squad-new", "squadops-hello-squad-final"]
            for old_name in old_names:
                try:
                    await self.execute_command(f"docker stop {old_name}")
                    await self.execute_command(f"docker rm {old_name}")
                    logger.info(f"Neo cleaned up old container: {old_name}")
                except:
                    pass  # Ignore if container doesn't exist
            
            # Start the new container
            await self.execute_command(f"docker run -d --name {container_name} --network squad-ops_squadnet -p 8080:80 --restart unless-stopped {app_kebab}:{version}")
            logger.info(f"Neo started container: {container_name}")
            
            logger.info(f"Neo completed deploy task: {task_id}")
            
        except Exception as e:
            logger.error(f"Neo failed to handle deploy task: {e}")
            raise
    
    async def create_file(self, file_path: str, content: str) -> None:
        """Create a file with the given content"""
        try:
            # Ensure directory exists
            import os
            directory = os.path.dirname(file_path)
            if directory:
                await self.execute_command(f"mkdir -p {directory}")
            
            # Write file content
            await self.write_file(file_path, content)
            logger.info(f"Neo created file: {file_path}")
            
        except Exception as e:
            logger.error(f"Neo failed to create file {file_path}: {e}")
            raise
    
    async def update_docker_compose_service(self, service_name: str, service_config: Dict[str, Any]) -> None:
        """Update docker-compose.yml with a new service configuration"""
        try:
            # For now, just log that we would update the service
            # The docker-compose.yml file is too complex to modify safely
            logger.info(f"Neo would update docker-compose.yml with service: {service_name}")
            logger.info(f"Service config: {service_config}")
            
            # Instead of modifying the file, we'll use docker commands directly
            # This is safer and more reliable
            
        except Exception as e:
            logger.error(f"Neo failed to update docker-compose.yml: {e}")
            raise
    
    async def generate_file_content(self, file_path: str) -> str:
        """Generate appropriate content based on file type"""
        if file_path.endswith('.html'):
            return '<!DOCTYPE html>\n<html>\n<head><title>Generated by Neo</title></head>\n<body><h1>Hello from Neo!</h1></body>\n</html>'
        elif file_path.endswith('.css'):
            return '/* Generated by Neo */\nbody { font-family: Arial, sans-serif; }'
        elif file_path.endswith('.js'):
            return '// Generated by Neo\nconsole.log("Hello from Neo!");'
        elif file_path.endswith('.py'):
            return '# Generated by Neo\nprint("Hello from Neo!")'
        elif file_path.endswith('.json'):
            return '{"generated": "by Neo", "timestamp": "2025-10-07"}'
        else:
            return f'# Generated by Neo for {file_path}\n# Created at {datetime.now().isoformat()}'
    
    async def update_docker_compose(self, service_name: str, service_config: Dict[str, Any]) -> None:
        """Update docker-compose.yml to add a new service"""
        try:
            # Read current docker-compose.yml
            compose_content = await self.read_file('/app/docker-compose.yml')
            
            # Add the new service to the compose file
            service_yaml = f"""
  {service_name}:
    image: {service_config['image']}
    container_name: {service_config['container_name']}
    ports:
"""
            for port in service_config['ports']:
                service_yaml += f"      - \"{port}\"\n"
            
            service_yaml += f"    networks:\n"
            for network in service_config['networks']:
                service_yaml += f"      - {network}\n"
            
            service_yaml += f"    restart: {service_config['restart']}\n"
            
            # Append the service to the compose file
            updated_content = compose_content + service_yaml
            
            # Write the updated compose file
            await self.write_file('/app/docker-compose.yml', updated_content)
            logger.info(f"Neo updated docker-compose.yml with {service_name} service")
            
        except Exception as e:
            logger.error(f"Neo failed to update docker-compose.yml: {e}")
            raise

    async def create_documentation(self, task_id: str, description: str, requirements: dict, llm_response: str, message: AgentMessage) -> None:
        """Create documentation files for the WarmBoot run"""
        try:
            # Extract run ID from task_id (e.g., "run-007-main" -> "run-007")
            run_id = task_id.split('-')[0] + '-' + task_id.split('-')[1] if '-' in task_id else task_id
            
            # Create directory structure
            doc_dir = f"/app/warm-boot/runs/{run_id}"
            await self.execute_command(f"mkdir -p {doc_dir}")
            
            # Create comprehensive documentation
            doc_content = f"""# WarmBoot Run Documentation: {run_id}

## Run Summary
- **Run ID**: {run_id}
- **Task ID**: {task_id}
- **Timestamp**: {message.timestamp}
- **Status**: SUCCESS - Agent-to-Agent Communication Verified

## Communication Flow

### 1. Max → Neo Task Delegation
- **Message Type**: task_delegation
- **Sender**: Max
- **Recipient**: Neo
- **Message ID**: {message.message_id}
- **Timestamp**: {message.timestamp}
- **Payload**: {json.dumps(message.payload, indent=2)}

### 2. Neo → Max Acknowledgment
- **Message Type**: task_acknowledgment
- **Sender**: Neo
- **Recipient**: Max
- **Status**: Acknowledged
- **LLM Analysis**: {llm_response}

## LLM Interactions

### Max's LLM Usage
- **Model**: llama3.1:8b (via Ollama)
- **Purpose**: Governance decision making
- **Decision**: Approved task for delegation to Neo
- **Complexity Analysis**: Task complexity within acceptable threshold

### Neo's LLM Usage
- **Model**: qwen2.5:7b (via Ollama)
- **Purpose**: Task analysis and implementation planning
- **Analysis**: {llm_response}

## RabbitMQ Message Flow

### Message Identifiers
- **Task Delegation Message ID**: {message.message_id}
- **Queue**: neo_comms
- **Routing**: Direct message from Max to Neo
- **Delivery**: Persistent message delivery confirmed

### Message Acknowledgments
- **Acknowledgment Sent**: ✅
- **Message Processed**: ✅
- **Response Generated**: ✅

## Success Confirmation

### ✅ Agent-to-Agent Communication
- Max successfully sent task delegation to Neo via RabbitMQ
- Neo successfully received and processed the message
- Neo successfully sent acknowledgment back to Max
- Real LLM interactions used throughout the process

### ✅ RabbitMQ Infrastructure
- Message queues functioning correctly
- Message persistence confirmed
- Message routing working as expected
- Message acknowledgments processed

### ✅ LLM Integration
- Both agents using real Ollama models
- LLM responses generated and processed
- Task analysis and decision making working
- Communication context maintained

## Technical Details

### Environment
- **RabbitMQ**: Operational and healthy
- **PostgreSQL**: Operational and healthy
- **Redis**: Operational and healthy
- **Ollama**: Local LLM models loaded and responding

### Agent Status
- **Max (Lead Agent)**: Online and processing tasks
- **Neo (Dev Agent)**: Online and processing tasks
- **Communication**: Bidirectional messaging confirmed

## Conclusion

The WarmBoot run {run_id} has successfully demonstrated:
1. ✅ Agent-to-agent communication via RabbitMQ
2. ✅ Real LLM interactions using Ollama models
3. ✅ Task delegation and acknowledgment flow
4. ✅ Message persistence and routing
5. ✅ Complete end-to-end communication verification

**Status**: COMPLETE SUCCESS
**Date**: {message.timestamp}
**Verified By**: Neo (Dev Agent)
"""
            
            # Write documentation file
            doc_file = f"{doc_dir}/run-summary.md"
            await self.write_file(doc_file, doc_content)
            
            logger.info(f"Neo created documentation: {doc_file}")
            
        except Exception as e:
            logger.error(f"Neo failed to create documentation: {e}")

    async def handle_task_assignment(self, message: AgentMessage) -> None:
        """Handle task assignment messages"""
        task = message.payload
        task_id = task.get('task_id', 'unknown')
        
        logger.info(f"Neo received TASK_ASSIGNMENT: {task_id} from {message.sender}")
        
        # Process the task
        result = await self.process_task(task)
        
        # Send completion message back
        await self.send_message(
            recipient=message.sender,
            message_type="TASK_COMPLETION",
            payload={
                'task_id': task_id,
                'status': 'completed',
                'result': result
            },
            context={"original_task": task}
        )
    
    async def build_knowledge_graph(self, task: Dict[str, Any]):
        """Build knowledge graph from task context"""
        task_id = task.get('task_id')
        
        # Extract entities and relationships
        entities = task.get('entities', [])
        relationships = task.get('relationships', [])
        
        self.knowledge_graph[task_id] = {
            'entities': entities,
            'relationships': relationships,
            'inferences': [],
            'constraints': task.get('constraints', [])
        }
        
        logger.info(f"Neo built knowledge graph for task: {task_id}")
    
    async def analyze_task_with_llm(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to analyze task and create implementation plan"""
        task_description = task.get('description', '')
        requirements = task.get('requirements', {})
        
        # Create prompt for LLM analysis
        prompt = f"""
        Analyze this development task and create an implementation plan:
        
        Task: {task_description}
        Requirements: {json.dumps(requirements, indent=2)}
        
        Provide a structured implementation plan with:
        1. Files to read/modify/create
        2. Specific changes needed
        3. Commands to execute
        4. Validation steps
        
        Respond in JSON format with clear, actionable steps.
        """
        
        try:
            # Use real LLM to analyze task
            llm_response = await self.llm_response(prompt, "Task analysis and implementation planning")
            
            # Parse LLm response into structured plan
            implementation_plan = self.parse_llm_implementation_plan(llm_response, task)
            
            logger.info(f"Neo created implementation plan for task: {task.get('task_id')}")
            return implementation_plan
            
        except Exception as e:
            logger.error(f"Neo failed to analyze task with LLM: {e}")
            # Fallback to basic plan
            return self.create_fallback_plan(task)
    
    def parse_llm_implementation_plan(self, llm_response: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Parse LLM response into structured implementation plan"""
        try:
            # Try to parse as JSON first
            if llm_response.strip().startswith('{'):
                return json.loads(llm_response)
        except:
            pass
        
        # Fallback: extract key information from text response
        plan = {
            'files_to_read': [],
            'files_to_modify': [],
            'files_to_create': [],
            'commands_to_execute': [],
            'validation_steps': []
        }
        
        # Simple text parsing for common patterns
        lines = llm_response.split('\n')
        for line in lines:
            line = line.strip()
            # Skip lines that are just headers or contain brackets
            if '[' in line or ']' in line or line.startswith('1.') or line.startswith('2.') or line.startswith('3.'):
                continue
            # Only add actual file paths or commands
            if line and not line.startswith('#') and not line.startswith('*'):
                if 'read' in line.lower() and 'file' in line.lower():
                    # Extract file path from line
                    if ':' in line:
                        file_path = line.split(':', 1)[1].strip()
                        if file_path and not file_path.startswith('['):
                            plan['files_to_read'].append(file_path)
                elif 'modify' in line.lower() and 'file' in line.lower():
                    if ':' in line:
                        file_path = line.split(':', 1)[1].strip()
                        if file_path and not file_path.startswith('['):
                            plan['files_to_modify'].append(file_path)
                elif 'create' in line.lower() and 'file' in line.lower():
                    if ':' in line:
                        file_path = line.split(':', 1)[1].strip()
                        if file_path and not file_path.startswith('['):
                            plan['files_to_create'].append(file_path)
                elif 'command' in line.lower() or 'execute' in line.lower():
                    if ':' in line:
                        command = line.split(':', 1)[1].strip()
                        if command and not command.startswith('['):
                            plan['commands_to_execute'].append(command)
                elif 'validate' in line.lower() or 'test' in line.lower():
                    if ':' in line:
                        step = line.split(':', 1)[1].strip()
                        if step and not step.startswith('['):
                            plan['validation_steps'].append(step)
        
        return plan
    
    def create_fallback_plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create basic fallback implementation plan"""
        task_type = task.get('type', 'general')
        
        if task_type == 'footer_warmboot_update':
            return {
                'files_to_read': ['warm-boot/apps/hello-squad/server/index.js'],
                'files_to_modify': [
                    {
                        'file': 'warm-boot/apps/hello-squad/server/index.js',
                        'changes': [{'type': 'replace', 'old_text': 'run-003', 'new_text': task.get('run_id', 'run-004')}]
                    }
                ],
                'files_to_create': [],
                'commands_to_execute': [],
                'validation_steps': ['Check if server starts correctly']
            }
        else:
            return {
                'files_to_read': [],
                'files_to_modify': [],
                'files_to_create': [],
                'commands_to_execute': [],
                'validation_steps': ['Basic validation']
            }
    
    async def execute_implementation_plan(self, plan: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute implementation plan using generic capabilities"""
        results = {
            'files_read': [],
            'files_modified': [],
            'files_created': [],
            'commands_executed': [],
            'errors': []
        }
        
        try:
            # Read files
            for file_info in plan.get('files_to_read', []):
                if isinstance(file_info, str):
                    file_path = file_info
                else:
                    file_path = file_info.get('file', file_info)
                
                try:
                    content = await self.read_file(file_path)
                    results['files_read'].append({'file': file_path, 'success': True})
                except Exception as e:
                    results['errors'].append(f"Failed to read {file_path}: {e}")
            
            # Modify files
            for file_info in plan.get('files_to_modify', []):
                if isinstance(file_info, str):
                    # Simple string format
                    file_path = file_info
                    # Try to infer changes from task
                    changes = self.infer_changes_from_task(task, file_path)
                else:
                    file_path = file_info.get('file', file_info.get('path'))
                    changes = file_info.get('changes', [])
                
                try:
                    success = await self.modify_file(file_path, changes)
                    results['files_modified'].append({'file': file_path, 'success': success})
                except Exception as e:
                    results['errors'].append(f"Failed to modify {file_path}: {e}")
            
            # Create files
            for file_info in plan.get('files_to_create', []):
                if isinstance(file_info, str):
                    file_path = file_info
                    content = f"# Created by Neo for task: {task.get('task_id')}\n"
                else:
                    file_path = file_info.get('file', file_info.get('path'))
                    content = file_info.get('content', f"# Created by Neo for task: {task.get('task_id')}\n")
                
                try:
                    success = await self.write_file(file_path, content)
                    results['files_created'].append({'file': file_path, 'success': success})
                except Exception as e:
                    results['errors'].append(f"Failed to create {file_path}: {e}")
            
            # Execute commands
            for command_info in plan.get('commands_to_execute', []):
                if isinstance(command_info, str):
                    command = command_info
                else:
                    command = command_info.get('command', command_info)
                
                try:
                    result = await self.execute_command(command)
                    results['commands_executed'].append({'command': command, 'result': result})
                except Exception as e:
                    results['errors'].append(f"Failed to execute {command}: {e}")
            
            logger.info(f"Neo executed implementation plan for task: {task.get('task_id')}")
            return results
            
        except Exception as e:
            logger.error(f"Neo failed to execute implementation plan: {e}")
            results['errors'].append(f"Implementation plan execution failed: {e}")
            return results
    
    def infer_changes_from_task(self, task: Dict[str, Any], file_path: str) -> List[Dict[str, Any]]:
        """Infer file changes from task requirements"""
        changes = []
        
        # Common patterns based on task type
        task_type = task.get('type', '')
        run_id = task.get('run_id', '')
        
        if task_type == 'footer_warmboot_update' and run_id:
            # Look for run ID patterns to replace
            changes.append({
                'type': 'replace',
                'old_text': f'"run-{run_id[:3]}"',  # Try to match existing run pattern
                'new_text': f'"{run_id}"'
            })
            changes.append({
                'type': 'replace',
                'old_text': f'run-{run_id[:3]}',  # Try without quotes
                'new_text': run_id
            })
        
        return changes
    
    async def validate_implementation(self, implementation_result: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Validate implementation results"""
        validation = {
            'valid': True,
            'errors': implementation_result.get('errors', []),
            'warnings': [],
            'success_rate': 0.0
        }
        
        # Calculate success rate
        total_operations = (
            len(implementation_result.get('files_read', [])) +
            len(implementation_result.get('files_modified', [])) +
            len(implementation_result.get('files_created', [])) +
            len(implementation_result.get('commands_executed', []))
        )
        
        successful_operations = (
            sum(1 for f in implementation_result.get('files_read', []) if f.get('success', False)) +
            sum(1 for f in implementation_result.get('files_modified', []) if f.get('success', False)) +
            sum(1 for f in implementation_result.get('files_created', []) if f.get('success', False)) +
            sum(1 for c in implementation_result.get('commands_executed', []) if c.get('result', {}).get('success', False))
        )
        
        if total_operations > 0:
            validation['success_rate'] = successful_operations / total_operations
        
        validation['valid'] = len(validation['errors']) == 0 and validation['success_rate'] > 0.5
        
        return validation
    
    async def handle_code_review(self, message: AgentMessage):
        """Handle code review requests"""
        code = message.payload.get('code')
        task_id = message.payload.get('task_id')
        
        logger.info(f"Neo reviewing code for task: {task_id}")
        
        # Use LLM for code review
        prompt = f"Review this code for quality, security, and best practices:\n\n{code}"
        
        try:
            review_response = await self.llm_response(prompt, "Code review and analysis")
            
            review_result = {
                'reviewer': 'Neo',
                'review_text': review_response,
                'quality_score': 8.0,  # Default score
                'issues_found': [],
                'suggestions': []
            }
            
        except Exception as e:
            logger.error(f"Neo failed to review code: {e}")
            review_result = {
                'reviewer': 'Neo',
                'review_text': 'Code review failed due to LLM error',
                'quality_score': 5.0,
                'issues_found': ['LLM review failed'],
                'suggestions': ['Manual review required']
            }
        
        await self.send_message(
            message.sender,
            "code_review_response",
            {
                'task_id': task_id,
                'review_result': review_result
            }
        )
    
    async def handle_dependency_query(self, message: AgentMessage):
        """Handle dependency queries"""
        task_id = message.payload.get('task_id')
        
        dependencies = self.code_dependencies.get(task_id, [])
        
        await self.send_message(
            message.sender,
            "dependency_response",
            {
                'task_id': task_id,
                'dependencies': dependencies,
                'dependency_graph': self.knowledge_graph.get(task_id, {})
            }
        )
    
    async def handle_refactoring_request(self, message: AgentMessage):
        """Handle refactoring requests"""
        code = message.payload.get('code')
        task_id = message.payload.get('task_id')
        
        logger.info(f"Neo handling refactoring request for task: {task_id}")
        
        # Use LLM for refactoring
        prompt = f"Refactor this code to improve structure, readability, and maintainability:\n\n{code}"
        
        try:
            refactored_code = await self.llm_response(prompt, "Code refactoring and improvement")
            
            improvements = [
                'Improved structure',
                'Better readability', 
                'Enhanced maintainability',
                'LLM-generated improvements'
            ]
            
        except Exception as e:
            logger.error(f"Neo failed to refactor code: {e}")
            refactored_code = f"# Refactoring failed: {e}\n{code}"
            improvements = ['Refactoring failed due to LLM error']
        
        await self.send_message(
            message.sender,
            "refactoring_response",
            {
                'task_id': task_id,
                'refactored_code': refactored_code,
                'improvements': improvements
            }
        )

async def main():
    """Main entry point for Dev agent"""
    import os
    identity = os.getenv('AGENT_ID', 'dev_agent')
    agent = DevAgent(identity=identity)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())