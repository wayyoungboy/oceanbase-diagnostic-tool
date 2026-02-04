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
@time: 2026/02/04
@file: handler_invoker.py
@desc: Direct handler invoker for AI Assistant - replaces subprocess command execution
"""

import os
from optparse import Values
from typing import Dict, List, Any, Optional
from io import StringIO

from src.common.handler_factory import HandlerFactory
from src.common.context_manager import ContextManager
from src.common.config import ConfigManager, InnerConfigManager
from src.common.context import HandlerContext
from src.common.result_type import ObdiagResult


class HandlerInvoker:
    """
    Direct handler invoker for AI Assistant.
    
    This class provides a unified interface to directly invoke obdiag handlers
    without going through subprocess command execution.
    
    Benefits:
    1. Better performance (no subprocess overhead)
    2. Better error handling (direct exception propagation)
    3. Structured data access (direct ObdiagResult access)
    4. Unified codebase (no duplicate logic)
    """

    # Mapping from tool names to handler names and namespaces
    TOOL_TO_HANDLER_MAP = {
        "gather_log": {
            "handler": "gather_component_log",
            "namespace": "gather",
            "module": "src.handler.gather.gather_component_log",
        },
        "gather_plan_monitor": {
            "handler": "gather_plan_monitor",
            "namespace": "gather",
            "module": "src.handler.gather.gather_plan_monitor",
        },
        "gather_sysstat": {
            "handler": "gather_sysstat",
            "namespace": "gather",
            "module": "src.handler.gather.gather_sysstat",
        },
        "gather_perf": {
            "handler": "gather_perf",
            "namespace": "gather",
            "module": "src.handler.gather.gather_perf",
        },
        "gather_obproxy_log": {
            "handler": "gather_obproxy_log",
            "namespace": "gather",
            "module": "src.handler.gather.gather_obproxy_log",
        },
        "gather_ash": {
            "handler": "gather_ash_report",
            "namespace": "gather",
            "module": "src.handler.gather.gather_ash_report",
        },
        "gather_awr": {
            "handler": "gather_awr",
            "namespace": "gather",
            "module": "src.handler.gather.gather_awr",
        },
        "analyze_log": {
            "handler": "analyze_log",
            "namespace": "analyze",
            "module": "src.handler.analyzer.analyze_log",
        },
        "check": {
            "handler": "check",
            "namespace": "check",
            "module": "src.handler.check.check_handler",
        },
        "check_list": {
            "handler": "check_list",
            "namespace": "check",
            "module": "src.handler.check.check_list",
        },
        "rca_run": {
            "handler": "rca",
            "namespace": "rca",
            "module": "src.handler.rca.rca_handler",
        },
        "rca_list": {
            "handler": "rca_list",
            "namespace": "rca",
            "module": "src.handler.rca.rca_list",
        },
        "tool_io_performance": {
            "handler": "tool_io_performance",
            "namespace": "tool",
            "module": "src.handler.tools.io_performance_handler",
        },
    }

    def __init__(self, config_path: Optional[str] = None, stdio=None, context: Optional[HandlerContext] = None):
        """
        Initialize handler invoker.
        
        Args:
            config_path: Path to obdiag config file
            stdio: Stdio instance for logging
            context: Existing HandlerContext (optional)
        """
        self.config_path = config_path or os.path.expanduser("~/.obdiag/config.yml")
        self.stdio = stdio
        self.context = context
        
        # Initialize managers
        self.config_manager = None
        self.inner_config_manager = None
        self.context_manager = None
        self.handler_factory = None
        
        self._initialize_managers()

    def _initialize_managers(self):
        """Initialize configuration and handler managers"""
        try:
            # Initialize config managers
            self.inner_config_manager = InnerConfigManager(stdio=self.stdio)
            self.config_manager = ConfigManager(
                config_path=self.config_path,
                stdio=self.stdio,
                inner_config_manager=self.inner_config_manager
            )
            
            # Initialize context manager
            self.context_manager = ContextManager(
                stdio=self.stdio,
                config_manager=self.config_manager,
                inner_config_manager=self.inner_config_manager
            )
            
            # Initialize handler factory
            self.handler_factory = HandlerFactory()
            self.handler_factory.auto_discover("src.handler")
            
        except Exception as e:
            if self.stdio:
                self.stdio.warn(f"Failed to initialize managers: {e}")
            raise

    def invoke(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        capture_output: bool = True
    ) -> Dict[str, Any]:
        """
        Invoke a handler directly.
        
        Args:
            tool_name: Name of the tool to invoke
            arguments: Dictionary of arguments to pass to the handler
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            Dictionary containing:
            - success: bool
            - result: ObdiagResult or None
            - stdout: str (if capture_output=True)
            - stderr: str (if capture_output=True)
            - error: str (if error occurred)
        """
        if tool_name not in self.TOOL_TO_HANDLER_MAP:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "stdout": "",
                "stderr": f"Unknown tool: {tool_name}",
            }

        tool_info = self.TOOL_TO_HANDLER_MAP[tool_name]
        handler_name = tool_info["handler"]
        namespace = tool_info["namespace"]

        # Use existing stdio or create a capturing one
        if capture_output and self.stdio:
            # For now, use the existing stdio
            # Output will be captured through the stdio's internal mechanisms
            use_stdio = self.stdio
        else:
            use_stdio = self.stdio

        try:
            # Convert arguments to Options Values object
            options = self._arguments_to_options(arguments)
            
            # Create context with proper stdio
            context = self.context_manager.create_context(
                handler_name=handler_name,
                namespace=namespace,
                options=options,
                skip_cluster_conn=False  # Most handlers need cluster connection
            )
            
            # Override stdio if we want to capture
            if use_stdio:
                context.stdio = use_stdio
            
            # Create handler
            handler = self.handler_factory.create(
                handler_name=handler_name,
                context=context
            )
            
            # Execute handler
            result: ObdiagResult = handler.handle()
            
            # Extract output from result if available
            stdout_content = ""
            stderr_content = ""
            
            # Try to get output from result data
            if hasattr(result, 'data') and isinstance(result.data, dict):
                stdout_content = result.data.get('stdout', '')
                stderr_content = result.data.get('stderr', '')
            
            # If no output in result, construct from result message
            if not stdout_content and hasattr(result, 'msg'):
                stdout_content = result.msg or ""
            
            return {
                "success": result.code == ObdiagResult.SUCCESS_CODE,
                "result": result,
                "stdout": stdout_content,
                "stderr": stderr_content,
                "return_code": result.code,
                "data": result.data if hasattr(result, 'data') else None,
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": f"{str(e)}\n{error_trace}",
                "return_code": -1,
            }

    def _arguments_to_options(self, arguments: Dict[str, Any]) -> Values:
        """
        Convert arguments dictionary to Options Values object.
        
        Handlers access options via _get_option(name) which calls getattr(options, name).
        So we need to set all arguments as attributes on the Values object.
        
        Args:
            arguments: Dictionary of argument name-value pairs
            
        Returns:
            Values object compatible with optparse
        """
        options = Values()
        
        # Set all arguments as attributes
        # Handlers will access them via _get_option(name)
        for key, value in arguments.items():
            if value is not None:
                setattr(options, key, value)
        
        # Set default values for common options
        if not hasattr(options, 'config'):
            options.config = []
        
        # Handle special cases
        # Some handlers expect 'from' and 'to' for time ranges
        if 'from' in arguments:
            setattr(options, 'from', arguments['from'])
        if 'to' in arguments:
            setattr(options, 'to', arguments['to'])
        if 'since' in arguments:
            setattr(options, 'since', arguments['since'])
        
        # Handle grep as list
        if 'grep' in arguments and isinstance(arguments['grep'], list):
            setattr(options, 'grep', arguments['grep'])
        
        return options

    def list_available_tools(self) -> List[str]:
        """
        List all available tools.
        
        Returns:
            List of tool names
        """
        return list(self.TOOL_TO_HANDLER_MAP.keys())

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Dictionary containing tool information or None if not found
        """
        return self.TOOL_TO_HANDLER_MAP.get(tool_name)
