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
@file: error_codes.py
@desc: Error code registry for user-friendly error messages
"""

from typing import Dict, List, Optional


ERROR_REGISTRY: Dict[str, Dict[str, any]] = {
    # ========== Connection Errors (1000-1999) ==========
    'OBDIAG-1001': {
        'category': 'connection',
        'message': 'Cannot connect to OceanBase cluster at {host}:{port}',
        'suggestion': [
            'Check if the OceanBase cluster is running',
            'Verify the host and port in config file (~/.obdiag/config.yml)',
            'Test connectivity: telnet {host} {port}',
        ],
        'doc_link': 'https://oceanbase.github.io/obdiag/troubleshooting/connection',
    },
    'OBDIAG-1002': {
        'category': 'connection',
        'message': 'SSH authentication failed for {user}@{host}',
        'suggestion': [
            'Check SSH credentials in config file (~/.obdiag/config.yml)',
            'Verify SSH key permissions: chmod 600 ~/.ssh/id_rsa',
            'Test manually: ssh {user}@{host}',
        ],
    },
    'OBDIAG-1003': {
        'category': 'connection',
        'message': 'SSH connection timeout to {host}:{port} after {timeout}s',
        'suggestion': [
            'Check network connectivity between obdiag host and target',
            'Verify firewall rules allow SSH traffic',
            'Try increasing timeout in config: ssh_client.connect_timeout',
        ],
    },
    'OBDIAG-1004': {
        'category': 'connection',
        'message': 'Database connection pool exhausted (max={max}, timeout={timeout}s)',
        'suggestion': [
            'Increase connection pool size in configuration',
            'Check for connection leaks in handlers',
            'Reduce concurrent operations',
        ],
    },
    # ========== Configuration Errors (2000-2999) ==========
    'OBDIAG-2001': {
        'category': 'config',
        'message': 'Configuration file not found: {path}',
        'suggestion': [
            'Run "obdiag config generate --interactive" to create one',
            'Or specify a config file: obdiag -c /path/to/config.yml',
        ],
    },
    'OBDIAG-2002': {
        'category': 'config',
        'message': 'Missing required config field: {field}',
        'suggestion': [
            'Edit config file and add the missing field',
            'Run "obdiag config check" to validate your configuration',
        ],
    },
    'OBDIAG-2003': {
        'category': 'config',
        'message': 'Invalid config value for {field}: {value}',
        'suggestion': [
            'Check the expected format in documentation',
            'Run "obdiag config check" for detailed validation',
        ],
    },
    # ========== Execution Errors (3000-3999) ==========
    'OBDIAG-3001': {
        'category': 'execution',
        'message': 'Check task "{task}" failed on node {node}: {error}',
        'suggestion': [
            'Check node status and connectivity',
            'Run with -v flag for detailed output',
        ],
    },
    'OBDIAG-3002': {
        'category': 'execution',
        'message': 'Gather operation timed out after {timeout}s',
        'suggestion': [
            'Try narrowing the time range with --from and --to',
            'Check if target nodes are responsive',
        ],
    },
    'OBDIAG-3003': {
        'category': 'execution',
        'message': 'Handler "{handler}" execution failed: {error}',
        'suggestion': [
            'Check handler logs for details',
            'Verify configuration is correct',
            'Run with -v flag for verbose output',
        ],
    },
    # ========== SQL Errors (4000-4999) ==========
    'OBDIAG-4001': {
        'category': 'sql',
        'message': 'SQL execution failed: {error}',
        'suggestion': [
            'Check database connection status',
            'Verify sys tenant credentials in config',
            'Run "obdiag config check" to validate connection',
        ],
    },
    'OBDIAG-4002': {
        'category': 'sql',
        'message': 'SQL query timeout after {timeout}s',
        'suggestion': [
            'Query may be too complex or database is overloaded',
            'Try increasing sql_timeout in configuration',
        ],
    },
    # ========== File System Errors (5000-5999) ==========
    'OBDIAG-5001': {
        'category': 'filesystem',
        'message': 'Cannot create directory: {path}',
        'suggestion': [
            'Check directory permissions',
            'Verify disk space is available',
        ],
    },
    'OBDIAG-5002': {
        'category': 'filesystem',
        'message': 'File not found: {path}',
        'suggestion': [
            'Verify the file path is correct',
            'Check if file exists on the target node',
        ],
    },
}


def get_error_info(error_code: str) -> Optional[Dict[str, any]]:
    """
    Get error information by error code.

    Args:
        error_code: Error code (e.g., 'OBDIAG-1001')

    Returns:
        Error information dictionary or None if not found
    """
    return ERROR_REGISTRY.get(error_code)


def format_error_message(error_code: str, **kwargs) -> str:
    """
    Format error message with context variables.

    Args:
        error_code: Error code
        **kwargs: Context variables for message formatting

    Returns:
        Formatted error message
    """
    error_info = get_error_info(error_code)
    if not error_info:
        return f"Unknown error: {error_code}"

    message = error_info['message']
    try:
        return message.format(**kwargs)
    except KeyError as e:
        return f"{message} (formatting error: missing {e})"


def get_error_suggestions(error_code: str) -> List[str]:
    """
    Get error suggestions by error code.

    Args:
        error_code: Error code

    Returns:
        List of suggestion strings
    """
    error_info = get_error_info(error_code)
    if not error_info:
        return []

    return error_info.get('suggestion', [])
