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
@time: 2026/02/03
@file: base_handler.py
@desc: Unified base handler class for all handlers
"""

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, TYPE_CHECKING
from src.common.result_type import ObdiagResult
from src.common.context import HandlerContext
from src.common.config_accessor import ConfigAccessor
from src.common.ssh_connection_manager import SSHConnectionManager

if TYPE_CHECKING:
    from src.common.handler_factory import HandlerFactory


class BaseHandler(ABC):
    """
    Unified base class for all handlers.

    This class provides:
    - Unified initialization interface
    - Unified error handling
    - Common utility methods
    - Standard return type (ObdiagResult)

    All handlers should inherit from this class and implement:
    - handle(): Main handler logic
    """

    def __init__(self):
        """Constructor: Only do basic initialization"""
        self.context: Optional[HandlerContext] = None
        self.stdio = None
        self._initialized = False
        self.config: Optional[ConfigAccessor] = None
        self.ssh_manager: Optional[SSHConnectionManager] = None
        self.handler_factory: Optional['HandlerFactory'] = None

    def init(self, context: HandlerContext, ssh_manager: Optional[SSHConnectionManager] = None, handler_factory: Optional['HandlerFactory'] = None, **kwargs) -> 'BaseHandler':
        """
        Initialize handler with context and options.

        Args:
            context: Handler context containing config, stdio, etc.
            ssh_manager: SSH connection manager (optional)
            handler_factory: Handler factory (optional)
            **kwargs: Additional initialization parameters

        Returns:
            self: Support method chaining
        """
        self.context = context
        self.stdio = context.stdio if context else None
        self.ssh_manager = ssh_manager
        self.handler_factory = handler_factory

        # Initialize config accessor
        if context:
            self.config = ConfigAccessor(config_manager=context.cluster_config if hasattr(context, 'cluster_config') else None, inner_config_manager=context.inner_config if hasattr(context, 'inner_config') else None)

        self._initialized = True

        # Call subclass initialization hook
        self._init(**kwargs)

        return self

    def _init(self, **kwargs):
        """
        Subclass initialization hook.

        Override this method to perform subclass-specific initialization.

        Args:
            **kwargs: Additional initialization parameters
        """
        pass

    # ========== Configuration Access Properties ==========
    # These properties provide convenient access to common configuration values
    # All handlers should use these properties instead of direct config access

    @property
    def file_number_limit(self) -> int:
        """Get file number limit from config."""
        if self.config:
            return self.config.get_int('obdiag.basic.file_number_limit', 20)
        elif self.context and self.context.inner_config:
            basic_config = self.context.inner_config.get('obdiag', {}).get('basic', {})
            return int(basic_config.get('file_number_limit', 20))
        return 20

    @property
    def gather_thread_nums(self) -> int:
        """Get gather thread numbers from config."""
        if self.config:
            return self.config.get_int('gather.thread_nums', 4)
        elif self.context and self.context.inner_config:
            gather_config = self.context.inner_config.get('gather', {})
            return int(gather_config.get('thread_nums', 4))
        return 4

    @property
    def sql_timeout(self) -> int:
        """Get SQL timeout from config (in seconds)."""
        if self.config:
            return self.config.get_int('obdiag.basic.sql_timeout', 100)
        elif self.context and self.context.inner_config:
            basic_config = self.context.inner_config.get('obdiag', {}).get('basic', {})
            return int(basic_config.get('sql_timeout', 100))
        return 100

    @abstractmethod
    def handle(self) -> ObdiagResult:
        """
        Execute handler logic.

        This method should be implemented by subclasses.

        Returns:
            ObdiagResult: Execution result
        """
        pass

    def _handle_error(self, error: Exception, error_code: int = ObdiagResult.SERVER_ERROR_CODE) -> ObdiagResult:
        """
        Unified error handling.

        Args:
            error: Exception that occurred
            error_code: Error code to return (default: SERVER_ERROR_CODE)

        Returns:
            ObdiagResult: Error result
        """
        handler_name = self.__class__.__name__
        error_msg = f"{handler_name} failed: {str(error)}"

        if self.stdio:
            self.stdio.error(error_msg)
            self.stdio.exception("")

        return ObdiagResult(error_code, error_data=error_msg)

    def _validate_initialized(self):
        """
        Validate that handler has been initialized.

        Raises:
            RuntimeError: If handler is not initialized
        """
        if not self._initialized:
            raise RuntimeError(f"{self.__class__.__name__} has not been initialized. " "Call init(context, **kwargs) first.")

    def _get_option(self, name: str, default: Any = None) -> Any:
        """
        Get option value from context.

        Args:
            name: Option name
            default: Default value if option not found

        Returns:
            Option value or default
        """
        if not self.context or not self.context.options:
            return default

        return getattr(self.context.options, name, default)

    def _get_variable(self, name: str, default: Any = None) -> Any:
        """
        Get variable value from context.

        Args:
            name: Variable name
            default: Default value if variable not found

        Returns:
            Variable value or default
        """
        if not self.context:
            return default

        return self.context.get_variable(name, default=default)

    def _set_variable(self, name: str, value: Any):
        """
        Set variable value in context.

        Args:
            name: Variable name
            value: Variable value
        """
        if self.context:
            self.context.set_variable(name, value)

    def _log_verbose(self, message: str):
        """Log verbose message"""
        if self.stdio:
            self.stdio.verbose(message)

    def _log_info(self, message: str):
        """Log info message"""
        if self.stdio:
            self.stdio.print(message)

    def _log_warn(self, message: str):
        """Log warning message"""
        if self.stdio:
            self.stdio.warn(message)

    def _log_error(self, message: str):
        """Log error message"""
        if self.stdio:
            self.stdio.error(message)

    def get_ssh_connection(self, node: Dict):
        """
        Get SSH connection for node using connection manager.

        Args:
            node: Node configuration dictionary

        Returns:
            SSH client instance
        """
        if not self.ssh_manager:
            # Fallback to direct creation if manager not available
            from src.common.ssh_client.ssh import SshClient

            return SshClient(self.context, node)

        return self.ssh_manager.get_connection(self.context, node)

    def return_ssh_connection(self, client):
        """
        Return SSH connection to pool.

        Args:
            client: SSH client instance
        """
        if self.ssh_manager:
            self.ssh_manager.return_connection(client)

    # ========== Common Template Methods ==========
    # These methods eliminate code duplication across handlers

    def _init_time_range(self):
        """
        Initialize time range from options (from/to/since → timestamp).
        
        Sets:
            self.from_time: Start timestamp (microseconds)
            self.to_time: End timestamp (microseconds)
            self.from_time_str: Start time string
            self.to_time_str: End time string
        """
        from src.common.tool import TimeUtils
        
        from_opt = self._get_option('from')
        to_opt = self._get_option('to')
        since_opt = self._get_option('since')
        
        if from_opt and to_opt:
            from_dt = TimeUtils.parse_time_str(from_opt)
            to_dt = TimeUtils.parse_time_str(to_opt)
            # Convert datetime to microseconds timestamp
            self.from_time = int(from_dt.timestamp() * 1000000)
            self.to_time = int(to_dt.timestamp() * 1000000)
            self.from_time_str = from_opt
            self.to_time_str = to_opt
        elif since_opt:
            self.to_time = TimeUtils.get_current_us_timestamp()
            self.from_time = TimeUtils.parse_since(since_opt, self.to_time)
            self.from_time_str = TimeUtils.timestamp_to_str(self.from_time)
            self.to_time_str = TimeUtils.timestamp_to_str(self.to_time)
        else:
            self._log_warn("No time range specified, using default (last 30 minutes)")
            self.to_time = TimeUtils.get_current_us_timestamp()
            # 30 minutes = 30 * 60 * 1000000 microseconds
            self.from_time = self.to_time - 30 * 60 * 1000000
            self.from_time_str = TimeUtils.timestamp_to_str(self.from_time)
            self.to_time_str = TimeUtils.timestamp_to_str(self.to_time)

    def _init_store_dir(self, default: str = './') -> str:
        """
        Initialize store directory from options.
        
        Args:
            default: Default directory path
            
        Returns:
            Absolute path to store directory (created if not exists)
        """
        import os
        
        store_dir = self._get_option('store_dir', default)
        store_dir = os.path.abspath(os.path.expanduser(store_dir))
        
        if not os.path.exists(store_dir):
            self._log_warn(f'Directory {store_dir} does not exist, creating...')
            os.makedirs(store_dir, exist_ok=True)
        
        return store_dir

    def _init_db_connector(self):
        """
        Initialize database connector from cluster config.
        
        Returns:
            OBConnector instance
            
        Raises:
            ConfigException: If cluster config or credentials not found
        """
        from src.common.ob_connector import OBConnector
        from src.common.exceptions import ConfigException
        
        if not self.context:
            raise ConfigException("Handler context not available")
        
        ob_cluster = self.context.cluster_config
        if not ob_cluster:
            raise ConfigException("OB cluster configuration not found")
        
        tenant_sys = ob_cluster.get("tenant_sys", {})
        if not tenant_sys.get("user") or not tenant_sys.get("password"):
            raise ConfigException("Sys tenant credentials not configured")
        
        return OBConnector(
            context=self.context,
            ip=ob_cluster.get("db_host"),
            port=ob_cluster.get("db_port"),
            username=tenant_sys.get("user"),
            password=tenant_sys.get("password"),
            timeout=self.sql_timeout * 1000,  # Convert to milliseconds
        )

    def _generate_summary_table(self, headers: list, rows: list, title: Optional[str] = None) -> str:
        """
        Generate summary table using tabulate.
        
        Args:
            headers: Table headers
            rows: Table rows (list of tuples or lists)
            title: Optional title to display before table
            
        Returns:
            Formatted table string (including title if provided)
        """
        from tabulate import tabulate
        
        table_str = tabulate(rows, headers=headers, tablefmt="grid", showindex=False)
        
        if title:
            result = f"\n{title}\n{table_str}"
            self._log_info(result)
        else:
            result = f"\n{table_str}"
            self._log_info(result)
        
        return result

    def _iterate_nodes(self, nodes: list, callback):
        """
        Iterate over nodes with unified SSH connection management.
        
        Args:
            nodes: List of node configuration dictionaries
            callback: Function(node, ssh_client) -> result
            
        Returns:
            List of callback results
        """
        results = []
        
        for node in nodes:
            ssh_client = self.get_ssh_connection(node)
            if ssh_client is None:
                self._log_warn(f"SSH not available for node {node.get('ip', 'unknown')}, skipping")
                continue
            
            try:
                result = callback(node, ssh_client)
                results.append(result)
            except Exception as e:
                self._log_error(f"Error on node {node.get('ip', 'unknown')}: {e}")
            finally:
                self.return_ssh_connection(ssh_client)
        
        return results
