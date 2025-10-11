#!/usr/bin/env python3
"""
Snapshot tests for regression prevention
Compares current outputs against known good states
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
from agents.roles.lead.agent import LeadAgent
from agents.roles.dev.agent import RefactoredDevAgent

class TestSnapshots:
    """Snapshot tests to prevent regressions"""
    
    @pytest.fixture
    def snapshot_dir(self):
        """Get snapshot directory"""
        return Path(__file__).parent / "snapshots"
    
    @pytest.fixture
    def ensure_snapshot_dir(self, snapshot_dir):
        """Ensure snapshot directory exists"""
        snapshot_dir.mkdir(exist_ok=True)
        return snapshot_dir
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_lead_agent_prd_analysis_snapshot(self, ensure_snapshot_dir, sample_prd):
        """Test PRD analysis output matches snapshot"""
        agent = LeadAgent("max")
        
        with patch.object(agent, 'call_llm') as mock_llm:
            mock_llm.return_value = {
                'core_features': ['Web Interface', 'API Endpoints', 'Database Integration'],
                'technical_requirements': ['HTML/CSS/JS', 'REST API', 'PostgreSQL', 'Docker'],
                'complexity_score': 0.7,
                'estimated_effort': '3-4 days',
                'risk_factors': ['Database complexity', 'API integration'],
                'success_criteria': ['Functional web app', 'Working API', 'Database connectivity']
            }
            
            result = await agent.analyze_prd_requirements(sample_prd)
            
            # Normalize result for comparison
            normalized_result = self._normalize_analysis_result(result)
            
            snapshot_file = ensure_snapshot_dir / "lead_agent_prd_analysis.json"
            
            if not snapshot_file.exists():
                # Create initial snapshot
                with open(snapshot_file, 'w') as f:
                    json.dump(normalized_result, f, indent=2)
                pytest.skip("Created initial snapshot - run test again to verify")
            
            # Load and compare with snapshot
            with open(snapshot_file, 'r') as f:
                snapshot_data = json.load(f)
            
            assert normalized_result == snapshot_data, \
                f"PRD analysis output changed. Expected: {snapshot_data}, Got: {normalized_result}"
    
    @pytest.mark.regression
    @pytest.mark.asyncio
    async def test_task_creation_snapshot(self, ensure_snapshot_dir):
        """Test task creation output matches snapshot"""
        agent = LeadAgent("max")
        
        prd_analysis = {
            'core_features': ['Web Interface', 'API Endpoints'],
            'technical_requirements': ['HTML/CSS/JS', 'REST API', 'Database'],
            'complexity_score': 0.7,
            'estimated_effort': '3-4 days'
        }
        
        tasks = await agent.create_development_tasks(prd_analysis, "TestApp", "test-ecid-001")
        
        # Normalize tasks for comparison
        normalized_tasks = self._normalize_tasks(tasks)
        
        snapshot_file = ensure_snapshot_dir / "task_creation.json"
        
        if not snapshot_file.exists():
            # Create initial snapshot
            with open(snapshot_file, 'w') as f:
                json.dump(normalized_tasks, f, indent=2)
            pytest.skip("Created initial snapshot - run test again to verify")
        
        # Load and compare with snapshot
        with open(snapshot_file, 'r') as f:
            snapshot_data = json.load(f)
        
        assert normalized_tasks == snapshot_data, \
            f"Task creation output changed. Expected: {snapshot_data}, Got: {normalized_tasks}"
    
    @pytest.mark.regression
    def test_agent_health_status_snapshot(self, ensure_snapshot_dir):
        """Test agent health status matches snapshot"""
        max_agent = LeadAgent("max")
        neo_agent = RefactoredDevAgent("neo")
        
        max_health = max_agent.get_health_status()
        neo_health = neo_agent.get_health_status()
        
        # Normalize health status for comparison
        normalized_health = {
            'max': self._normalize_health_status(max_health),
            'neo': self._normalize_health_status(neo_health)
        }
        
        snapshot_file = ensure_snapshot_dir / "agent_health_status.json"
        
        if not snapshot_file.exists():
            # Create initial snapshot
            with open(snapshot_file, 'w') as f:
                json.dump(normalized_health, f, indent=2)
            pytest.skip("Created initial snapshot - run test again to verify")
        
        # Load and compare with snapshot
        with open(snapshot_file, 'r') as f:
            snapshot_data = json.load(f)
        
        assert normalized_health == snapshot_data, \
            f"Agent health status changed. Expected: {snapshot_data}, Got: {normalized_health}"
    
    @pytest.mark.regression
    def test_complexity_assessment_snapshot(self, ensure_snapshot_dir):
        """Test complexity assessment matches snapshot"""
        agent = LeadAgent("max")
        
        test_cases = [
            {'complexity': 0.1, 'requirements': {'action': 'archive'}},
            {'complexity': 0.3, 'requirements': {'action': 'build', 'features': ['basic']}},
            {'complexity': 0.6, 'requirements': {'action': 'build', 'features': ['advanced']}},
            {'complexity': 0.9, 'requirements': {'action': 'build', 'features': ['complex', 'advanced']}}
        ]
        
        results = {}
        for i, task in enumerate(test_cases):
            assessment = agent.assess_complexity(task)
            results[f"case_{i+1}"] = {
                'input_complexity': task['complexity'],
                'assessment': assessment
            }
        
        snapshot_file = ensure_snapshot_dir / "complexity_assessment.json"
        
        if not snapshot_file.exists():
            # Create initial snapshot
            with open(snapshot_file, 'w') as f:
                json.dump(results, f, indent=2)
            pytest.skip("Created initial snapshot - run test again to verify")
        
        # Load and compare with snapshot
        with open(snapshot_file, 'r') as f:
            snapshot_data = json.load(f)
        
        assert results == snapshot_data, \
            f"Complexity assessment changed. Expected: {snapshot_data}, Got: {results}"
    
    @pytest.mark.regression
    def test_governance_decisions_snapshot(self, ensure_snapshot_dir):
        """Test governance decisions match snapshot"""
        agent = LeadAgent("max")
        
        test_cases = [
            {'complexity': 0.2, 'priority': 'LOW'},
            {'complexity': 0.5, 'priority': 'MEDIUM'},
            {'complexity': 0.8, 'priority': 'HIGH'},
            {'complexity': 0.9, 'priority': 'CRITICAL'}
        ]
        
        results = {}
        for i, task in enumerate(test_cases):
            decision = agent.make_governance_decision(task)
            results[f"case_{i+1}"] = {
                'input': task,
                'decision': decision
            }
        
        snapshot_file = ensure_snapshot_dir / "governance_decisions.json"
        
        if not snapshot_file.exists():
            # Create initial snapshot
            with open(snapshot_file, 'w') as f:
                json.dump(results, f, indent=2)
            pytest.skip("Created initial snapshot - run test again to verify")
        
        # Load and compare with snapshot
        with open(snapshot_file, 'r') as f:
            snapshot_data = json.load(f)
        
        assert results == snapshot_data, \
            f"Governance decisions changed. Expected: {snapshot_data}, Got: {results}"
    
    def _normalize_analysis_result(self, result):
        """Normalize PRD analysis result for comparison"""
        return {
            'core_features': sorted(result.get('core_features', [])),
            'technical_requirements': sorted(result.get('technical_requirements', [])),
            'complexity_score': result.get('complexity_score'),
            'estimated_effort': result.get('estimated_effort'),
            'risk_factors': sorted(result.get('risk_factors', [])),
            'success_criteria': sorted(result.get('success_criteria', []))
        }
    
    def _normalize_tasks(self, tasks):
        """Normalize tasks for comparison"""
        normalized = []
        for task in tasks:
            normalized_task = {
                'task_type': task.get('task_type'),
                'requirements': {
                    'action': task.get('requirements', {}).get('action'),
                    'application': task.get('requirements', {}).get('application'),
                    'version': task.get('requirements', {}).get('version')
                },
                'complexity': task.get('complexity'),
                'priority': task.get('priority')
            }
            normalized.append(normalized_task)
        return normalized
    
    def _normalize_health_status(self, health):
        """Normalize health status for comparison"""
        return {
            'name': health.get('name'),
            'agent_type': health.get('agent_type'),
            'reasoning_style': health.get('reasoning_style'),
            'status': health.get('status'),
            'has_uptime': 'uptime' in health,
            'has_message_queue_size': 'message_queue_size' in health,
            'has_task_history_size': 'task_history_size' in health
        }


