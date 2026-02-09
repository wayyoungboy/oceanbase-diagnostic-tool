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
@file: string_utils.py
@desc: String utility functions (extracted from tool.py)
"""

import re
import copy
import datetime
import string
import random


class StringUtils(object):

    @staticmethod
    def parse_mysql_conn(cli_conn_str, stdio=None):
        db_info = {}
        # 处理密码选项，注意区分短选项和长选项的密码
        password_pattern = re.compile(r'(-p|--password=)([^ ]*)')
        password_match = password_pattern.search(cli_conn_str)
        if password_match:
            password = password_match.group(2)
            # 如果'-p'后面没有跟具体值，则设为''
            db_info['password'] = password if password else ''
            # 去除密码部分，避免后续解析出错
            cli_conn_str = cli_conn_str[: password_match.start()] + cli_conn_str[password_match.end() :].strip()

        # 模式匹配短选项
        short_opt_pattern = re.compile(r'-([hPuD])(\S*)')
        for match in short_opt_pattern.finditer(cli_conn_str):
            opt, value = match.groups()
            if opt == 'h':
                db_info['host'] = value
            elif opt == 'u':
                db_info['user'] = value
            elif opt == 'P':
                try:
                    db_info['port'] = int(value)
                except ValueError:
                    if stdio:
                        print("Invalid port number.")
                    return False
            elif opt == 'D':
                db_info['database'] = value

        # 长选项处理
        long_opt_pattern = re.compile(r'--(\w+)=([^ ]+)')
        for match in long_opt_pattern.finditer(cli_conn_str):
            opt, value = match.groups()
            if opt in ['host', 'user', 'port', 'dbname', 'database']:
                db_info[opt if opt != 'dbname' else 'database'] = value

        # 最后一个参数处理，如果未指定数据库名且最后的参数不是选项，则认为是数据库名
        parts = cli_conn_str.split()
        if parts and parts[-1][0] != '-' and 'database' not in db_info:
            db_info['database'] = parts[-1]

        return db_info

    @staticmethod
    def validate_db_info(db_info, stdio=None):
        required_keys = {'database', 'host', 'user', 'port'}
        if not required_keys.issubset(db_info.keys()):
            return False
        if not isinstance(db_info['port'], int):
            return False
        for key, value in db_info.items():
            if key != 'port' and not isinstance(value, str):
                return False
        return True

    @staticmethod
    def parse_env(env_string, stdio=None):
        env_dict = {}
        inner_str = env_string[1:-1].strip()
        pairs = inner_str.split(',')
        for pair in pairs:
            pair = pair.strip()
            key_value = pair.split('=', 1)
            if len(key_value) == 2:
                key, value = key_value
                key = key.strip()
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                env_dict[key] = value
        return env_dict

    @staticmethod
    def parse_env_display(env_list):
        env_dict = {}
        if not env_list:
            return {}
        for env_string in env_list:
            # 分割键和值
            key_value = env_string.split('=', 1)
            if len(key_value) == 2:
                key, value = key_value
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                env_dict[key.strip()] = value.strip()
        return env_dict

    @staticmethod
    def build_db_info_from_env(env_dict, stdio=None):
        """
        Build db_info dictionary from env_dict containing host, port, user, password, database.
        This replaces the old db_connect string parsing to avoid special character issues.
        """
        db_info = {}
        if 'host' in env_dict:
            db_info['host'] = env_dict['host']
        if 'port' in env_dict:
            try:
                db_info['port'] = int(env_dict['port'])
            except (ValueError, TypeError):
                if stdio:
                    stdio.error("Invalid port number: {0}".format(env_dict['port']))
                return None
        if 'user' in env_dict:
            db_info['user'] = env_dict['user']
        if 'password' in env_dict:
            db_info['password'] = env_dict['password']
        elif 'pwd' in env_dict:
            # Support 'pwd' as alias for 'password'
            db_info['password'] = env_dict['pwd']
        else:
            db_info['password'] = ''
        if 'database' in env_dict:
            db_info['database'] = env_dict['database']
        elif 'db' in env_dict:
            # Support 'db' as alias for 'database'
            db_info['database'] = env_dict['db']

        return db_info

    @staticmethod
    def extract_parameters(query_template):
        # 使用正则表达式查找占位符
        pattern = re.compile(r'#\{(\w+)\}')
        parameters = pattern.findall(query_template)
        return parameters

    @staticmethod
    def replace_parameters(query_template, params):
        # 使用正则表达式查找占位符
        pattern = re.compile(r'#\{(\w+)\}')

        # 定义替换函数
        def replacer(match):
            key = match.group(1)
            return str(params.get(key, match.group(0)))

        # 替换占位符
        query = pattern.sub(replacer, query_template)
        return query

    @staticmethod
    def get_observer_ip_port_from_trace_id(trace_id):
        if len(trace_id) >= 50:
            raise ValueError(f"Trace_id({trace_id}) is invalid due to its length.")

        if trace_id[0] == 'Y':
            id_ = trace_id.split('-')[0].split('Y')[1]
            uval = int(id_, 16)
            ip = uval & 0xFFFFFFFF
            port = (uval >> 32) & 0xFFFF
            ip_str = f"{(ip >> 24) & 0xFF}.{(ip >> 16) & 0xFF}.{(ip >> 8) & 0xFF}.{ip & 0xFF}"
            origin_ip_port = f"{ip_str}:{port}"
        else:
            parts = trace_id.split('-')
            processed_parts = [hex(int(t))[2:].upper().zfill(16 if idx == 1 else 0) for idx, t in enumerate(parts)]
            s = 'Y' + '-'.join(processed_parts)
            origin_ip_port = StringUtils.get_observer_ip_port_from_trace_id(s)
        return origin_ip_port

    @staticmethod
    def parse_range_string(range_str, nu, stdio=None):
        # parse_range_string: Determine whether variable 'nu' is within the range of 'range_str'
        # 提取范围字符串中的数字
        nu = int(nu)
        range_str = range_str.replace(" ", "")
        # range_str = range_str.replace(".", "")
        start, end = range_str[1:-1].split(',')
        need_less = True
        need_than = True
        # 将数字转换为整数
        if start.strip() == "*":
            need_less = False
        else:
            start = float(start.strip())
        if end.strip() == "*":
            need_than = False
        else:
            end = float(end.strip())
        stdio and getattr(stdio, 'verbose', print)('range_str is %s' % range_str)

        if need_less:
            if range_str[0] == "(":
                if nu <= start:
                    return False
            elif range_str[0] == "[":
                if nu < start:
                    return False
        if need_than:
            if range_str[-1] == ")":
                if nu >= end:
                    return False
            elif range_str[-1] == "]":
                if nu > end:
                    return False
        return True

    @staticmethod
    def build_str_on_expr_by_dict(expr, variable_dict, stdio=None):
        s = expr
        d = variable_dict

        def replacer(match):
            key = match.group(1)
            return str(d.get(key, match.group(0)))

        return re.sub(r'#\{(\w+)\}', replacer, s)

    @staticmethod
    def build_sql_on_expr_by_dict(expr, variable_dict, stdio=None):
        s = expr
        d = variable_dict

        def replacer(match):
            key = match.group(1)
            value = str(d.get(key, match.group(0)))
            return f'"{value}"'

        return re.sub(r'\$\{(\w+)\}', replacer, s)

    @staticmethod
    def node_cut_passwd_for_log(obj, stdio=None):
        if isinstance(obj, dict):
            new_obj = {}
            for key, value in obj.items():
                if key == "password" or key == "ssh_password":
                    continue
                new_obj[key] = StringUtils.node_cut_passwd_for_log(value)
            return new_obj
        elif isinstance(obj, list):
            return [StringUtils.node_cut_passwd_for_log(item) for item in obj]
        else:
            return obj

    @staticmethod
    def split_ip(ip_str, stdio=None):
        pattern = r'((?:[0-9]{1,3}\.){3}[0-9]{1,3}|(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4})'
        result = re.findall(pattern, ip_str)
        if not result:
            pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            result = re.findall(pattern, ip_str)
            return result
        return result

    @staticmethod
    def is_chinese(s, stdio=None):
        try:
            s.encode('ascii')
        except UnicodeEncodeError:
            return True
        else:
            return False

    @staticmethod
    def compare_versions_greater(v1, v2, stdio=None):
        for i, j in zip(map(int, v1.split(".")), map(int, v2.split("."))):
            if i == j:
                continue
            return i > j
        return len(v1.split(".")) > len(v2.split("."))

    @staticmethod
    def compare_versions_lower(v1, v2, stdio=None):
        for i, j in zip(map(int, v1.split(".")), map(int, v2.split("."))):
            if i == j:
                continue
            return i < j
        return len(v1.split(".")) < len(v2.split("."))

    @staticmethod
    def mask_passwords(data):
        # Make a deep copy of the data to avoid modifying the original
        masked_data = copy.deepcopy(data)

        if isinstance(masked_data, dict):
            for key, value in masked_data.items():
                if 'password' in key.lower():
                    if not isinstance(value, str):
                        value = str(value)
                    masked_data[key] = '*' * (len(value) if value else 1)
                elif isinstance(value, (dict, list)):
                    masked_data[key] = StringUtils.mask_passwords(value)
        elif isinstance(masked_data, list):
            for index, item in enumerate(masked_data):
                if isinstance(item, (dict, list)):
                    masked_data[index] = StringUtils.mask_passwords(item)

        return masked_data

    @staticmethod
    def parse_optimization_info(text, stdio, filter_tables=None):
        # Fixed module names that should not be treated as table names
        module_names = {'Outputs & filters', 'Used Hint', 'Qb name trace', 'Outline Data', 'Optimization Info', 'Plan Type', 'Note'}

        tables = {}
        current_table = None
        lines = text.splitlines()

        for line in lines:
            # Remove leading/trailing whitespace and '|' characters
            line = line.strip().strip('|').strip()
            if not line or line.startswith('-') or line.startswith('|'):
                # Skip empty lines, separator lines, and lines starting with '|'
                continue

            try:
                # Check if it's the start of a new table (contains ':' and ends with it, and is not a module name)
                if ':' in line and line.endswith(':') and line.rstrip(':').strip() not in module_names:
                    current_table = line.rstrip(':').strip()
                    tables[current_table] = None
                elif current_table:
                    match_stats_version = re.search(r'stats version:(\d+)', line)
                    match_stats_info = re.search(r'stats info:\[version=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+),\s*is_locked=\d+,\s*is_expired=\d+]', line)

                    if match_stats_version:
                        stats_version = int(match_stats_version.group(1))
                        tables[current_table] = {'type': 'version', 'value': stats_version}
                    elif match_stats_info:
                        stats_time_str = match_stats_info.group(1)
                        stats_time = datetime.datetime.strptime(stats_time_str, '%Y-%m-%d %H:%M:%S.%f')
                        tables[current_table] = {'type': 'info', 'value': stats_time}
            except Exception as e:
                return None

        messages = []
        for table, stats_data in tables.items():
            if stats_data is None:
                stdio.verbose(f"Could not find stats version information for the {table} table.")
            else:
                try:
                    if stats_data['type'] == 'version':
                        if stats_data['value'] == 0 and (table in filter_tables):
                            message = f"In explain extended [Optimization Info], the [stats version] for the {table} table is 0, indicating that statistics have not been collected. Please collect statistics."
                            stdio.print(message)
                            messages.append(message)
                        else:
                            stats_time = datetime.datetime.utcfromtimestamp(stats_data['value'] // 1000000).strftime('%Y-%m-%d %H:%M:%S')
                            if ((datetime.datetime.now().timestamp() - stats_data['value'] / 1000000) > 24 * 60 * 60) and (table in filter_tables):
                                message = f"In explain extended [Optimization Info], the [stats version] time for the {table} table is {stats_time}, indicating that statistics are over 24 hours old. Please collect statistics."
                                stdio.print(message)
                                messages.append(message)
                            else:
                                message = f"The statistics are up-to-date. The last collection time for the {table} table was {stats_time}. No action needed."
                                stdio.verbose(message)
                    elif stats_data['type'] == 'info':
                        if ((datetime.datetime.now() - stats_data['value']).total_seconds() > 24 * 60 * 60) and (table in filter_tables):
                            message = (
                                f"In explain extended [Optimization Info], the [stats version] time for the {table} table is {stats_data['value'].strftime('%Y-%m-%d %H:%M:%S')}, indicating that statistics are over 24 hours old. Please collect statistics."
                            )
                            stdio.print(message)
                            messages.append(message)
                        else:
                            message = f"The statistics are up-to-date. The last collection time for the {table} table is {stats_data['value'].strftime('%Y-%m-%d %H:%M:%S')}，No action needed."
                            stdio.verbose(message)
                except Exception as e:
                    stdio.verbose(f"Error processing {table} table: {e}")
        return "\n".join(messages)

    @staticmethod
    def generate_numeric_code(length=6):
        """生成指定长度的纯数字验证码"""
        return ''.join(random.choices('0123456789', k=length))

    @staticmethod
    def generate_alphanum_code(length=8):
        """生成包含大小写字母和数字的随机码"""
        characters = string.ascii_letters + string.digits  # a-zA-Z0-9
        return ''.join(random.choices(characters, k=length))

    @staticmethod
    def fill_sql_with_params(sql, params_value, stdio):
        """
        将参数值填充到带有占位符的SQL中

        Args:
            sql (str): 带有占位符(?)的SQL语句
            params_value (str): 逗号分隔的参数值字符串
            stdio: 标准输入输出对象

        Returns:
            str: 填充了参数值的完整SQL语句
        """
        if not params_value or not sql:
            return sql

        try:
            # Parse parameters
            params = []
            current_param = ""
            in_quotes = False
            quote_char = None

            for char in params_value:
                if char in ["'", '"']:
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                        current_param += char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                        current_param += char
                    else:
                        current_param += char
                elif char == ',' and not in_quotes:
                    # Remove leading/trailing spaces
                    param = current_param.strip()
                    params.append(param)
                    current_param = ""
                else:
                    current_param += char

            # Process the last parameter
            if current_param:
                param = current_param.strip()
                params.append(param)

            # Replace placeholders in SQL
            result_sql = sql
            for param in params:
                # Find the first ? and replace
                pos = result_sql.find('?')
                if pos != -1:
                    result_sql = result_sql[:pos] + str(param) + result_sql[pos + 1 :]
                else:
                    # If the parameter count does not match, record a warning and stop
                    stdio.warn(f"Parameter count mismatch: SQL has more placeholders than parameters. SQL: {sql}, Params: {params_value}")
                    break

            stdio.verbose(f"Original SQL: {sql}")
            stdio.verbose(f"Params: {params_value}")
            stdio.verbose(f"Filled SQL: {result_sql}")

            return result_sql

        except Exception as e:
            stdio.warn(f"Failed to fill SQL with parameters: {e}")
            return sql
