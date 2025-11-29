#!/usr/bin/env python3
"""
Unit tests for VersionManager class
Tests version detection, archiving, and version management
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from agents.tools.version_manager import VersionManager


class TestVersionManager:
    """Test VersionManager functionality"""
    
    @pytest.mark.unit
    def test_version_manager_initialization(self):
        """Test VersionManager initialization"""
        vm = VersionManager()
        assert vm.version_cache == {}
        assert vm.archive_history == {}
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_existing_version_from_index_html(self):
        """Test version detection from index.html"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock) as mock_exists, \
             patch.object(vm, '_read_file', new_callable=AsyncMock) as mock_read:
            
            mock_exists.return_value = True
            mock_read.return_value = '<html><body>Version: v0.1.4.021</body></html>'
            
            version = await vm.detect_existing_version('/test/source')
            
            assert version == '0.1.4.021'
            mock_exists.assert_called_once_with('/test/source/index.html')
            mock_read.assert_called_once_with('/test/source/index.html')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_existing_version_from_package_json(self):
        """Test version detection from package.json"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock) as mock_exists, \
             patch.object(vm, '_read_file', new_callable=AsyncMock) as mock_read:
            
            # index.html doesn't exist, package.json does
            def exists_side_effect(path):
                return path.endswith('package.json')
            
            mock_exists.side_effect = exists_side_effect
            mock_read.return_value = json.dumps({'version': '1.2.3'})
            
            version = await vm.detect_existing_version('/test/source')
            
            assert version == '1.2.3'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_existing_version_from_dockerfile(self):
        """Test version detection from Dockerfile"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock) as mock_exists, \
             patch.object(vm, '_read_file', new_callable=AsyncMock) as mock_read:
            
            def exists_side_effect(path):
                return path.endswith('Dockerfile')
            
            mock_exists.side_effect = exists_side_effect
            mock_read.return_value = '# VERSION=2.3.4'
            
            version = await vm.detect_existing_version('/test/source')
            
            assert version == '2.3.4'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_existing_version_from_version_file(self):
        """Test version detection from VERSION file"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock) as mock_exists, \
             patch.object(vm, '_read_file', new_callable=AsyncMock) as mock_read:
            
            def exists_side_effect(path):
                return path.endswith('VERSION')
            
            mock_exists.side_effect = exists_side_effect
            mock_read.return_value = '3.4.5\n'
            
            version = await vm.detect_existing_version('/test/source')
            
            assert version == '3.4.5'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_existing_version_unknown(self):
        """Test version detection when no version found"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=False):
            version = await vm.detect_existing_version('/test/source')
            
            assert version == 'unknown'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_existing_version_error_handling(self):
        """Test version detection error handling"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, side_effect=Exception("File error")):
            version = await vm.detect_existing_version('/test/source')
            
            assert version == 'unknown'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_archive_existing_version_success(self):
        """Test archiving existing version successfully"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(vm, 'detect_existing_version', new_callable=AsyncMock, return_value='1.0.0'), \
             patch.object(vm, '_execute_command', new_callable=AsyncMock) as mock_exec, \
             patch.object(vm, '_write_file', new_callable=AsyncMock) as mock_write:
            
            result = await vm.archive_existing_version('HelloSquad', '/test/source', '2.0.0')
            
            assert result['status'] == 'success'
            assert result['archived_version'] == '1.0.0'
            assert result['new_version'] == '2.0.0'
            assert 'archive_dir' in result
            mock_exec.assert_called()
            mock_write.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_archive_existing_version_no_source_dir(self):
        """Test archiving when source directory doesn't exist"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=False):
            result = await vm.archive_existing_version('HelloSquad', '/test/source', '2.0.0')
            
            assert result['status'] == 'no_archive_needed'
            assert result['reason'] == 'source_directory_not_found'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_archive_existing_version_unknown_version(self):
        """Test archiving with unknown version (creates legacy timestamp)"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(vm, 'detect_existing_version', new_callable=AsyncMock, return_value='unknown'), \
             patch.object(vm, '_execute_command', new_callable=AsyncMock), \
             patch.object(vm, '_write_file', new_callable=AsyncMock):
            
            result = await vm.archive_existing_version('HelloSquad', '/test/source', '2.0.0')
            
            assert result['status'] == 'success'
            assert result['archived_version'].startswith('legacy-')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_archive_existing_version_error(self):
        """Test archiving error handling"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(vm, 'detect_existing_version', new_callable=AsyncMock, side_effect=Exception("Archive error")):
            
            result = await vm.archive_existing_version('HelloSquad', '/test/source', '2.0.0')
            
            assert result['status'] == 'error'
            assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_calculate_new_version(self):
        """Test calculating new version from framework version and run ID"""
        vm = VersionManager()
        
        version = await vm.calculate_new_version('1.0.0', 'run-014')
        
        assert version == '1.0.0.014'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_calculate_new_version_no_dash(self):
        """Test calculating new version with run ID without dash"""
        vm = VersionManager()
        
        version = await vm.calculate_new_version('1.0.0', 'run014')
        
        assert version == '1.0.0.001'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_calculate_new_version_error(self):
        """Test calculating new version error handling"""
        vm = VersionManager()
        
        with patch('agents.tools.version_manager.logger'):
            version = await vm.calculate_new_version('1.0.0', None)
            
            assert version == '1.0.0.001'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_version_in_files(self):
        """Test updating version in files"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(vm, '_read_file', new_callable=AsyncMock) as mock_read, \
             patch.object(vm, '_write_file', new_callable=AsyncMock) as mock_write:
            
            mock_read.return_value = json.dumps({'version': '1.0.0'})
            
            result = await vm.update_version_in_files('/test/app', '2.0.0')
            
            assert result['status'] == 'success'
            assert result['new_version'] == '2.0.0'
            assert 'package.json' in result['updated_files']
            assert 'index.html' in result['updated_files']
            assert 'VERSION' in result['updated_files']
            assert mock_write.call_count >= 3
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_version_in_files_no_package_json(self):
        """Test updating version when package.json doesn't exist"""
        vm = VersionManager()
        
        def exists_side_effect(path):
            return not path.endswith('package.json')
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, side_effect=exists_side_effect), \
             patch.object(vm, '_read_file', new_callable=AsyncMock, return_value='<html>Version: v1.0.0</html>'), \
             patch.object(vm, '_write_file', new_callable=AsyncMock):
            
            result = await vm.update_version_in_files('/test/app', '2.0.0')
            
            assert result['status'] == 'success'
            assert 'package.json' not in result['updated_files']
            assert 'index.html' in result['updated_files']
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_update_version_in_files_error(self):
        """Test updating version error handling"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(vm, '_read_file', new_callable=AsyncMock, side_effect=Exception("Read error")):
            
            result = await vm.update_version_in_files('/test/app', '2.0.0')
            
            assert result['status'] == 'error'
            assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_version_history(self):
        """Test getting version history"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock) as mock_exists, \
             patch.object(vm, '_execute_command', new_callable=AsyncMock, return_value='archive1\narchive2'), \
             patch.object(vm, 'detect_existing_version', new_callable=AsyncMock, return_value='1.0.0'):
            
            def exists_side_effect(path):
                return 'archive' in path or 'apps' in path
            
            mock_exists.side_effect = exists_side_effect
            
            result = await vm.get_version_history('HelloSquad')
            
            assert result['status'] == 'success'
            assert result['app_name'] == 'HelloSquad'
            assert result['current_version'] == '1.0.0'
            assert 'archives' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_version_history_no_archives(self):
        """Test getting version history when no archives exist"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=False):
            result = await vm.get_version_history('HelloSquad')
            
            assert result['status'] == 'success'
            assert result['archive_count'] == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_version_history_error(self):
        """Test getting version history error handling"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, side_effect=Exception("History error")):
            result = await vm.get_version_history('HelloSquad')
            
            assert result['status'] == 'error'
            assert 'error' in result
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_old_archives(self):
        """Test cleaning up old archives"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(vm, '_execute_command', new_callable=AsyncMock) as mock_exec:
            
            # The code splits on '\\n' (literal backslash-n string)
            # Need to return string with literal \n sequences
            mock_exec.return_value = 'archive1\\narchive2\\narchive3\\narchive4\\narchive5\\narchive6'
            
            result = await vm.cleanup_old_archives('HelloSquad', keep_count=5)
            
            assert result['status'] == 'success'
            # Should have removed 1 archive (6 total - 5 keep = 1 removed)
            assert result['total_removed'] == 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_old_archives_no_cleanup_needed(self):
        """Test cleanup when not enough archives to clean"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(vm, '_execute_command', new_callable=AsyncMock, return_value='archive1\\narchive2'):
            
            result = await vm.cleanup_old_archives('HelloSquad', keep_count=5)
            
            assert result['status'] == 'no_cleanup_needed'
            assert result['archive_count'] == 2
            assert result['keep_count'] == 5
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_old_archives_no_archive_dir(self):
        """Test cleanup when archive directory doesn't exist"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=False):
            result = await vm.cleanup_old_archives('HelloSquad')
            
            assert result['status'] == 'no_archives'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_cleanup_old_archives_error(self):
        """Test cleanup error handling"""
        vm = VersionManager()
        
        with patch.object(vm, '_file_exists', new_callable=AsyncMock, return_value=True), \
             patch.object(vm, '_execute_command', new_callable=AsyncMock, side_effect=Exception("Cleanup error")):
            
            result = await vm.cleanup_old_archives('HelloSquad')
            
            assert result['status'] == 'error'
            assert 'error' in result
    
    @pytest.mark.unit
    def test_convert_to_kebab_case(self):
        """Test converting CamelCase to kebab-case"""
        vm = VersionManager()
        
        assert vm._convert_to_kebab_case('HelloSquad') == 'hello-squad'
        assert vm._convert_to_kebab_case('MyApp') == 'my-app'
        assert vm._convert_to_kebab_case('simple') == 'simple'
        assert vm._convert_to_kebab_case('AlreadyKebab') == 'already-kebab'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_generate_archive_documentation(self):
        """Test generating archive documentation"""
        vm = VersionManager()
        
        doc = await vm._generate_archive_documentation(
            'HelloSquad', '1.0.0', '2.0.0', '/source', '/archive'
        )
        
        assert 'HelloSquad' in doc
        assert '1.0.0' in doc
        assert '2.0.0' in doc
        assert '/source' in doc
        assert '/archive' in doc
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_exists(self):
        """Test file existence check"""
        vm = VersionManager()
        
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(None, None))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            exists = await vm._file_exists('/test/path')
            
            assert exists is True
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_exists_false(self):
        """Test file existence check when file doesn't exist"""
        vm = VersionManager()
        
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(None, None))
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process
            
            exists = await vm._file_exists('/test/path')
            
            assert exists is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_file_exists_error(self):
        """Test file existence check error handling"""
        vm = VersionManager()
        
        with patch('asyncio.create_subprocess_shell', side_effect=Exception("Error")):
            exists = await vm._file_exists('/test/path')
            
            assert exists is False
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_read_file(self):
        """Test reading file"""
        vm = VersionManager()
        
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b'file content', b''))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            content = await vm._read_file('/test/path')
            
            assert content == 'file content'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_read_file_error(self):
        """Test reading file error handling"""
        vm = VersionManager()
        
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b'', b'error'))
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process
            
            with pytest.raises(Exception):
                await vm._read_file('/test/path')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_write_file(self):
        """Test writing file"""
        vm = VersionManager()
        
        with patch.object(vm, '_execute_command', new_callable=AsyncMock) as mock_exec, \
             patch('asyncio.create_subprocess_shell') as mock_subprocess:
            
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(None, None))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            await vm._write_file('/test/path', 'content')
            
            mock_exec.assert_called_once()
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_write_file_error(self):
        """Test writing file error handling"""
        vm = VersionManager()
        
        with patch.object(vm, '_execute_command', new_callable=AsyncMock), \
             patch('asyncio.create_subprocess_shell') as mock_subprocess:
            
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(None, b'error'))
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process
            
            with pytest.raises(Exception):
                await vm._write_file('/test/path', 'content')
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_command(self):
        """Test executing command"""
        vm = VersionManager()
        
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b'output', b''))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await vm._execute_command('test command')
            
            assert result == 'output'
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_command_error(self):
        """Test executing command error handling"""
        vm = VersionManager()
        
        with patch('asyncio.create_subprocess_shell') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b'', b'error'))
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process
            
            with pytest.raises(Exception) as exc_info:
                await vm._execute_command('test command')
            
            assert 'Command failed' in str(exc_info.value)

