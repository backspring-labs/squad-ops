#!/usr/bin/env python3
"""
Code Generator Component for Dev Agent
Handles application file generation and template management
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class CodeGenerator:
    """Handles code generation and file creation for applications"""
    
    def __init__(self):
        self.templates = {}
        self.generated_files = {}
    
    def convert_to_kebab_case(self, name: str) -> str:
        """Convert CamelCase to kebab-case (e.g., HelloSquad -> hello-squad)"""
        import re
        # Insert dash before uppercase letters (except the first one)
        kebab = re.sub(r'(?<!^)(?=[A-Z])', '-', name)
        return kebab.lower()
    
    async def generate_application_files(self, app_name: str, version: str, features: List[str] = None, run_id: str = "run-001") -> List[Dict[str, Any]]:
        """Generate complete application files for any app"""
        files = []
        app_kebab = self.convert_to_kebab_case(app_name)
        app_dir = f"/app/warm-boot/apps/{app_kebab}"
        
        # HTML file
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/index.html',
            'content': self._generate_html_content(app_name, app_kebab, version, run_id),
            'directory': app_dir
        })
        
        # CSS file
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/styles.css',
            'content': self._generate_css_content(),
            'directory': app_dir
        })
        
        # JavaScript file
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/script.js',
            'content': self._generate_js_content(),
            'directory': app_dir
        })
        
        # Dockerfile
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/Dockerfile',
            'content': self._generate_dockerfile_content(app_kebab),
            'directory': app_dir
        })
        
        # Package.json
        files.append({
            'type': 'create_file',
            'file_path': f'{app_dir}/package.json',
            'content': self._generate_package_json_content(app_kebab, version),
            'directory': app_dir
        })
        
        logger.info(f"CodeGenerator generated {len(files)} files for {app_name} v{version}")
        return files
    
    def _generate_html_content(self, app_name: str, app_kebab: str, version: str, run_id: str) -> str:
        """Generate HTML content for the application"""
        return f'''<!DOCTYPE html>
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
            <p>Built by SquadOps Framework | WarmBoot Run: {run_id} | Version: v{version}</p>
        </footer>
    </div>
    
    <script src="script.js"></script>
</body>
</html>'''
    
    def _generate_css_content(self) -> str:
        """Generate CSS content for the application"""
        return '''/* Application Styles */
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
}'''
    
    def _generate_js_content(self) -> str:
        """Generate JavaScript content for the application"""
        return '''// Application JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('Application loaded');
    
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
document.head.appendChild(style);'''
    
    def _generate_dockerfile_content(self, app_kebab: str) -> str:
        """Generate Dockerfile content for the application"""
        return f'''FROM nginx:alpine

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
CMD ["nginx", "-g", "daemon off;"]'''
    
    def _generate_package_json_content(self, app_kebab: str, version: str) -> str:
        """Generate package.json content for the application"""
        return f'''{{
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
}}'''
    
    async def generate_custom_files(self, app_name: str, requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate custom files based on specific requirements"""
        files = []
        
        # Add custom file generation logic based on requirements
        if requirements.get('api_endpoints'):
            files.extend(await self._generate_api_files(app_name, requirements['api_endpoints']))
        
        if requirements.get('database_schema'):
            files.extend(await self._generate_database_files(app_name, requirements['database_schema']))
        
        if requirements.get('authentication'):
            files.extend(await self._generate_auth_files(app_name, requirements['authentication']))
        
        return files
    
    async def _generate_api_files(self, app_name: str, endpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate API endpoint files"""
        files = []
        app_kebab = self.convert_to_kebab_case(app_name)
        
        # Generate FastAPI main file
        api_content = f'''from fastapi import FastAPI
from typing import List, Dict, Any

app = FastAPI(title="{app_name} API", version="1.0.0")

@app.get("/")
async def root():
    return {{"message": "Welcome to {app_name} API"}}

@app.get("/health")
async def health():
    return {{"status": "healthy", "service": "{app_name}"}}

'''
        
        for endpoint in endpoints:
            api_content += f'''
@app.{endpoint.get('method', 'get')}("/{endpoint.get('path', 'endpoint')}")
async def {endpoint.get('name', 'endpoint')}():
    return {{"message": "Endpoint {endpoint.get('name', 'endpoint')} implemented"}}
'''
        
        files.append({
            'type': 'create_file',
            'file_path': f'/app/warm-boot/apps/{app_kebab}/api.py',
            'content': api_content
        })
        
        return files
    
    async def _generate_database_files(self, app_name: str, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate database schema files"""
        files = []
        app_kebab = self.convert_to_kebab_case(app_name)
        
        # Generate database models
        models_content = f'''from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class {app_name}Model(Base):
    __tablename__ = "{app_kebab}_data"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
'''
        
        files.append({
            'type': 'create_file',
            'file_path': f'/app/warm-boot/apps/{app_kebab}/models.py',
            'content': models_content
        })
        
        return files
    
    async def _generate_auth_files(self, app_name: str, auth_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate authentication files"""
        files = []
        app_kebab = self.convert_to_kebab_case(app_name)
        
        # Generate authentication module
        auth_content = f'''from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

security = HTTPBearer()

class {app_name}Auth:
    def __init__(self):
        self.secret_key = "{auth_config.get('secret_key', 'your-secret-key')}"
    
    async def verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(security)):
        token = credentials.credentials
        # Add token verification logic here
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        return token
'''
        
        files.append({
            'type': 'create_file',
            'file_path': f'/app/warm-boot/apps/{app_kebab}/auth.py',
            'content': auth_content
        })
        
        return files
