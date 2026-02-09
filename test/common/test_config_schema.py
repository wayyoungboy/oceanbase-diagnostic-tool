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
@file: test_config_schema.py
@desc: Unit tests for configuration schema validation
"""

import unittest
from src.common.config_schema import validate_config, ValidationException


class TestConfigSchema(unittest.TestCase):
    """Test cases for configuration schema validation"""

    def test_valid_obcluster_config(self):
        """Test valid obcluster configuration"""
        config = {'obcluster': {'db_host': '127.0.0.1', 'db_port': 2881, 'tenant_sys': {'user': 'root@sys', 'password': 'password'}, 'servers': {'nodes': [{'ip': '192.168.1.1'}]}}}

        errors = validate_config(config)
        self.assertEqual(len(errors), 0)

    def test_missing_required_field(self):
        """Test missing required field"""
        config = {
            'obcluster': {
                'db_host': '127.0.0.1',
                # Missing db_port and tenant_sys
            }
        }

        errors = validate_config(config)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any('db_port' in e for e in errors))
        self.assertTrue(any('tenant_sys' in e for e in errors))

    def test_invalid_db_port(self):
        """Test invalid db_port value"""
        config = {'obcluster': {'db_host': '127.0.0.1', 'db_port': 99999, 'tenant_sys': {'user': 'root@sys', 'password': 'password'}}}  # Invalid port

        errors = validate_config(config)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any('db_port' in e and '65535' in e for e in errors))

    def test_missing_tenant_sys_credentials(self):
        """Test missing tenant_sys credentials"""
        config = {
            'obcluster': {
                'db_host': '127.0.0.1',
                'db_port': 2881,
                'tenant_sys': {
                    # Missing user and password
                },
            }
        }

        errors = validate_config(config)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any('user' in e for e in errors))

    def test_strict_mode_raises_exception(self):
        """Test strict mode raises exception"""
        config = {
            'obcluster': {
                'db_host': '127.0.0.1',
                # Missing required fields
            }
        }

        with self.assertRaises(ValidationException):
            validate_config(config, strict=True)


if __name__ == '__main__':
    unittest.main()
