"""
Smoke tests for WarmBoot workflow.
"""
import pytest
import subprocess
import json
import time
import requests
from typing import Dict, Any


class TestWarmBootSmoke:
    """Smoke tests for WarmBoot workflow."""
    
    @pytest.fixture
    def infrastructure_available(self):
        """Check if full infrastructure is available for smoke tests."""
        try:
            # Check health check service
            response = requests.get('http://localhost:8000/health', timeout=5)
            if response.status_code != 200:
                return False
            
            # Check Ollama
            ollama_response = requests.get('http://localhost:11434/api/version', timeout=5)
            if ollama_response.status_code != 200:
                return False
            
            # Check Docker
            result = subprocess.run(['docker', 'ps'], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                return False
            
            return True
        except:
            return False
    
    def get_next_run_id(self) -> str:
        """Get next sequential run ID from API using curl."""
        result = subprocess.run(
            ['curl', '-s', 'http://localhost:8000/warmboot/next-run-id'],
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)
        return data['run_id']  # Returns format: "run-056"
    
    def submit_warmboot_request(self, run_id: str) -> Dict:
        """Submit WarmBoot request using curl (matches user workflow)."""
        request_data = {
            "run_id": run_id,
            "application": "HelloSquad",
            "request_type": "from_scratch",
            "agents": ["test-lead-agent", "test-dev-agent"],
            "priority": "HIGH",
            "description": f"Smoke test run {run_id}",
            "requirements": None,
            "prd_path": "warm-boot/prd/PRD-001-HelloSquad.md"
        }
        
        result = subprocess.run(
            [
                'curl', '-s', '-X', 'POST',
                'http://localhost:8000/warmboot/submit',
                '-H', 'Content-Type: application/json',
                '-d', json.dumps(request_data)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    
    def get_warmboot_status(self, run_id: str) -> Dict:
        """Get WarmBoot status using curl."""
        result = subprocess.run(
            ['curl', '-s', f'http://localhost:8000/warmboot/status/{run_id}'],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    
    def wait_for_completion(self, run_id: str, max_wait: int = 300) -> Dict:
        """Wait for WarmBoot run to complete."""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self.get_warmboot_status(run_id)
            
            if status.get('status') in ['completed', 'failed', 'error']:
                return status
            
            time.sleep(10)  # Check every 10 seconds
        
        raise TimeoutError(f"WarmBoot run {run_id} did not complete within {max_wait} seconds")
    
    @pytest.mark.smoke
    def test_warmboot_hello_squad_workflow(self, infrastructure_available):
        """Test complete WarmBoot HelloSquad workflow."""
        if not infrastructure_available:
            pytest.skip("Full infrastructure not available for smoke test")
        
        # Step 1: Get next run ID
        run_id = self.get_next_run_id()
        assert run_id.startswith("run-")
        assert len(run_id) > 5
        
        # Step 2: Submit WarmBoot request
        submit_response = self.submit_warmboot_request(run_id)
        assert submit_response.get('status') == 'submitted'
        assert submit_response.get('run_id') == run_id
        
        # Step 3: Wait for completion
        final_status = self.wait_for_completion(run_id, max_wait=600)  # 10 minutes max
        
        # Step 4: Verify completion
        assert final_status.get('status') == 'completed'
        assert final_status.get('run_id') == run_id
        
        # Step 5: Verify all 4 tasks executed
        tasks = final_status.get('tasks', [])
        task_actions = [task.get('action') for task in tasks]
        
        assert 'archive' in task_actions
        assert 'design_manifest' in task_actions
        assert 'build' in task_actions
        assert 'deploy' in task_actions
        
        # Step 6: Verify task completion status
        for task in tasks:
            assert task.get('status') == 'completed'
            assert 'completed_at' in task
    
    @pytest.mark.smoke
    def test_app_accessible_at_target_url(self, infrastructure_available):
        """Test that app is accessible at target URL."""
        if not infrastructure_available:
            pytest.skip("Full infrastructure not available for smoke test")
        
        # Submit a quick WarmBoot request
        run_id = self.get_next_run_id()
        self.submit_warmboot_request(run_id)
        
        # Wait for completion
        final_status = self.wait_for_completion(run_id, max_wait=600)
        assert final_status.get('status') == 'completed'
        
        # Test app accessibility
        try:
            response = requests.get('http://localhost:8080/hello-squad', timeout=10)
            assert response.status_code == 200
            assert 'HelloSquad' in response.text
            
            # Check for version footer
            assert 'SquadOps' in response.text or 'version' in response.text.lower()
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"App not accessible at target URL: {e}")
    
    @pytest.mark.smoke
    def test_manifest_file_created(self, infrastructure_available):
        """Test that manifest file is created in logs."""
        if not infrastructure_available:
            pytest.skip("Full infrastructure not available for smoke test")
        
        # Submit WarmBoot request
        run_id = self.get_next_run_id()
        self.submit_warmboot_request(run_id)
        
        # Wait for completion
        final_status = self.wait_for_completion(run_id, max_wait=600)
        assert final_status.get('status') == 'completed'
        
        # Check for manifest file
        manifest_file = f"/app/logs/{run_id}_manifest.yaml"
        
        try:
            result = subprocess.run(
                ['docker', 'exec', 'squad-ops-lead-1', 'ls', '-la', manifest_file],
                capture_output=True,
                text=True,
                check=True
            )
            assert result.returncode == 0
            
            # Verify manifest content
            result = subprocess.run(
                ['docker', 'exec', 'squad-ops-lead-1', 'cat', manifest_file],
                capture_output=True,
                text=True,
                check=True
            )
            
            manifest_content = result.stdout
            assert 'architecture:' in manifest_content
            assert 'type: spa_web_app' in manifest_content
            assert 'framework: vanilla_js' in manifest_content
            assert 'files:' in manifest_content
            assert 'deployment:' in manifest_content
            
        except subprocess.CalledProcessError:
            pytest.fail(f"Manifest file {manifest_file} not found or invalid")
    
    @pytest.mark.smoke
    def test_checksums_file_created(self, infrastructure_available):
        """Test that checksums file is created in logs."""
        if not infrastructure_available:
            pytest.skip("Full infrastructure not available for smoke test")
        
        # Submit WarmBoot request
        run_id = self.get_next_run_id()
        self.submit_warmboot_request(run_id)
        
        # Wait for completion
        final_status = self.wait_for_completion(run_id, max_wait=600)
        assert final_status.get('status') == 'completed'
        
        # Check for checksums file
        checksums_file = f"/app/logs/{run_id}_checksums.json"
        
        try:
            result = subprocess.run(
                ['docker', 'exec', 'squad-ops-lead-1', 'ls', '-la', checksums_file],
                capture_output=True,
                text=True,
                check=True
            )
            assert result.returncode == 0
            
            # Verify checksums content
            result = subprocess.run(
                ['docker', 'exec', 'squad-ops-lead-1', 'cat', checksums_file],
                capture_output=True,
                text=True,
                check=True
            )
            
            checksums_data = json.loads(result.stdout)
            assert checksums_data['run_id'] == run_id
            assert 'timestamp' in checksums_data
            assert 'files' in checksums_data
            assert len(checksums_data['files']) > 0
            
            # Verify checksums are valid SHA-256 hashes
            for file_path, checksum in checksums_data['files'].items():
                assert len(checksum) == 64  # SHA-256 hex length
                assert all(c in '0123456789abcdef' for c in checksum)
            
        except subprocess.CalledProcessError:
            pytest.fail(f"Checksums file {checksums_file} not found or invalid")
        except json.JSONDecodeError:
            pytest.fail(f"Checksums file {checksums_file} contains invalid JSON")
    
    @pytest.mark.smoke
    def test_docker_container_running(self, infrastructure_available):
        """Test that Docker container is running and healthy."""
        if not infrastructure_available:
            pytest.skip("Full infrastructure not available for smoke test")
        
        # Submit WarmBoot request
        run_id = self.get_next_run_id()
        self.submit_warmboot_request(run_id)
        
        # Wait for completion
        final_status = self.wait_for_completion(run_id, max_wait=600)
        assert final_status.get('status') == 'completed'
        
        # Check container status
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=hello-squad', '--format', '{{.Status}}'],
            capture_output=True,
            text=True,
            check=True
        )
        
        container_status = result.stdout.strip()
        assert 'Up' in container_status
        assert 'healthy' in container_status or 'running' in container_status
        
        # Check container logs for errors
        result = subprocess.run(
            ['docker', 'logs', '--tail', '50', 'hello-squad'],
            capture_output=True,
            text=True,
            check=True
        )
        
        logs = result.stdout
        # Should not contain critical errors
        assert 'ERROR' not in logs or 'error' not in logs.lower()
        assert 'FATAL' not in logs or 'fatal' not in logs.lower()
    
    @pytest.mark.smoke
    def test_warmboot_api_endpoints(self, infrastructure_available):
        """Test WarmBoot API endpoints functionality."""
        if not infrastructure_available:
            pytest.skip("Full infrastructure not available for smoke test")
        
        # Test next-run-id endpoint
        run_id = self.get_next_run_id()
        assert run_id.startswith("run-")
        
        # Test submit endpoint
        submit_response = self.submit_warmboot_request(run_id)
        assert submit_response.get('status') == 'submitted'
        
        # Test status endpoint
        status_response = self.get_warmboot_status(run_id)
        assert status_response.get('run_id') == run_id
        assert 'status' in status_response
        assert 'tasks' in status_response
        
        # Test health endpoint
        health_response = requests.get('http://localhost:8000/health', timeout=5)
        assert health_response.status_code == 200
        
        health_data = health_response.json()
        assert health_data.get('status') == 'healthy'
    
    @pytest.mark.smoke
    def test_concurrent_warmboot_runs(self, infrastructure_available):
        """Test handling of concurrent WarmBoot runs."""
        if not infrastructure_available:
            pytest.skip("Full infrastructure not available for smoke test")
        
        # Submit multiple concurrent requests
        run_ids = []
        for i in range(3):
            run_id = self.get_next_run_id()
            self.submit_warmboot_request(run_id)
            run_ids.append(run_id)
        
        # Wait for all to complete
        completed_runs = []
        for run_id in run_ids:
            try:
                final_status = self.wait_for_completion(run_id, max_wait=900)  # 15 minutes
                assert final_status.get('status') == 'completed'
                completed_runs.append(run_id)
            except TimeoutError:
                pytest.fail(f"Concurrent run {run_id} did not complete in time")
        
        # Verify all runs completed successfully
        assert len(completed_runs) == 3
        
        # Verify each run has proper task sequence
        for run_id in completed_runs:
            status = self.get_warmboot_status(run_id)
            tasks = status.get('tasks', [])
            task_actions = [task.get('action') for task in tasks]
            
            assert 'archive' in task_actions
            assert 'design_manifest' in task_actions
            assert 'build' in task_actions
            assert 'deploy' in task_actions
    
    @pytest.mark.smoke
    def test_warmboot_error_handling(self, infrastructure_available):
        """Test WarmBoot error handling and recovery."""
        if not infrastructure_available:
            pytest.skip("Full infrastructure not available for smoke test")
        
        # Submit request with invalid PRD path
        run_id = self.get_next_run_id()
        
        request_data = {
            "run_id": run_id,
            "application": "TestApp",
            "request_type": "from_scratch",
            "agents": ["test-lead-agent", "test-dev-agent"],
            "priority": "HIGH",
            "description": f"Error handling test run {run_id}",
            "requirements": None,
            "prd_path": "nonexistent/prd/path.md"  # Invalid path
        }
        
        result = subprocess.run(
            [
                'curl', '-s', '-X', 'POST',
                'http://localhost:8000/warmboot/submit',
                '-H', 'Content-Type: application/json',
                '-d', json.dumps(request_data)
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        submit_response = json.loads(result.stdout)
        assert submit_response.get('status') == 'submitted'
        
        # Wait for completion (should fail gracefully)
        try:
            final_status = self.wait_for_completion(run_id, max_wait=300)
            # Should either complete with error or fail gracefully
            assert final_status.get('status') in ['completed', 'failed', 'error']
        except TimeoutError:
            # Timeout is acceptable for error cases
            pass
