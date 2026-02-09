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
@file: test_output_formatter.py
@desc: Unit tests for OutputFormatter
"""

import unittest
import json
import sys
from io import StringIO
from src.common.output_formatter import OutputFormatter


class TestOutputFormatter(unittest.TestCase):
    """Test cases for OutputFormatter"""
    
    def test_json_format(self):
        """Test JSON output format"""
        formatter = OutputFormatter(format='json')
        data = {'key': 'value', 'number': 123}
        
        output = StringIO()
        formatter.stream = output
        formatter.output(data)
        
        result = json.loads(output.getvalue())
        self.assertEqual(result['key'], 'value')
        self.assertEqual(result['number'], 123)
    
    def test_table_format(self):
        """Test table output format"""
        formatter = OutputFormatter(format='table')
        data = [{'name': 'test', 'value': 123}]
        
        output = StringIO()
        formatter.stream = output
        formatter.output(data)
        
        result = output.getvalue()
        self.assertIn('test', result)
        self.assertIn('123', result)
    
    def test_quiet_mode(self):
        """Test quiet mode suppresses table output"""
        formatter = OutputFormatter(format='table', quiet=True)
        data = {'key': 'value'}
        
        output = StringIO()
        formatter.stream = output
        formatter.output(data)
        
        # Table output should be suppressed in quiet mode
        self.assertEqual(len(output.getvalue()), 0)
    
    def test_csv_format(self):
        """Test CSV output format"""
        formatter = OutputFormatter(format='csv')
        data = [{'name': 'test', 'value': 123}]
        
        output = StringIO()
        formatter.stream = output
        formatter.output(data)
        
        result = output.getvalue()
        self.assertIn('test', result)
        self.assertIn('123', result)


if __name__ == '__main__':
    unittest.main()
