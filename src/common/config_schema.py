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
@file: config_schema.py
@desc: Configuration schema validation
"""

from typing import Dict, Any, List, Optional
from src.common.exceptions import ConfigException, ValidationException


def validate_config(config_data: Dict[str, Any], strict: bool = False) -> List[str]:
    """
    Validate configuration data against schema.

    Args:
        config_data: Configuration dictionary to validate
        strict: If True, raise exception on validation failure; if False, return errors list

    Returns:
        List of validation error messages (empty if valid)

    Raises:
        ValidationException: If strict=True and validation fails
    """
    errors = []

    # Validate obcluster section
    if 'obcluster' in config_data:
        errors.extend(_validate_obcluster(config_data['obcluster']))

    # Validate obproxy section (optional)
    if 'obproxy' in config_data:
        errors.extend(_validate_obproxy(config_data['obproxy']))

    # Validate ocp section (optional)
    if 'ocp' in config_data:
        errors.extend(_validate_ocp(config_data['ocp']))

    if strict and errors:
        raise ValidationException(f"Configuration validation failed: {'; '.join(errors)}", context={'errors': errors})

    return errors


def _validate_obcluster(obcluster: Dict[str, Any]) -> List[str]:
    """Validate obcluster configuration."""
    errors = []

    # Required fields
    required_fields = ['db_host', 'db_port', 'tenant_sys']
    for field in required_fields:
        if field not in obcluster:
            errors.append(f"obcluster.{field} is required")

    # Validate db_port
    if 'db_port' in obcluster:
        try:
            port = int(obcluster['db_port'])
            if not (1 <= port <= 65535):
                errors.append(f"obcluster.db_port must be between 1 and 65535, got {port}")
        except (ValueError, TypeError):
            errors.append(f"obcluster.db_port must be an integer, got {obcluster['db_port']}")

    # Validate tenant_sys
    if 'tenant_sys' in obcluster:
        tenant_sys = obcluster['tenant_sys']
        if not isinstance(tenant_sys, dict):
            errors.append("obcluster.tenant_sys must be a dictionary")
        else:
            if 'user' not in tenant_sys or not tenant_sys.get('user'):
                errors.append("obcluster.tenant_sys.user is required")
            if 'password' not in tenant_sys:
                errors.append("obcluster.tenant_sys.password is required")

    # Validate servers
    if 'servers' in obcluster:
        servers = obcluster['servers']
        if not isinstance(servers, dict):
            errors.append("obcluster.servers must be a dictionary")
        elif 'nodes' in servers:
            nodes = servers['nodes']
            if not isinstance(nodes, list):
                errors.append("obcluster.servers.nodes must be a list")
            else:
                for i, node in enumerate(nodes):
                    if not isinstance(node, dict):
                        errors.append(f"obcluster.servers.nodes[{i}] must be a dictionary")
                    elif 'ip' not in node or not node.get('ip'):
                        errors.append(f"obcluster.servers.nodes[{i}].ip is required")

    return errors


def _validate_obproxy(obproxy: Dict[str, Any]) -> List[str]:
    """Validate obproxy configuration."""
    errors = []

    # servers is optional but if present, must be valid
    if 'servers' in obproxy:
        servers = obproxy['servers']
        if not isinstance(servers, dict):
            errors.append("obproxy.servers must be a dictionary")
        elif 'nodes' in servers:
            nodes = servers['nodes']
            if not isinstance(nodes, list):
                errors.append("obproxy.servers.nodes must be a list")
            else:
                for i, node in enumerate(nodes):
                    if not isinstance(node, dict):
                        errors.append(f"obproxy.servers.nodes[{i}] must be a dictionary")
                    elif 'ip' not in node or not node.get('ip'):
                        errors.append(f"obproxy.servers.nodes[{i}].ip is required")

    return errors


def _validate_ocp(ocp: Dict[str, Any]) -> List[str]:
    """Validate OCP configuration."""
    errors = []

    if 'login' in ocp:
        login = ocp['login']
        if not isinstance(login, dict):
            errors.append("ocp.login must be a dictionary")
        else:
            if 'url' not in login or not login.get('url'):
                errors.append("ocp.login.url is required")
            if 'user' not in login or not login.get('user'):
                errors.append("ocp.login.user is required")
            if 'password' not in login:
                errors.append("ocp.login.password is required")

    return errors
