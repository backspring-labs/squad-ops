#!/usr/bin/env python3
"""
Unit tests for TaskResult Pydantic model
Tests ACI v0.8 task result structure
"""

import pytest
from pydantic import ValidationError

from agents.tasks.models import TaskResult


@pytest.mark.unit
class TestTaskResultModel:
    """Test TaskResult Pydantic model structure and status validation"""

    def test_task_result_succeeded(self):
        """Test TaskResult with SUCCEEDED status requires outputs"""
        result = TaskResult(
            task_id="task-001",
            status="SUCCEEDED",
            outputs={"result": "ok", "data": {"value": 42}},
        )

        assert result.task_id == "task-001"
        assert result.status == "SUCCEEDED"
        assert result.outputs == {"result": "ok", "data": {"value": 42}}
        assert result.error is None

    def test_task_result_failed(self):
        """Test TaskResult with FAILED status requires error"""
        result = TaskResult(
            task_id="task-001",
            status="FAILED",
            error="Task execution failed: timeout",
        )

        assert result.task_id == "task-001"
        assert result.status == "FAILED"
        assert result.error == "Task execution failed: timeout"
        assert result.outputs is None

    def test_task_result_canceled(self):
        """Test TaskResult with CANCELED status can have error"""
        result = TaskResult(
            task_id="task-001",
            status="CANCELED",
            error="Task was canceled by user",
        )

        assert result.task_id == "task-001"
        assert result.status == "CANCELED"
        assert result.error == "Task was canceled by user"
        assert result.outputs is None

    def test_task_result_missing_task_id(self):
        """Test missing task_id raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            TaskResult(
                status="SUCCEEDED",
                outputs={"result": "ok"},
            )
        assert "task_id" in str(exc_info.value)

