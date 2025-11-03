"""
Agent Manager for Integration Tests

Helper to manage agent containers for integration testing.
Ensures agents are running, rebuilt when needed, and healthy before tests.
"""

import asyncio
import subprocess
import time
import os
import json
from typing import List, Dict, Optional
from pathlib import Path


class AgentManager:
    """Manages agent containers for integration tests."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.agent_containers = {
            'max': 'squadops-max',
            'neo': 'squadops-neo'
        }
    
    async def ensure_agents_running(self, agents: List[str] = ['max', 'neo']) -> bool:
        """
        Ensure specified agents are running and healthy.
        
        Args:
            agents: List of agent names to check (e.g., ['max', 'neo'])
            
        Returns:
            bool: True if all agents are running and healthy
        """
        print(f"🔍 Checking agent containers: {agents}")
        
        # Check if containers exist and are running
        for agent in agents:
            if not await self._is_container_running(agent):
                print(f"⚠️  Container {agent} is not running, attempting to start...")
                if not await self._start_container(agent):
                    print(f"❌ Failed to start container {agent}")
                    return False
        
        # Wait for agents to be healthy
        for agent in agents:
            if not await self._wait_for_agent_health(agent):
                print(f"❌ Agent {agent} failed health check")
                return False
        
        print(f"✅ All agents ({agents}) are running and healthy")
        return True
    
    async def rebuild_agents(self, agents: List[str] = ['max', 'neo']) -> bool:
        """
        Rebuild and restart specified agents with latest code.
        
        Args:
            agents: List of agent names to rebuild
            
        Returns:
            bool: True if all agents rebuilt successfully
        """
        print(f"🔨 Rebuilding agent containers: {agents}")
        
        for agent in agents:
            print(f"📦 Rebuilding {agent}...")
            
            # Stop container if running
            await self._stop_container(agent)
            
            # Rebuild Docker image
            if not await self._rebuild_image(agent):
                print(f"❌ Failed to rebuild image for {agent}")
                return False
            
            # Start container
            if not await self._start_container(agent):
                print(f"❌ Failed to start rebuilt container {agent}")
                return False
        
        # Wait for all agents to be healthy
        for agent in agents:
            if not await self._wait_for_agent_health(agent):
                print(f"❌ Rebuilt agent {agent} failed health check")
                return False
        
        print(f"✅ All agents ({agents}) rebuilt and running successfully")
        return True
    
    async def verify_agent_health(self, agent_name: str) -> bool:
        """
        Verify a single agent is healthy.
        
        Args:
            agent_name: Name of agent to check
            
        Returns:
            bool: True if agent is healthy
        """
        container_name = self.agent_containers.get(agent_name)
        if not container_name:
            print(f"❌ Unknown agent: {agent_name}")
            return False
        
        # Check container status
        if not await self._is_container_running(agent_name):
            print(f"❌ Container {container_name} is not running")
            return False
        
        # Check agent logs for errors
        if not await self._check_agent_logs(agent_name):
            print(f"❌ Agent {agent_name} has errors in logs")
            return False
        
        # Check if agent is responding (basic connectivity)
        if not await self._check_agent_connectivity(agent_name):
            print(f"❌ Agent {agent_name} is not responding")
            return False
        
        print(f"✅ Agent {agent_name} is healthy")
        return True
    
    async def _is_container_running(self, agent_name: str) -> bool:
        """Check if agent container is running."""
        container_name = self.agent_containers.get(agent_name)
        if not container_name:
            return False
        
        try:
            result = subprocess.run(
                ['docker', 'ps', '--filter', f'name={container_name}', '--format', '{{.Status}}'],
                capture_output=True,
                text=True,
                check=True
            )
            return 'Up' in result.stdout
        except subprocess.CalledProcessError:
            return False
    
    async def _start_container(self, agent_name: str) -> bool:
        """Start agent container."""
        container_name = self.agent_containers.get(agent_name)
        if not container_name:
            return False
        
        try:
            # Use docker-compose to start the specific service
            result = subprocess.run(
                ['docker-compose', 'up', '-d', agent_name],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"📦 Started container {container_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start {container_name}: {e.stderr}")
            return False
    
    async def _stop_container(self, agent_name: str) -> bool:
        """Stop agent container."""
        container_name = self.agent_containers.get(agent_name)
        if not container_name:
            return False
        
        try:
            subprocess.run(
                ['docker-compose', 'stop', agent_name],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"🛑 Stopped container {container_name}")
            return True
        except subprocess.CalledProcessError:
            # Container might not be running, that's okay
            return True
    
    async def _rebuild_image(self, agent_name: str) -> bool:
        """Rebuild Docker image for agent."""
        try:
            result = subprocess.run(
                ['docker-compose', 'build', '--no-cache', agent_name],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"🔨 Rebuilt image for {agent_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to rebuild {agent_name}: {e.stderr}")
            return False
    
    async def _wait_for_agent_health(self, agent_name: str, timeout: int = 60) -> bool:
        """Wait for agent to become healthy."""
        print(f"⏳ Waiting for {agent_name} to become healthy...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if await self.verify_agent_health(agent_name):
                return True
            await asyncio.sleep(2)
        
        print(f"⏰ Timeout waiting for {agent_name} to become healthy")
        return False
    
    async def _check_agent_logs(self, agent_name: str) -> bool:
        """Check agent logs for errors."""
        container_name = self.agent_containers.get(agent_name)
        if not container_name:
            return False
        
        try:
            # Get last 20 lines of logs
            result = subprocess.run(
                ['docker', 'logs', '--tail', '20', container_name],
                capture_output=True,
                text=True,
                check=True
            )
            
            logs = result.stdout.lower()
            
            # Check for common error patterns
            error_patterns = [
                'error', 'exception', 'failed', 'traceback',
                'connection refused', 'timeout', 'dead'
            ]
            
            for pattern in error_patterns:
                if pattern in logs:
                    print(f"⚠️  Found potential error in {agent_name} logs: {pattern}")
                    return False
            
            return True
        except subprocess.CalledProcessError:
            return False
    
    async def _check_agent_connectivity(self, agent_name: str) -> bool:
        """Check basic agent connectivity."""
        container_name = self.agent_containers.get(agent_name)
        if not container_name:
            return False
        
        try:
            # Check if container is responding to basic commands
            result = subprocess.run(
                ['docker', 'exec', container_name, 'python', '-c', 'import sys; print("ok")'],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            return 'ok' in result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
    
    def get_agent_container_info(self) -> Dict[str, Dict]:
        """Get information about all agent containers."""
        info = {}
        
        for agent_name, container_name in self.agent_containers.items():
            try:
                # Get container status
                result = subprocess.run(
                    ['docker', 'ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Status}}'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                status = result.stdout.strip()
                info[agent_name] = {
                    'container_name': container_name,
                    'status': status,
                    'running': 'Up' in status if status else False
                }
            except subprocess.CalledProcessError:
                info[agent_name] = {
                    'container_name': container_name,
                    'status': 'Not found',
                    'running': False
                }
        
        return info
    
    async def check_code_freshness(self, agent_name: str) -> bool:
        """
        Check if agent code is newer than Docker image.
        
        Args:
            agent_name: Name of agent to check
            
        Returns:
            bool: True if code is newer than image (needs rebuild)
        """
        try:
            # Get agent Python file modification time
            agent_file = self.project_root / f"agents/roles/{agent_name}/agent.py"
            if not agent_file.exists():
                return False
            
            code_mtime = agent_file.stat().st_mtime
            
            # Get Docker image creation time
            container_name = self.agent_containers.get(agent_name)
            if not container_name:
                return False
            
            result = subprocess.run(
                ['docker', 'inspect', container_name, '--format', '{{.Created}}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse Docker timestamp (ISO format)
            import datetime
            image_time_str = result.stdout.strip()
            image_time = datetime.datetime.fromisoformat(image_time_str.replace('Z', '+00:00'))
            image_mtime = image_time.timestamp()
            
            return code_mtime > image_mtime
            
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            # If we can't determine, assume rebuild is needed
            return True

