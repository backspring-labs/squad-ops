"""
Mock utilities for testing JSON workflow components.
"""
import json
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any, List
import aiohttp
import asyncio

from agents.contracts.task_spec import TaskSpec
from agents.contracts.build_manifest import BuildManifest, FileSpec


class MockOllamaResponse:
    """Mock Ollama API response for testing."""
    
    @staticmethod
    def manifest_response() -> Dict[str, Any]:
        """Valid manifest JSON response."""
        return {
            "architecture": {
                "type": "spa_web_app",
                "framework": "vanilla_js",
                "description": "Single page web application"
            },
            "files": [
                {
                    "path": "index.html",
                    "purpose": "Main HTML page",
                    "dependencies": []
                },
                {
                    "path": "app.js", 
                    "purpose": "JavaScript application logic",
                    "dependencies": ["index.html"]
                },
                {
                    "path": "styles.css",
                    "purpose": "CSS styling",
                    "dependencies": ["index.html"]
                }
            ],
            "deployment": {
                "container": "nginx:alpine",
                "port": 80,
                "environment": "production"
            }
        }
    
    @staticmethod
    def files_response() -> Dict[str, Any]:
        """Valid files JSON response."""
        return {
            "files": [
                {
                    "path": "index.html",
                    "content": "<!DOCTYPE html>\n<html>\n<head><title>Test App</title></head>\n<body><h1>Hello World</h1></body>\n</html>"
                },
                {
                    "path": "app.js",
                    "content": "console.log('Hello from Test App');"
                },
                {
                    "path": "styles.css", 
                    "content": "body { font-family: Arial, sans-serif; }"
                },
                {
                    "path": "nginx.conf",
                    "content": "server {\n    listen 80;\n    location / {\n        root /usr/share/nginx/html;\n        index index.html;\n    }\n}"
                },
                {
                    "path": "Dockerfile",
                    "content": "FROM nginx:alpine\nCOPY . /usr/share/nginx/html/\nEXPOSE 80"
                }
            ]
        }
    
    @staticmethod
    def malformed_json_response() -> str:
        """Malformed JSON response."""
        return '{"architecture": {"type": "spa_web_app", "framework": "vanilla_js"'  # Missing closing braces


class MockAiohttpSession:
    """Mock aiohttp.ClientSession for testing."""
    
    def __init__(self, response_data: Dict[str, Any] = None, should_timeout: bool = False, 
                 should_raise_exception: bool = False):
        self.response_data = response_data or MockOllamaResponse.manifest_response()
        self.should_timeout = should_timeout
        self.should_raise_exception = should_raise_exception
        self.post_calls = []
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def post(self, url: str, json: Dict[str, Any] = None, **kwargs):
        """Mock POST method that returns an async context manager."""
        self.post_calls.append({"url": url, "json": json, "kwargs": kwargs})
        
        return MockAiohttpResponse(
            response_data=self.response_data,
            should_timeout=self.should_timeout,
            should_raise_exception=self.should_raise_exception
        )


class MockAiohttpResponse:
    """Mock aiohttp response for testing."""
    
    def __init__(self, response_data: Dict[str, Any] = None, should_timeout: bool = False,
                 should_raise_exception: bool = False, malformed_json: bool = False):
        self.response_data = response_data or MockOllamaResponse.manifest_response()
        self.should_timeout = should_timeout
        self.should_raise_exception = should_raise_exception
        self.malformed_json = malformed_json
    
    async def __aenter__(self):
        if self.should_timeout:
            raise asyncio.TimeoutError("Mock timeout")
        
        if self.should_raise_exception:
            raise aiohttp.ClientError("Mock connection error")
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def json(self):
        """Mock JSON response."""
        import json
        if self.malformed_json:
            return {"response": MockOllamaResponse.malformed_json_response()}
        return {"response": json.dumps(self.response_data)}
    
    @property
    def status(self):
        return 200


def create_sample_task_spec() -> TaskSpec:
    """Create a sample TaskSpec for testing."""
    return TaskSpec(
        app_name="TestApp",
        version="1.0.0", 
        run_id="TEST-001",
        prd_analysis="Test application for unit testing",
        features=["Feature 1", "Feature 2"],
        constraints={"framework": "vanilla_js"},
        success_criteria=["Application loads", "No errors"]
    )


def create_sample_build_manifest() -> BuildManifest:
    """Create a sample BuildManifest for testing."""
    return BuildManifest(
        architecture_type="spa_web_app",
        framework="vanilla_js",
        files=[
            FileSpec(
                path="index.html",
                purpose="Main page",
                dependencies=[]
            ),
            FileSpec(
                path="app.js",
                purpose="JavaScript logic",
                dependencies=["index.html"]
            )
        ],
        deployment={
            "container": "nginx:alpine",
            "port": 80,
            "environment": "production"
        }
    )


class MockFileManager:
    """Mock file manager for testing."""
    
    def __init__(self):
        self.created_files = {}
        self.create_file_calls = []
    
    async def create_file(self, file_path: str, content: str, directory: str = None) -> Dict[str, Any]:
        """Mock create_file method."""
        self.create_file_calls.append({"path": file_path, "content": content, "directory": directory})
        self.created_files[file_path] = content
        return {"status": "success", "file_path": file_path}
    
    def get_created_files(self) -> Dict[str, str]:
        """Get all created files."""
        return self.created_files.copy()


class MockDockerManager:
    """Mock Docker manager for testing."""
    
    def __init__(self):
        self.build_calls = []
        self.deploy_calls = []
        self.containers = {}
    
    async def build_image(self, app_name: str, version: str, source_dir: str) -> Dict[str, Any]:
        """Mock build_image method."""
        self.build_calls.append({"app_name": app_name, "version": version, "source_dir": source_dir})
        return {"status": "success", "image_name": f"{app_name.lower()}:{version}"}
    
    async def deploy_container(self, image_name: str, container_name: str, 
                              port: int = 80, target_url: str = None) -> Dict[str, Any]:
        """Mock deploy_container method."""
        self.deploy_calls.append({
            "image_name": image_name,
            "container_name": container_name, 
            "port": port,
            "target_url": target_url
        })
        self.containers[container_name] = {
            "image": image_name,
            "port": port,
            "url": target_url,
            "status": "running"
        }
        return {"status": "success", "container_name": container_name, "image": image_name}


class MockAgentMessage:
    """Mock AgentMessage for testing."""
    
    def __init__(self, sender: str, recipient: str, message_type: str, 
                 payload: Dict[str, Any], context: Dict[str, Any] = None):
        self.sender = sender
        self.recipient = recipient
        self.message_type = message_type
        self.payload = payload
        self.context = context or {}


def mock_ollama_json_call(response_data: Dict[str, Any] = None, 
                         should_fail: bool = False) -> MagicMock:
    """Create a mock for _call_ollama_json method."""
    mock = MagicMock()
    
    if should_fail:
        mock.side_effect = Exception("Mock LLM call failure")
    else:
        mock.return_value = response_data or MockOllamaResponse.manifest_response()
    
    return mock
