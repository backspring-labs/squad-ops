#!/usr/bin/env python3
"""
Version Manager Component for Dev Agent
Handles version detection, archiving, and version management
"""

import logging
import asyncio
import json
import re
from typing import Dict, Any, Optional
from datetime import datetime
import sys
import os

# Add config path
sys.path.append('/app')
from config.deployment_config import get_version_config

logger = logging.getLogger(__name__)

class VersionManager:
    """Handles version detection, archiving, and version management"""
    
    def __init__(self):
        self.version_cache = {}
        self.archive_history = {}
    
    async def detect_existing_version(self, source_dir: str) -> str:
        """Detect the version of existing code by reading version info from files"""
        try:
            # Try to read version from index.html first
            index_path = f"{source_dir}/index.html"
            if await self._file_exists(index_path):
                content = await self._read_file(index_path)
                # Look for version pattern like "Version: v0.1.4.021"
                version_match = re.search(r'Version:\s*v([0-9.]+)', content)
                if version_match:
                    detected_version = version_match.group(1)
                    logger.info(f"VersionManager detected version from index.html: {detected_version}")
                    return detected_version
            
            # Try to read version from package.json
            package_path = f"{source_dir}/package.json"
            if await self._file_exists(package_path):
                content = await self._read_file(package_path)
                # Look for version in package.json
                try:
                    package_data = json.loads(content)
                    if 'version' in package_data:
                        detected_version = package_data['version']
                        logger.info(f"VersionManager detected version from package.json: {detected_version}")
                        return detected_version
                except json.JSONDecodeError:
                    pass
            
            # Try to read version from Dockerfile
            dockerfile_path = f"{source_dir}/Dockerfile"
            if await self._file_exists(dockerfile_path):
                content = await self._read_file(dockerfile_path)
                # Look for version in comments or labels
                version_match = re.search(r'VERSION[:\s=]+([0-9.]+)', content, re.IGNORECASE)
                if version_match:
                    detected_version = version_match.group(1)
                    logger.info(f"VersionManager detected version from Dockerfile: {detected_version}")
                    return detected_version
            
            # Try to read version from a version file
            version_file_path = f"{source_dir}/VERSION"
            if await self._file_exists(version_file_path):
                content = await self._read_file(version_file_path)
                detected_version = content.strip()
                logger.info(f"VersionManager detected version from VERSION file: {detected_version}")
                return detected_version
            
            logger.warning(f"VersionManager could not detect version in {source_dir}")
            return 'unknown'
            
        except Exception as e:
            logger.error(f"VersionManager failed to detect existing version: {e}")
            return 'unknown'
    
    async def archive_existing_version(self, app_name: str, source_dir: str, new_version: str) -> Dict[str, Any]:
        """Archive existing version to preserve it before new deployment"""
        try:
            app_kebab = self._convert_to_kebab_case(app_name)
            
            # Check if source directory exists
            if not await self._file_exists(source_dir):
                logger.info(f"VersionManager: no existing {source_dir} to archive (clean slate)")
                return {
                    'status': 'no_archive_needed',
                    'reason': 'source_directory_not_found',
                    'source_dir': source_dir
                }
            
            # Detect the existing version
            existing_version = await self.detect_existing_version(source_dir)
            if existing_version == 'unknown':
                # If we can't detect version, use a timestamp-based version
                import time
                existing_version = f"legacy-{int(time.time())}"
            
            # Create archive directory
            archive_dir = f"warm-boot/archive/{app_kebab}-{existing_version}-archive"
            await self._execute_command(f"mkdir -p {archive_dir}")
            
            # Move the entire source directory to archive
            await self._execute_command(f"mv {source_dir} {archive_dir}/")
            logger.info(f"VersionManager moved entire {source_dir} to {archive_dir}")
            
            # Create archive documentation
            doc_content = await self._generate_archive_documentation(
                app_name, existing_version, new_version, source_dir, archive_dir
            )
            await self._write_file(f"{archive_dir}/ARCHIVE_README.md", doc_content)
            logger.info(f"VersionManager created archive documentation")
            
            # Store archive info
            self.archive_history[f"{app_name}-{existing_version}"] = {
                'archived_at': datetime.now().isoformat(),
                'source_dir': source_dir,
                'archive_dir': archive_dir,
                'existing_version': existing_version,
                'new_version': new_version
            }
            
            return {
                'status': 'success',
                'archived_version': existing_version,
                'archive_dir': archive_dir,
                'source_dir': source_dir,
                'new_version': new_version
            }
            
        except Exception as e:
            logger.error(f"VersionManager failed to archive existing version: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'app_name': app_name,
                'source_dir': source_dir
            }
    
    async def calculate_new_version(self, framework_version: str, run_id: str) -> str:
        """Calculate new version based on framework version and run ID"""
        try:
            # Extract warm-boot sequence from the run_id
            # The run_id is passed in the task (e.g., "run-014" -> "014")
            warm_boot_sequence = run_id.split("-")[1] if "-" in run_id else "001"
            
            new_version = f"{framework_version}.{warm_boot_sequence}"
            logger.info(f"VersionManager calculated new version: {new_version}")
            
            return new_version
            
        except Exception as e:
            logger.error(f"VersionManager failed to calculate new version: {e}")
            return f"{framework_version}.001"
    
    async def update_version_in_files(self, app_dir: str, new_version: str) -> Dict[str, Any]:
        """Update version information in application files"""
        try:
            updated_files = []
            
            # Update package.json
            package_json_path = f"{app_dir}/package.json"
            if await self._file_exists(package_json_path):
                content = await self._read_file(package_json_path)
                package_data = json.loads(content)
                package_data['version'] = new_version
                updated_content = json.dumps(package_data, indent=2)
                await self._write_file(package_json_path, updated_content)
                updated_files.append('package.json')
            
            # Update index.html
            index_html_path = f"{app_dir}/index.html"
            if await self._file_exists(index_html_path):
                content = await self._read_file(index_html_path)
                # Replace version in footer
                updated_content = re.sub(
                    r'Version: v[0-9.]+',
                    f'Version: v{new_version}',
                    content
                )
                await self._write_file(index_html_path, updated_content)
                updated_files.append('index.html')
            
            # Create/update VERSION file
            version_file_path = f"{app_dir}/VERSION"
            await self._write_file(version_file_path, new_version)
            updated_files.append('VERSION')
            
            logger.info(f"VersionManager updated version in {len(updated_files)} files: {updated_files}")
            
            return {
                'status': 'success',
                'new_version': new_version,
                'updated_files': updated_files
            }
            
        except Exception as e:
            logger.error(f"VersionManager failed to update version in files: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'app_dir': app_dir,
                'new_version': new_version
            }
    
    async def get_version_history(self, app_name: str) -> Dict[str, Any]:
        """Get version history for an application"""
        try:
            app_kebab = self._convert_to_kebab_case(app_name)
            archive_dir = f"warm-boot/archive"
            
            # List all archives for this app
            if await self._file_exists(archive_dir):
                result = await self._execute_command(f"ls -la {archive_dir} | grep {app_kebab}")
                archives = result.split('\\n') if result else []
            else:
                archives = []
            
            # Get current version if app exists
            current_app_dir = f"warm-boot/apps/{app_kebab}"
            current_version = 'unknown'
            if await self._file_exists(current_app_dir):
                current_version = await self.detect_existing_version(current_app_dir)
            
            return {
                'status': 'success',
                'app_name': app_name,
                'current_version': current_version,
                'archives': archives,
                'archive_count': len(archives)
            }
            
        except Exception as e:
            logger.error(f"VersionManager failed to get version history: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'app_name': app_name
            }
    
    async def cleanup_old_archives(self, app_name: str, keep_count: int = 5) -> Dict[str, Any]:
        """Clean up old archives, keeping only the most recent ones"""
        try:
            app_kebab = self._convert_to_kebab_case(app_name)
            archive_dir = f"warm-boot/archive"
            
            if not await self._file_exists(archive_dir):
                return {
                    'status': 'no_archives',
                    'app_name': app_name
                }
            
            # List archives for this app, sorted by modification time (newest first)
            result = await self._execute_command(f"ls -t {archive_dir} | grep {app_kebab}")
            archives = result.split('\\n') if result else []
            
            if len(archives) <= keep_count:
                return {
                    'status': 'no_cleanup_needed',
                    'app_name': app_name,
                    'archive_count': len(archives),
                    'keep_count': keep_count
                }
            
            # Remove old archives
            archives_to_remove = archives[keep_count:]
            removed_archives = []
            
            for archive in archives_to_remove:
                if archive.strip():  # Skip empty lines
                    archive_path = f"{archive_dir}/{archive}"
                    await self._execute_command(f"rm -rf {archive_path}")
                    removed_archives.append(archive)
                    logger.info(f"VersionManager removed old archive: {archive}")
            
            return {
                'status': 'success',
                'app_name': app_name,
                'removed_archives': removed_archives,
                'kept_archives': archives[:keep_count],
                'total_removed': len(removed_archives)
            }
            
        except Exception as e:
            logger.error(f"VersionManager failed to cleanup old archives: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'app_name': app_name
            }
    
    def _convert_to_kebab_case(self, name: str) -> str:
        """Convert CamelCase to kebab-case (e.g., HelloSquad -> hello-squad)"""
        import re
        # Insert dash before uppercase letters (except the first one)
        kebab = re.sub(r'(?<!^)(?=[A-Z])', '-', name)
        return kebab.lower()
    
    async def _generate_archive_documentation(self, app_name: str, existing_version: str, new_version: str, source_dir: str, archive_dir: str) -> str:
        """Generate archive documentation"""
        return f"""# Archive Documentation

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

## Files Archived
- index.html (main application file)
- styles.css (styling)
- script.js (JavaScript functionality)
- Dockerfile (container configuration)
- package.json (project metadata)
- Any additional custom files

## Recovery
To restore this version:
1. Copy the archived directory back to the apps folder
2. Update the container name and ports if needed
3. Redeploy using the Docker configuration

**Archive created by SquadOps Version Manager**
"""
    
    async def _file_exists(self, file_path: str) -> bool:
        """Check if a file or directory exists"""
        try:
            process = await asyncio.create_subprocess_shell(
                f"test -e '{file_path}'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False
    
    async def _read_file(self, file_path: str) -> str:
        """Read file content"""
        try:
            process = await asyncio.create_subprocess_shell(
                f"cat '{file_path}'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Failed to read file: {file_path}")
            
            return stdout.decode()
        except Exception as e:
            logger.error(f"VersionManager failed to read file {file_path}: {e}")
            raise
    
    async def _write_file(self, file_path: str, content: str):
        """Write content to file"""
        try:
            # Ensure directory exists
            dir_path = os.path.dirname(file_path)
            await self._execute_command(f"mkdir -p '{dir_path}'")
            
            # Write file
            process = await asyncio.create_subprocess_shell(
                f"cat > '{file_path}'",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate(input=content.encode())
            
            if process.returncode != 0:
                raise Exception(f"Failed to write file: {file_path}")
                
        except Exception as e:
            logger.error(f"VersionManager failed to write file {file_path}: {e}")
            raise
    
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
                raise Exception(f"Command failed: {command}, Error: {stderr.decode()}")
            
            return stdout.decode().strip()
            
        except Exception as e:
            logger.error(f"VersionManager command execution failed: {command}, Error: {e}")
            raise
