#!/usr/bin/env python3
"""
Docker Manager Component for Dev Agent
Handles container operations, deployment, and Docker management
"""

import asyncio
import logging
import os
import sys
from typing import Any

# Add config path
sys.path.append('/app')
from config.deployment_config import get_deployment_config, get_docker_config

logger = logging.getLogger(__name__)

class DockerManager:
    """Handles Docker container operations and deployment"""
    
    def __init__(self):
        self.containers = {}
        self.images = {}
    
    async def build_image(self, app_name: str, version: str, source_dir: str) -> dict[str, Any]:
        """Build Docker image for application"""
        try:
            app_kebab = self._convert_to_kebab_case(app_name)
            
            # Check if source directory exists
            if not os.path.exists(source_dir):
                error_msg = f"Source directory does not exist: {source_dir}. Files may not have been generated."
                logger.error(f"DockerManager: {error_msg}")
                return {
                    'status': 'error',
                    'error': error_msg,
                    'image_name': app_name,
                    'version': version,
                    'source_dir': source_dir
                }
            
            # Build Docker image
            build_cmd = f"cd {source_dir} && docker build -t {app_kebab} ."
            await self._execute_command(build_cmd)
            
            # Tag with version
            tag_cmd = f"docker tag {app_kebab} {app_kebab}:{version}"
            await self._execute_command(tag_cmd)
            
            logger.info(f"DockerManager built image: {app_kebab}:{version}")
            
            return {
                'status': 'success',
                'image_name': app_kebab,
                'version': version,
                'source_dir': source_dir
            }
            
        except Exception as e:
            logger.error(f"DockerManager failed to build image: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'image_name': app_name,
                'version': version
            }
    
    async def deploy_container(self, app_name: str, version: str) -> dict[str, Any]:
        """Deploy application container"""
        try:
            app_kebab = self._convert_to_kebab_case(app_name)
            container_name = f"squadops-{app_kebab}"
            
            # Clean up existing containers
            await self._cleanup_existing_containers(container_name, app_kebab)
            
            # Start new container
            network_name = get_docker_config('network_name')
            port = get_deployment_config('default_port')
            restart_policy = get_docker_config('restart_policy')
            
            run_cmd = f"docker run -d --name {container_name} --network {network_name} -p {port}:80 --restart {restart_policy} {app_kebab}:{version}"
            await self._execute_command(run_cmd)
            
            logger.info(f"DockerManager deployed container: {container_name}")
            
            return {
                'status': 'success',
                'container_name': container_name,
                'image': f"{app_kebab}:{version}",
                'network': network_name,
                'port': port
            }
            
        except Exception as e:
            logger.error(f"DockerManager failed to deploy container: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'container_name': container_name
            }
    
    async def stop_container(self, container_name: str) -> dict[str, Any]:
        """Stop a running container"""
        try:
            stop_cmd = f"docker stop {container_name}"
            await self._execute_command(stop_cmd)
            
            logger.info(f"DockerManager stopped container: {container_name}")
            
            return {
                'status': 'success',
                'container_name': container_name,
                'action': 'stopped'
            }
            
        except Exception as e:
            # Check if container doesn't exist - this is expected during cleanup
            if "No such container" in str(e):
                logger.debug(f"DockerManager: container {container_name} doesn't exist (expected during cleanup)")
                return {
                    'status': 'not_found',
                    'container_name': container_name,
                    'action': 'not_found'
                }
            else:
                logger.error(f"DockerManager failed to stop container: {e}")
                return {
                    'status': 'error',
                    'error': str(e),
                    'container_name': container_name
                }
    
    async def remove_container(self, container_name: str) -> dict[str, Any]:
        """Remove a container"""
        try:
            remove_cmd = f"docker rm {container_name}"
            await self._execute_command(remove_cmd)
            
            logger.info(f"DockerManager removed container: {container_name}")
            
            return {
                'status': 'success',
                'container_name': container_name,
                'action': 'removed'
            }
            
        except Exception as e:
            # Check if container doesn't exist - this is expected during cleanup
            if "No such container" in str(e):
                logger.debug(f"DockerManager: container {container_name} doesn't exist (expected during cleanup)")
                return {
                    'status': 'not_found',
                    'container_name': container_name,
                    'action': 'not_found'
                }
            else:
                logger.error(f"DockerManager failed to remove container: {e}")
                return {
                    'status': 'error',
                    'error': str(e),
                    'container_name': container_name
                }
    
    async def get_container_status(self, container_name: str) -> dict[str, Any]:
        """Get container status"""
        try:
            status_cmd = f"docker ps -a --filter name={container_name} --format '{{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'"
            result = await self._execute_command(status_cmd)
            
            if result and container_name in result:
                return {
                    'status': 'success',
                    'container_name': container_name,
                    'details': result
                }
            else:
                return {
                    'status': 'not_found',
                    'container_name': container_name
                }
                
        except Exception as e:
            logger.error(f"DockerManager failed to get container status: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'container_name': container_name
            }
    
    async def list_containers(self, filter_name: str = None) -> dict[str, Any]:
        """List containers with optional filtering"""
        try:
            if filter_name:
                list_cmd = f"docker ps -a --filter name={filter_name} --format '{{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'"
            else:
                list_cmd = "docker ps -a --format '{{.Names}}\\t{{.Status}}\\t{{.Ports}}'"
            
            result = await self._execute_command(list_cmd)
            
            return {
                'status': 'success',
                'containers': result.split('\\n') if result else [],
                'filter': filter_name
            }
            
        except Exception as e:
            logger.error(f"DockerManager failed to list containers: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def cleanup_old_containers(self, app_name: str) -> dict[str, Any]:
        """Clean up old containers for an application"""
        try:
            app_kebab = self._convert_to_kebab_case(app_name)
            cleaned_containers = []
            
            # List of potential old container names
            old_names = [
                f"squadops-{app_kebab}",
                f"squadops-{app_name.lower()}",
                f"squadops-{app_name.lower()}-test",
                f"squadops-{app_name.lower()}-new",
                f"squadops-{app_name.lower()}-final"
            ]
            
            for old_name in old_names:
                try:
                    # Stop container if running
                    await self.stop_container(old_name)
                    # Remove container
                    await self.remove_container(old_name)
                    cleaned_containers.append(old_name)
                    logger.info(f"DockerManager cleaned up old container: {old_name}")
                except Exception:
                    # Container might not exist, which is fine
                    pass
            
            return {
                'status': 'success',
                'cleaned_containers': cleaned_containers,
                'app_name': app_name
            }
            
        except Exception as e:
            logger.error(f"DockerManager failed to cleanup old containers: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'app_name': app_name
            }
    
    async def _cleanup_existing_containers(self, container_name: str, app_kebab: str):
        """Clean up existing containers that might conflict"""
        try:
            # Stop and remove any existing containers with the same name
            await self.stop_container(container_name)
            await self.remove_container(container_name)
            logger.info(f"DockerManager removed existing container: {container_name}")
        except Exception:
            logger.info(f"DockerManager: no existing container {container_name} to remove")
        
        # Also clean up any old containers with different naming patterns
        old_names = [
            f"squadops-{app_kebab}",
            f"squadops-{app_kebab}-test",
            f"squadops-{app_kebab}-new",
            f"squadops-{app_kebab}-final"
        ]
        
        for old_name in old_names:
            try:
                await self.stop_container(old_name)
                await self.remove_container(old_name)
                logger.info(f"DockerManager cleaned up old container: {old_name}")
            except Exception:
                pass  # Ignore if container doesn't exist
    
    def _convert_to_kebab_case(self, name: str) -> str:
        """Convert CamelCase to kebab-case (e.g., HelloSquad -> hello-squad)"""
        import re
        # Insert dash before uppercase letters (except the first one)
        kebab = re.sub(r'(?<!^)(?=[A-Z])', '-', name)
        return kebab.lower()
    
    async def _execute_command(self, command: str) -> str:
        """Execute a shell command and return output"""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                stderr_text = stderr.decode().strip() if stderr else 'No error details'
                # Provide clearer error messages for common issues
                if "can't cd to" in stderr_text or "No such file or directory" in stderr_text:
                    raise Exception(f"Directory not found - {stderr_text}. Files may not have been generated successfully.")
                raise Exception(f"Command failed: {command}, Error: {stderr_text}")
            
            return stdout.decode().strip()
            
        except Exception as e:
            # Don't log "No such container" errors as they're expected during cleanup
            if "No such container" not in str(e):
                logger.error(f"DockerManager command execution failed: {command}, Error: {e}")
            raise
    
    async def health_check(self) -> dict[str, Any]:
        """Perform Docker health check"""
        try:
            # Check if Docker is available
            await self._execute_command("docker --version")
            
            # Check if Docker daemon is running
            await self._execute_command("docker info")
            
            return {
                'status': 'healthy',
                'docker_available': True,
                'daemon_running': True
            }
            
        except Exception as e:
            logger.error(f"DockerManager health check failed: {e}")
            return {
                'status': 'unhealthy',
                'docker_available': False,
                'daemon_running': False,
                'error': str(e)
            }
    
    async def get_system_info(self) -> dict[str, Any]:
        """Get Docker system information"""
        try:
            # Get Docker version
            version_info = await self._execute_command("docker --version")
            
            # Get system info
            system_info = await self._execute_command("docker system df")
            
            # Get running containers count
            running_containers = await self._execute_command("docker ps --format '{{.Names}}'")
            container_count = len(running_containers.split('\\n')) if running_containers else 0
            
            return {
                'status': 'success',
                'docker_version': version_info,
                'system_info': system_info,
                'running_containers': container_count
            }
            
        except Exception as e:
            logger.error(f"DockerManager failed to get system info: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
