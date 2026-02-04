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
@file: context_manager.py
@desc: Context manager for creating and managing HandlerContext
"""

from optparse import Values
from src.common.context import HandlerContext
from src.common.config import ConfigManager


class ContextManager:
    """
    Manager for creating and managing HandlerContext instances.

    Provides unified context creation with proper configuration injection.
    """

    def __init__(self, stdio=None, config_manager=None, inner_config_manager=None):
        """
        Initialize context manager.

        Args:
            stdio: Stdio instance
            config_manager: ConfigManager instance
            inner_config_manager: InnerConfigManager instance
        """
        self.stdio = stdio
        self.config_manager = config_manager
        self.inner_config_manager = inner_config_manager

    def create_context(self, handler_name: str, namespace: str, cmds=None, options: Values = None, skip_cluster_conn: bool = False) -> HandlerContext:
        """
        Create HandlerContext with proper configuration.

        Args:
            handler_name: Handler name
            namespace: Namespace name
            cmds: Command list
            options: Options Values object
            skip_cluster_conn: Whether to skip cluster connection setup

        Returns:
            HandlerContext instance
        """
        if not self.config_manager:
            raise ValueError("ConfigManager is required")

        if skip_cluster_conn:
            return self._create_context_skip_cluster_conn(handler_name, namespace, cmds, options)
        else:
            return self._create_context(handler_name, namespace, cmds, options)

    def _create_context(self, handler_name: str, namespace: str, cmds=None, options: Values = None) -> HandlerContext:
        """Create context with cluster connection"""
        return HandlerContext(
            handler_name=handler_name,
            namespace=namespace,
            cluster_config=self.config_manager.get_ob_cluster_config,
            obproxy_config=self.config_manager.get_obproxy_config,
            ocp_config=self.config_manager.get_ocp_config,
            oms_config=self.config_manager.get_oms_config,
            cmd=cmds or [],
            options=options or Values(),
            stdio=self.stdio,
            inner_config=self.inner_config_manager.config if self.inner_config_manager else None,
        )

    def _create_context_skip_cluster_conn(self, handler_name: str, namespace: str, cmds=None, options: Values = None) -> HandlerContext:
        """Create context without cluster connection"""
        return HandlerContext(
            handler_name=handler_name,
            namespace=namespace,
            cluster_config=None,
            obproxy_config=None,
            ocp_config=None,
            oms_config=None,
            cmd=cmds or [],
            options=options or Values(),
            stdio=self.stdio,
            inner_config=self.inner_config_manager.config if self.inner_config_manager else None,
        )

    def create_simple_context(self, stdio=None) -> HandlerContext:
        """
        Create simple context with only stdio.

        Args:
            stdio: Stdio instance

        Returns:
            HandlerContext instance
        """
        return HandlerContext(stdio=stdio or self.stdio)
