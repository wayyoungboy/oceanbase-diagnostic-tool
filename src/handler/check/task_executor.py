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
@file: task_executor.py
@desc: Task executor for running check tasks in subprocesses.

This module provides:
- SilentIO: Silent IO handler for subprocess execution
- execute_task: Main function to execute a task in a subprocess
"""

import os
import sys
import traceback
from typing import List, Tuple, Optional, Any, Dict

from src.handler.check.task_context import TaskExecutionContext, TaskExecutionResult


class SilentIO:
    """
    Silent IO handler for subprocess execution.

    Collects messages in memory instead of printing to stdout/stderr.
    Used when executing tasks in subprocesses to avoid IO conflicts.
    """

    def __init__(self, silent: bool = True):
        self.silent = silent
        self.messages: List[Tuple[str, str]] = []  # [(level, message), ...]
        self._verbose_messages: List[Tuple[str, str]] = []

    def _add_message(self, level: str, msg: str):
        """Add a message to the collection."""
        self.messages.append((level, str(msg)))

    def print(self, msg: str):
        """Print message (silent in subprocess mode)."""
        if not self.silent:
            self._add_message("print", msg)

    def verbose(self, msg: str):
        """Verbose message (stored but not added to main messages)."""
        self._verbose_messages.append(("verbose", str(msg)))

    def warn(self, msg: str):
        """Warning message."""
        self._add_message("warn", msg)

    def error(self, msg: str):
        """Error message."""
        self._add_message("error", msg)

    def start_progressbar(self, *args, **kwargs):
        """No-op for progress bar in subprocess."""
        pass

    def update_progressbar(self, *args, **kwargs):
        """No-op for progress bar in subprocess."""
        pass

    def finish_progressbar(self, *args, **kwargs):
        """No-op for progress bar in subprocess."""
        pass

    def get_messages(self) -> List[Tuple[str, str]]:
        """Get all collected messages."""
        return self.messages

    def get_warnings(self) -> List[str]:
        """Get all warning messages."""
        return [msg for level, msg in self.messages if level == "warn"]


class SubprocessReport:
    """
    Report collector for subprocess execution.

    Collects report items in memory instead of using TaskReport directly.
    """

    def __init__(self, task_name: str):
        self.name = task_name
        self.warning: List[str] = []
        self.critical: List[str] = []
        self.fail: List[str] = []
        self.normal: List[str] = []

    def add(self, info: str, level: str = "normal"):
        """Add a report item."""
        if level == "normal":
            self.add_normal(info)
        elif level == "warning":
            self.add_warning(info)
        elif level == "critical":
            self.add_critical(info)
        elif level == "fail":
            self.add_fail(info)

    def add_normal(self, info: str):
        msg = "[normal] " + str(info)
        if msg not in self.normal:
            self.normal.append(msg)

    def add_warning(self, info: str):
        msg = "[warning] " + str(info)
        if msg not in self.warning:
            self.warning.append(msg)

    def add_critical(self, info: str):
        msg = "[critical] " + str(info)
        if msg not in self.critical:
            self.critical.append(msg)

    def add_fail(self, info: str):
        msg = "[fail] " + str(info)
        if msg not in self.fail:
            self.fail.append(msg)

    def all(self) -> List[str]:
        return self.fail + self.critical + self.warning + self.normal

    def all_fail(self) -> List[str]:
        return self.fail

    def all_critical(self) -> List[str]:
        return self.critical

    def all_warning(self) -> List[str]:
        return self.warning

    def all_normal(self) -> List[str]:
        return self.normal


class SubprocessContext:
    """
    Minimal context for subprocess execution.

    Provides the same interface as HandlerContext but with serializable data.
    Creates independent SSH and DB connections for the subprocess.
    """

    def __init__(self, task_context: TaskExecutionContext):
        self.task_context = task_context
        self.stdio = SilentIO()
        self.cluster_config = task_context.cluster_config
        self.obproxy_config = task_context.obproxy_config
        self.inner_config = task_context.inner_config
        self.options = task_context.options
        self._variables: Dict[str, Any] = {}

    def get_variable(self, name: str, default: Any = None) -> Any:
        return self._variables.get(name, default)

    def set_variable(self, name: str, value: Any):
        self._variables[name] = value


def _create_ssh_connection(context: SubprocessContext, node: dict):
    """Create a new SSH connection for the node in the subprocess."""
    from src.common.ssh_client.ssh import SshClient

    try:
        ssher = SshClient(context, node)
        return ssher
    except Exception as e:
        context.stdio.error("Failed to create SSH connection for {0}: {1}".format(node.get("ip", "unknown"), e))
        return None


def _create_db_connection(context: SubprocessContext):
    """Create a new database connection in the subprocess."""
    from src.common.ob_connector import OBConnector

    cluster = context.cluster_config
    try:
        conn = OBConnector(
            context=context,
            ip=cluster.get("db_host"),
            port=cluster.get("db_port"),
            username=cluster.get("tenant_sys", {}).get("user"),
            password=cluster.get("tenant_sys", {}).get("password"),
            timeout=10000,
        )
        return conn
    except Exception as e:
        context.stdio.error("Failed to create DB connection: {0}".format(e))
        return None


def _init_task_in_subprocess(task_instance, context: SubprocessContext, report: SubprocessReport):
    """
    Initialize a task instance in the subprocess.

    Creates independent SSH and DB connections instead of using shared pools.
    """
    from src.handler.check.check_task import NodeWrapper
    from src.common.tool import Util

    task_instance.report = report
    task_instance.context = context
    task_instance.stdio = context.stdio
    task_instance.ob_cluster = context.cluster_config

    # Create SSH connections for observer nodes (independent per subprocess)
    observer_nodes_config = context.cluster_config.get("servers")
    if observer_nodes_config:
        task_instance.observer_nodes = []
        for node in observer_nodes_config:
            node_copy = NodeWrapper(node.copy())
            ssher = _create_ssh_connection(context, node)
            node_copy["ssher"] = ssher
            task_instance.observer_nodes.append(node_copy)

    # Create SSH connections for obproxy nodes
    obproxy_nodes_config = context.obproxy_config.get("servers")
    if obproxy_nodes_config:
        task_instance.obproxy_nodes = []
        for node in obproxy_nodes_config:
            node_copy = NodeWrapper(node.copy())
            ssher = _create_ssh_connection(context, node)
            node_copy["ssher"] = ssher
            task_instance.obproxy_nodes.append(node_copy)

    # Check if this is build_before case
    cases_option = context.options.get("cases")
    is_build_before = cases_option == "build_before"

    # Get observer version
    if is_build_before:
        task_instance.observer_version = None
        context.stdio.verbose("cases is build_before, skip getting observer version")
    else:
        task_instance.observer_version = context.task_context.observer_version

    # Create DB connection if not build_before
    if is_build_before:
        task_instance.ob_connector = None
        task_instance._using_pool_connection = False
        context.stdio.verbose("cases is build_before, skip creating database connection")
    else:
        task_instance.ob_connector = _create_db_connection(context)
        task_instance._using_pool_connection = False

    # Get obproxy version
    if task_instance.obproxy_nodes is None or len(task_instance.obproxy_nodes) == 0:
        context.stdio.verbose("obproxy_nodes is None, skip getting obproxy version")
    else:
        task_instance.obproxy_version = context.task_context.obproxy_version


def _cleanup_task_in_subprocess(task_instance):
    """
    Cleanup task resources in the subprocess.

    Closes SSH and DB connections created for this task.
    """
    # Close DB connection
    if hasattr(task_instance, "ob_connector") and task_instance.ob_connector:
        try:
            # OBConnector doesn't have explicit close, connection will be garbage collected
            pass
        except Exception:
            pass
        task_instance.ob_connector = None

    # Close SSH connections
    if hasattr(task_instance, "observer_nodes") and task_instance.observer_nodes:
        for node in task_instance.observer_nodes:
            ssher = node.get("ssher")
            if ssher and hasattr(ssher, "ssh_close"):
                try:
                    ssher.ssh_close()
                except Exception:
                    pass

    if hasattr(task_instance, "obproxy_nodes") and task_instance.obproxy_nodes:
        for node in task_instance.obproxy_nodes:
            ssher = node.get("ssher")
            if ssher and hasattr(ssher, "ssh_close"):
                try:
                    ssher.ssh_close()
                except Exception:
                    pass


def execute_task(task_context: TaskExecutionContext) -> TaskExecutionResult:
    """
    Execute a single check task in a subprocess.

    This function is the entry point for subprocess execution.
    It:
    1. Creates independent SSH and DB connections
    2. Loads and initializes the task
    3. Executes the task
    4. Collects results
    5. Cleans up resources

    Args:
        task_context: Serializable task execution context

    Returns:
        TaskExecutionResult with success status and report data
    """
    task_instance = None
    context = None
    report = None

    try:
        # Create subprocess context
        context = SubprocessContext(task_context)
        report = SubprocessReport(task_context.task_name)

        # Add task module path to sys.path for dynamic import
        module_path = task_context.task_module_path
        if module_path not in sys.path:
            sys.path.insert(0, module_path)

        # Dynamic import of task module
        from src.common.tool import DynamicLoading

        DynamicLoading.add_lib_path(module_path)
        task_module = DynamicLoading.import_module(task_context.task_class_name, context.stdio)

        if task_module is None:
            return TaskExecutionResult.create_error_result(
                task_context.task_name,
                "Failed to import task module"
            )

        if not hasattr(task_module, task_context.task_class_name):
            return TaskExecutionResult.create_error_result(
                task_context.task_name,
                "Task module missing class {0}".format(task_context.task_class_name)
            )

        # Get task class
        task_cls = getattr(task_module, task_context.task_class_name)

        # Get task info for timeout
        task_info = {}
        try:
            task_info = task_cls.get_task_info()
        except Exception as e:
            context.stdio.warn("Failed to get task info: {0}".format(e))

        # Create task instance
        task_instance = task_cls

        # Initialize task with independent connections
        _init_task_in_subprocess(task_instance, context, report)

        # Execute task
        task_instance.execute()

        # Build result
        result = TaskExecutionResult(
            task_name=task_context.task_name,
            success=True,
            warning=report.all_warning(),
            critical=report.all_critical(),
            fail=report.all_fail(),
            normal=report.all_normal(),
            task_info=task_info,
        )

        # Add any collected messages as context
        messages = context.stdio.get_messages()
        for level, msg in messages:
            if level == "warn" and msg not in result.warning:
                result.warning.append("[warning] " + msg)
            elif level == "error" and not result.error_message:
                result.error_message = msg

        return result

    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()

        # Try to get more context from stdio messages
        if context and hasattr(context, 'stdio') and hasattr(context.stdio, 'get_messages'):
            messages = context.stdio.get_messages()
            if messages:
                error_msg = error_msg + " | Messages: " + "; ".join(["{0}: {1}".format(l, m) for l, m in messages[-5:]])

        return TaskExecutionResult.create_error_result(
            task_context.task_name,
            "{0}\nTraceback: {1}".format(error_msg, error_trace)
        )

    finally:
        # Cleanup resources
        if task_instance:
            try:
                _cleanup_task_in_subprocess(task_instance)
            except Exception as cleanup_error:
                pass  # Ignore cleanup errors, process is exiting anyway