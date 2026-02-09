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
@file: config_options_parser.py
@desc: Configuration options parser utility (extracted from tool.py)
"""


class ConfigOptionsParserUtil(object):
    def __init__(self):
        self.config_dict = {}
        self.key_mapping = {
            'db_host': 'obcluster.db_host',
            'db_port': 'obcluster.db_port',
            'tenant_sys.user': 'obcluster.tenant_sys.user',
            'tenant_sys.password': 'obcluster.tenant_sys.password',
            'ssh_username': 'obcluster.servers.global.ssh_username',
            'ssh_password': 'obcluster.servers.global.ssh_password',
            'ssh_port': 'obcluster.servers.global.ssh_port',
            'home_path': 'obcluster.servers.global.home_path',
            'obproxy_home_path': 'obproxy.servers.global.home_path',
        }

    def set_nested_value(self, d, keys, value):
        """Recursively set the value in a nested dictionary."""
        if len(keys) > 1:
            if 'nodes' in keys[0]:
                try:
                    # Handle nodes
                    parts = keys[0].split('[')
                    base_key = parts[0]
                    index = int(parts[1].rstrip(']'))
                    if base_key not in d:
                        d[base_key] = []
                    while len(d[base_key]) <= index:
                        d[base_key].append({})
                    self.set_nested_value(d[base_key][index], keys[1:], value)
                except (IndexError, ValueError) as e:
                    raise ValueError(f"Invalid node index in key '{keys[0]}'") from e
            else:
                if keys[0] not in d:
                    d[keys[0]] = {}
                d[keys[0]] = self.set_nested_value(d[keys[0]], keys[1:], value)
        else:
            d[keys[0]] = value
        return d

    def parse_config(self, input_array):
        for item in input_array:
            try:
                key, value = item.split('=', 1)
                # Map short keys to full keys if needed
                if key in self.key_mapping:
                    key = self.key_mapping[key]
                keys = key.split('.')
                self.set_nested_value(self.config_dict, keys, value)
            except ValueError:
                raise ValueError(f"Invalid input format for item '{item}'")

        self.config_dict = self.add_default_values(self.config_dict)
        return self.config_dict

    def add_default_values(self, d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == 'login':
                    if 'password' not in v:
                        v['password'] = ''
                elif k == 'tenant_sys':
                    if 'password' not in v:
                        v['password'] = ''
                elif k == 'global':
                    if 'ssh_username' not in v:
                        v['ssh_username'] = ''
                    if 'ssh_password' not in v:
                        v['ssh_password'] = ''
                elif k == 'servers':
                    # Ensure 'nodes' is present and initialized as an empty list
                    if 'nodes' not in v:
                        v['nodes'] = []
                    if 'global' not in v:
                        v['global'] = {}
                    self.add_default_values(v['global'])
                    for node in v['nodes']:
                        if isinstance(node, dict):
                            self.add_default_values(node)
                elif isinstance(v, dict):
                    self.add_default_values(v)
                elif isinstance(v, list):
                    for node in v:
                        if isinstance(node, dict):
                            self.add_default_values(node)
        return d
