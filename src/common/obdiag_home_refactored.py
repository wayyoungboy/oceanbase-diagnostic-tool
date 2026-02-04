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
@file: obdiag_home_refactored.py
@desc: Refactored ObdiagHome using new infrastructure (example implementation)
"""

import os
from optparse import Values
from copy import copy
from src.common.context_manager import ContextManager
from src.common.ssh_connection_manager import SSHConnectionManager
from src.common.handler_factory import HandlerFactory
from src.common.config import ConfigManager, InnerConfigManager
from src.common.context import HandlerContext


class ObdiagHomeRefactored:
    """
    Refactored ObdiagHome using new infrastructure.

    This is an example implementation showing how to use the new managers
    to reduce responsibilities and improve maintainability.
    """

    def __init__(self, stdio=None, config_path=os.path.expanduser('~/.obdiag/config.yml'), inner_config_change_map=None, custom_config_env_list=None, config_password=None):
        """
        Initialize refactored ObdiagHome.

        Args:
            stdio: Stdio instance
            config_path: Config file path
            inner_config_change_map: Inner config change map
            custom_config_env_list: Custom config env list
            config_password: Config password
        """
        self.stdio = stdio
        self.cmds = []
        self.options = Values()
        self.namespaces = {}

        # Initialize managers
        self.inner_config_manager = InnerConfigManager(stdio=stdio, inner_config_change_map=inner_config_change_map)
        self.config_manager = ConfigManager(config_path, stdio, custom_config_env_list, config_password=config_password)

        # Initialize new infrastructure managers
        self.context_manager = ContextManager(stdio=stdio, config_manager=self.config_manager, inner_config_manager=self.inner_config_manager)
        self.ssh_manager = SSHConnectionManager()
        self.handler_factory = HandlerFactory()

        # Auto-discover handlers
        self.handler_factory.auto_discover("src.handler")

        # Setup stdio based on config
        self._setup_stdio()

    def _setup_stdio(self):
        """Setup stdio based on inner config"""
        if not self.stdio:
            return

        inner_config = self.inner_config_manager.config

        # Set error stream
        if inner_config.get("obdiag") and inner_config.get("obdiag").get("basic") and inner_config.get("obdiag").get("basic").get("print_type"):
            error_stream = inner_config.get("obdiag").get("logger").get("error_stream")
            self.stdio.set_err_stream(error_stream)

        # Set silent mode
        if inner_config.get("obdiag") and inner_config.get("obdiag").get("logger") and inner_config.get("obdiag").get("logger").get("silent") is not None:
            silent = inner_config.get("obdiag").get("logger").get("silent")
            self.stdio.set_silent(silent)

    def set_cmds(self, cmds):
        """Set commands"""
        self.cmds = cmds

    def set_options(self, options):
        """Set options"""
        self.options = options

    def create_context(self, handler_name: str, namespace: str, skip_cluster_conn: bool = False) -> HandlerContext:
        """
        Create handler context using context manager.

        Args:
            handler_name: Handler name
            namespace: Namespace name
            skip_cluster_conn: Whether to skip cluster connection

        Returns:
            HandlerContext instance
        """
        return self.context_manager.create_context(handler_name=handler_name, namespace=namespace, cmds=self.cmds, options=self.options, skip_cluster_conn=skip_cluster_conn)

    def get_handler(self, handler_name: str, context: HandlerContext, **kwargs):
        """
        Get handler instance using handler factory.

        Args:
            handler_name: Handler name
            context: Handler context
            **kwargs: Additional initialization parameters

        Returns:
            Handler instance
        """
        return self.handler_factory.create(handler_name, context, ssh_manager=self.ssh_manager, handler_factory=self.handler_factory, **kwargs)

    def setup_nodes_with_connections(self, context: HandlerContext, nodes: list, node_type: str = "observer") -> list:
        """
        Setup nodes with SSH connections.

        Args:
            context: Handler context
            nodes: List of node dictionaries
            node_type: Type of nodes

        Returns:
            List of nodes with connections attached
        """
        return self.ssh_manager.setup_nodes_with_connections(context, nodes, node_type)

    def cleanup(self):
        """Cleanup resources"""
        self.ssh_manager.cleanup()

    def close_all(self):
        """Close all connections"""
        self.ssh_manager.close_all()
