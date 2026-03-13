#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.

"""
@time: 2025/03
@file: task_context.py
@desc: Serializable task execution context for process pool execution.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class TaskExecutionResult:
    """
    Serializable task execution result.

    Contains all results from task execution that can be sent back from subprocess.
    """

    # Task identification
    task_name: str

    # Execution status
    success: bool = False
    timeout: bool = False

    # Report data (lists of messages)
    warning: List[str] = field(default_factory=list)
    critical: List[str] = field(default_factory=list)
    fail: List[str] = field(default_factory=list)
    normal: List[str] = field(default_factory=list)

    # Error message if execution failed
    error_message: Optional[str] = None

    # Task info (optional, for reference)
    task_info: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_name": self.task_name,
            "success": self.success,
            "timeout": self.timeout,
            "warning": self.warning,
            "critical": self.critical,
            "fail": self.fail,
            "normal": self.normal,
            "error_message": self.error_message,
            "task_info": self.task_info,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskExecutionResult":
        """Create from dictionary after deserialization."""
        return cls(
            task_name=data["task_name"],
            success=data.get("success", False),
            timeout=data.get("timeout", False),
            warning=data.get("warning", []),
            critical=data.get("critical", []),
            fail=data.get("fail", []),
            normal=data.get("normal", []),
            error_message=data.get("error_message"),
            task_info=data.get("task_info"),
        )

    @classmethod
    def create_timeout_result(cls, task_name: str, timeout_seconds: int) -> "TaskExecutionResult":
        """Create a result for timed-out task."""
        return cls(
            task_name=task_name,
            success=False,
            timeout=True,
            fail=["[fail] Task execution timed out after {0} seconds".format(timeout_seconds)],
        )

    @classmethod
    def create_error_result(cls, task_name: str, error_message: str) -> "TaskExecutionResult":
        """Create a result for failed task."""
        return cls(
            task_name=task_name,
            success=False,
            fail=["[fail] Task execution failed: {0}".format(error_message)],
            error_message=error_message,
        )


@dataclass
class TaskExecutionContext:
    """
    Serializable task execution context.

    Contains all configuration needed for task execution in a subprocess.
    Does NOT include non-serializable objects like stdio, connections, or file handles.
    """

    # Task identification
    task_name: str
    task_module_path: str  # Path to the task module (e.g., "/path/to/tasks/observer")
    task_class_name: str  # Class name of the task (e.g., "python_version")

    # Cluster configuration (serializable dicts)
    cluster_config: Dict[str, Any] = field(default_factory=dict)
    obproxy_config: Dict[str, Any] = field(default_factory=dict)
    inner_config: Dict[str, Any] = field(default_factory=dict)

    # Options converted from Values object
    options: Dict[str, Any] = field(default_factory=dict)

    # Version information
    observer_version: Optional[str] = None
    obproxy_version: Optional[str] = None

    # Check target type: "observer" or "obproxy"
    check_target_type: str = "observer"

    # Timeout for this specific task (seconds), None means use global default
    timeout: Optional[int] = None

    # Environment variables
    env: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_name": self.task_name,
            "task_module_path": self.task_module_path,
            "task_class_name": self.task_class_name,
            "cluster_config": self.cluster_config,
            "obproxy_config": self.obproxy_config,
            "inner_config": self.inner_config,
            "options": self.options,
            "observer_version": self.observer_version,
            "obproxy_version": self.obproxy_version,
            "check_target_type": self.check_target_type,
            "timeout": self.timeout,
            "env": self.env,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskExecutionContext":
        """Create from dictionary after deserialization."""
        return cls(
            task_name=data["task_name"],
            task_module_path=data["task_module_path"],
            task_class_name=data["task_class_name"],
            cluster_config=data.get("cluster_config", {}),
            obproxy_config=data.get("obproxy_config", {}),
            inner_config=data.get("inner_config", {}),
            options=data.get("options", {}),
            observer_version=data.get("observer_version"),
            obproxy_version=data.get("obproxy_version"),
            check_target_type=data.get("check_target_type", "observer"),
            timeout=data.get("timeout"),
            env=data.get("env", {}),
        )