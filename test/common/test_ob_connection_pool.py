#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: test_ob_connection_pool.py
@desc: Unit tests for OBConnectionPool
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from src.common.ob_connection_pool import OBConnectionPool
from src.common.obdiag_exception import OBDIAGDBConnException


class TestOBConnectionPool(unittest.TestCase):
    """Test cases for OBConnectionPool"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_context = Mock()
        self.mock_context.stdio = Mock()
        self.mock_context.stdio.verbose = Mock()
        self.mock_context.stdio.error = Mock()
        self.mock_context.stdio.warn = Mock()
        
        self.cluster_config = {
            "db_host": "127.0.0.1",
            "db_port": 2881,
            "tenant_sys": {
                "user": "root@sys",
                "password": "test_password"
            }
        }
    
    @patch('src.common.ob_connection_pool.OBConnector')
    def test_pool_initialization(self, mock_connector):
        """Test pool initialization"""
        mock_conn = Mock()
        mock_connector.return_value = mock_conn
        
        pool = OBConnectionPool(
            context=self.mock_context,
            cluster_config=self.cluster_config,
            max_size=5
        )
        
        self.assertEqual(pool.max_size, 5)
        self.assertEqual(pool.timeout, 30)
    
    @patch('src.common.ob_connection_pool.OBConnector')
    def test_get_connection(self, mock_connector):
        """Test getting connection from pool"""
        mock_conn = Mock()
        mock_conn.execute_sql = Mock(return_value=None)
        mock_connector.return_value = mock_conn
        
        pool = OBConnectionPool(
            context=self.mock_context,
            cluster_config=self.cluster_config,
            max_size=2
        )
        
        conn = pool.get_connection()
        self.assertIsNotNone(conn)
        mock_connector.assert_called()
    
    @patch('src.common.ob_connection_pool.OBConnector')
    def test_release_connection(self, mock_connector):
        """Test releasing connection back to pool"""
        mock_conn = Mock()
        mock_conn.execute_sql = Mock(return_value=None)
        mock_connector.return_value = mock_conn
        
        pool = OBConnectionPool(
            context=self.mock_context,
            cluster_config=self.cluster_config,
            max_size=2
        )
        
        conn = pool.get_connection()
        pool.release(conn)
        
        # Should be able to get connection again
        conn2 = pool.get_connection()
        self.assertIsNotNone(conn2)
    
    @patch('src.common.ob_connection_pool.OBConnector')
    def test_connection_context_manager(self, mock_connector):
        """Test connection context manager"""
        mock_conn = Mock()
        mock_conn.execute_sql = Mock(return_value=None)
        mock_connector.return_value = mock_conn
        
        pool = OBConnectionPool(
            context=self.mock_context,
            cluster_config=self.cluster_config,
            max_size=2
        )
        
        with pool.connection() as conn:
            self.assertIsNotNone(conn)
    
    @patch('src.common.ob_connection_pool.OBConnector')
    def test_health_check_failure(self, mock_connector):
        """Test health check detects dead connection"""
        mock_conn = Mock()
        mock_conn.execute_sql = Mock(side_effect=Exception("Connection dead"))
        mock_connector.return_value = mock_conn
        
        pool = OBConnectionPool(
            context=self.mock_context,
            cluster_config=self.cluster_config,
            max_size=2
        )
        
        # Get connection (will be marked as dead)
        conn = pool.get_connection()
        
        # Release dead connection - should create new one
        new_conn = Mock()
        new_conn.execute_sql = Mock(return_value=None)
        mock_connector.return_value = new_conn
        
        pool.release(conn)
        
        # Next get should create new connection
        conn2 = pool.get_connection()
        self.assertIsNotNone(conn2)


if __name__ == '__main__':
    unittest.main()
