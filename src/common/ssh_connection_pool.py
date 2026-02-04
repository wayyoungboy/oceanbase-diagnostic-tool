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
@file: ssh_connection_pool.py
@desc: SSH connection pool for connection reuse
"""

import threading
from typing import Dict, Optional, Tuple
from collections import deque
from contextlib import contextmanager
from src.common.ssh_client.ssh import SshClient
from src.common.context import HandlerContext


class SSHConnectionPool:
    """
    SSH connection pool for reusing connections.

    This pool manages SSH connections to avoid creating new connections
    for each operation, improving performance and reducing overhead.
    """

    def __init__(self, max_connections_per_node: int = 5, idle_timeout: int = 300):
        """
        Initialize SSH connection pool.

        Args:
            max_connections_per_node: Maximum connections per node (default: 5)
            idle_timeout: Idle timeout in seconds before closing connection (default: 300)
        """
        self.max_connections_per_node = max_connections_per_node
        self.idle_timeout = idle_timeout
        self._pools: Dict[str, deque] = {}  # node_key -> deque of connections
        self._lock = threading.Lock()
        self._connection_info: Dict[str, Tuple[SshClient, float]] = {}  # connection_id -> (client, last_used_time)
        self._node_keys: Dict[str, str] = {}  # connection_id -> node_key

    def _get_node_key(self, node: Dict) -> str:
        """
        Generate unique key for node.

        Args:
            node: Node configuration dictionary

        Returns:
            Unique node key
        """
        ssh_type = node.get("ssh_type", "remote")
        if ssh_type == "local":
            return "local"
        elif ssh_type == "docker":
            container = node.get("container_name", "")
            return f"docker:{container}"
        elif ssh_type == "kubernetes":
            namespace = node.get("namespace", "")
            pod = node.get("pod_name", "")
            return f"k8s:{namespace}:{pod}"
        else:
            ip = node.get("ip", "")
            port = node.get("ssh_port", 22)
            return f"ssh:{ip}:{port}"

    def _get_connection_id(self, client: SshClient) -> str:
        """
        Generate unique ID for connection.

        Args:
            client: SSH client instance

        Returns:
            Unique connection ID
        """
        return id(client)

    def get_connection(self, context: HandlerContext, node: Dict) -> SshClient:
        """
        Get SSH connection from pool or create new one.

        Args:
            context: Handler context
            node: Node configuration dictionary

        Returns:
            SSH client instance
        """
        node_key = self._get_node_key(node)

        with self._lock:
            # Try to get connection from pool
            if node_key in self._pools and self._pools[node_key]:
                client = self._pools[node_key].popleft()
                connection_id = self._get_connection_id(client)

                # Update last used time
                if connection_id in self._connection_info:
                    self._connection_info[connection_id] = (client, self._current_time())

                return client

            # Create new connection
            client = SshClient(context, node)
            connection_id = self._get_connection_id(client)
            self._connection_info[connection_id] = (client, self._current_time())
            self._node_keys[connection_id] = node_key

            return client

    def return_connection(self, client: SshClient):
        """
        Return connection to pool.

        Args:
            client: SSH client instance to return
        """
        connection_id = self._get_connection_id(client)

        with self._lock:
            if connection_id not in self._node_keys:
                # Connection not managed by pool, just ignore
                return

            node_key = self._node_keys[connection_id]

            # Check if pool is full
            if node_key not in self._pools:
                self._pools[node_key] = deque()

            if len(self._pools[node_key]) >= self.max_connections_per_node:
                # Pool is full, close connection
                self._close_connection(client, connection_id)
                return

            # Return to pool
            self._pools[node_key].append(client)
            self._connection_info[connection_id] = (client, self._current_time())

    def _close_connection(self, client: SshClient, connection_id: str):
        """
        Close connection and remove from pool.

        Args:
            client: SSH client instance
            connection_id: Connection ID
        """
        try:
            # Close connection if it has close method
            if hasattr(client, 'close'):
                client.close()
            elif hasattr(client, 'client') and hasattr(client.client, 'close'):
                client.client.close()
        except Exception:
            pass

        # Remove from tracking
        if connection_id in self._connection_info:
            del self._connection_info[connection_id]
        if connection_id in self._node_keys:
            del self._node_keys[connection_id]

    def cleanup_idle_connections(self):
        """Clean up idle connections that exceed timeout"""
        current_time = self._current_time()

        with self._lock:
            connections_to_close = []

            for connection_id, (client, last_used_time) in list(self._connection_info.items()):
                if current_time - last_used_time > self.idle_timeout:
                    connections_to_close.append((client, connection_id))

            for client, connection_id in connections_to_close:
                node_key = self._node_keys.get(connection_id)
                if node_key and node_key in self._pools:
                    # Remove from pool
                    try:
                        self._pools[node_key].remove(client)
                    except ValueError:
                        pass

                self._close_connection(client, connection_id)

    def close_all(self):
        """Close all connections in pool"""
        with self._lock:
            all_clients = []

            # Collect all clients
            for pool in self._pools.values():
                all_clients.extend(list(pool))

            # Close all
            for client in all_clients:
                connection_id = self._get_connection_id(client)
                self._close_connection(client, connection_id)

            # Clear pools
            self._pools.clear()
            self._connection_info.clear()
            self._node_keys.clear()

    @contextmanager
    def connection(self, context: HandlerContext, node: Dict):
        """
        Context manager for SSH connection.

        Usage:
            with pool.connection(context, node) as client:
                result = client.exec_cmd("ls")

        Args:
            context: Handler context
            node: Node configuration dictionary

        Yields:
            SSH client instance
        """
        client = self.get_connection(context, node)
        try:
            yield client
        finally:
            self.return_connection(client)

    def _current_time(self) -> float:
        """Get current time in seconds"""
        import time

        return time.time()

    def get_stats(self) -> Dict:
        """
        Get pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            stats = {"total_pools": len(self._pools), "total_connections": sum(len(pool) for pool in self._pools.values()), "pools": {}}

            for node_key, pool in self._pools.items():
                stats["pools"][node_key] = {"connections": len(pool), "max_connections": self.max_connections_per_node}

            return stats
