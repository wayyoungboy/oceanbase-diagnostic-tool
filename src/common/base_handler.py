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
