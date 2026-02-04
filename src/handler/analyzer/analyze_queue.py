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
@time: 2024/08/23
@file: analyze_queue.py
@desc: Analyze queue handler (Migrated to BaseHandler)
"""
import datetime
import os
import csv
from tabulate import tabulate
from src.common.base_handler import BaseHandler
from src.common.command import get_observer_version
from src.common.ssh_client.local_client import LocalClient
from src.common.obdiag_exception import OBDIAGFormatException, OBDIAGDBConnException
from src.common.constant import const
from src.common.ssh_client.ssh import SshClient
from src.common.ob_log_level import OBLogLevel
from src.common.command import download_file, get_logfile_name_list, mkdir, delete_file
from src.common.tool import StringUtils
from src.common.tool import Util
from src.common.tool import DirectoryUtil
from src.common.tool import FileUtil
from src.common.tool import TimeUtils
from src.common.result_type import ObdiagResult
from src.common.ob_connector import OBConnector
import re


class AnalyzeQueueHandler(BaseHandler):
    def _init(self, **kwargs):
        """Subclass initialization"""
        self.directly_analyze_files = False
        self.analyze_files_list = []
        self.is_ssh = True
        self.gather_timestamp = None
        self.gather_ob_log_temporary_dir = const.GATHER_LOG_TEMPORARY_DIR_DEFAULT
        self.gather_pack_dir = None
        self.ob_log_dir = None
        self.from_time_str = None
        self.to_time_str = None
        self.zip_encrypt = False
        self.log_level = OBLogLevel.WARN
        self.config_path = const.DEFAULT_CONFIG_PATH
        self.ob_cluster = self.context.cluster_config
        self.tenant = None
        self.queue = None
        self.tenant_id = None
        self.ip_list = None
        self.scope = None

        try:
            self.obconn = OBConnector(
                context=self.context,
                ip=self.ob_cluster.get("db_host"),
                port=self.ob_cluster.get("db_port"),
                username=self.ob_cluster.get("tenant_sys").get("user"),
                password=self.ob_cluster.get("tenant_sys").get("password"),
                timeout=10000,
                database="oceanbase",
            )
        except Exception as e:
            self._log_error(f"Failed to connect to database: {e}")
            raise OBDIAGDBConnException(f"Failed to connect to database: {e}")

        # Initialize config
        self.nodes = self.context.cluster_config['servers']

        # Use ConfigAccessor if available
        if self.config:
            self.file_number_limit = self.config.gather_file_number_limit
            self.file_size_limit = self.config.gather_file_size_limit
            self.config_path = self.config.config_path
        else:
            # Fallback to direct config access
            if self.context.inner_config is None:
                self.file_number_limit = 20
                self.file_size_limit = 2 * 1024 * 1024 * 1024
            else:
                basic_config = self.context.inner_config['obdiag']['basic']
                self.file_number_limit = int(basic_config["file_number_limit"])
                self.file_size_limit = int(FileUtil.size(basic_config["file_size_limit"]))
                self.config_path = basic_config['config_path']

        # Initialize options
        from_option = self._get_option('from')
        to_option = self._get_option('to')
        since_option = self._get_option('since')
        store_dir_option = self._get_option('store_dir')
        tenant_option = self._get_option('tenant')
        queue_option = self._get_option('queue')

        if tenant_option is None:
            raise ValueError('--tenant option was not provided')

        self.tenant = tenant_option
        observer_version = self.get_version()

        if StringUtils.compare_versions_greater(observer_version, "4.0.0.0"):
            sql = f'select tenant_id,GROUP_CONCAT(svr_ip ORDER BY svr_ip ) as ip_list from DBA_OB_UNITS where tenant_id=(select tenant_id from DBA_OB_TENANTS where tenant_name="{self.tenant}") group by tenant_id'
        else:
            sql = f'select c.tenant_id,GROUP_CONCAT(DISTINCT b.svr_ip ORDER BY b.svr_ip) AS ip_list FROM __all_resource_pool a JOIN __all_unit b ON a.resource_pool_id = b.resource_pool_id JOIN __all_tenant c ON a.tenant_id = c.tenant_id WHERE c.tenant_name ="{self.tenant}"'

        self._log_verbose(f"sql is {sql}")
        sql_result = self.obconn.execute_sql_return_cursor_dictionary(sql).fetchall()

        if len(sql_result) <= 0:
            raise ValueError(f'tenant is {tenant_option} not  in this cluster')

        self._log_verbose(f"sql_result is {sql_result}")
        for row in sql_result:
            self.tenant_id = row["tenant_id"]
            self.ip_list = row["ip_list"]

        self._log_verbose(f"tenant_id is {self.tenant_id}")
        self._log_verbose(f"ip_list is {self.ip_list}")
        self.queue = queue_option
        self.scope = "observer"

        if from_option is not None and to_option is not None:
            try:
                from_timestamp = TimeUtils.parse_time_str(from_option)
                to_timestamp = TimeUtils.parse_time_str(to_option)
                self.from_time_str = from_option
                self.to_time_str = to_option
            except OBDIAGFormatException:
                raise ValueError(f'Error: Datetime is invalid. Must be in format yyyy-mm-dd hh:mm:ss. from_datetime={from_option}, to_datetime={to_option}')
            if to_timestamp <= from_timestamp:
                raise ValueError('Error: from datetime is larger than to datetime, please check.')
        elif (from_option is None or to_option is None) and since_option is not None:
            now_time = datetime.datetime.now()
            self.to_time_str = (now_time + datetime.timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
            self.from_time_str = (now_time - datetime.timedelta(seconds=TimeUtils.parse_time_length_to_sec(since_option))).strftime('%Y-%m-%d %H:%M:%S')
            if not self.directly_analyze_files:
                self._log_info(f'analyze log from_time: {self.from_time_str}, to_time: {self.to_time_str}')
        else:
            self._log_info('No time option provided, default processing is based on the last 30 minutes')
            now_time = datetime.datetime.now()
            self.to_time_str = (now_time + datetime.timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
            if since_option is not None:
                self.from_time_str = (now_time - datetime.timedelta(seconds=TimeUtils.parse_time_length_to_sec(since_option))).strftime('%Y-%m-%d %H:%M:%S')
            else:
                self.from_time_str = (now_time - datetime.timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
            if not self.directly_analyze_files:
                self._log_info(f'analyze log from_time: {self.from_time_str}, to_time: {self.to_time_str}')

        if store_dir_option is not None:
            if not os.path.exists(os.path.abspath(store_dir_option)):
                self._log_warn(f'args --store_dir [{os.path.abspath(store_dir_option)}] incorrect: No such directory, Now create it')
                os.makedirs(os.path.abspath(store_dir_option))
            self.gather_pack_dir = os.path.abspath(store_dir_option)

    def get_version(self):
        observer_version = ""
        try:
            observer_version = get_observer_version(self.context)
        except Exception as e:
            self._log_warn(f"AnalyzeQueueHandler failed to get observer version:{e}")
        self._log_verbose(f"AnalyzeQueueHandler get observer version: {observer_version}")
        return observer_version

    def handle(self) -> ObdiagResult:
        """Main handle logic"""
        self._validate_initialized()

        try:

            local_store_parent_dir = os.path.join(self.gather_pack_dir, "obdiag_analyze_pack_{0}".format(TimeUtils.timestamp_to_filename_time(TimeUtils.get_current_us_timestamp())))
            self._log_verbose(f"Use {local_store_parent_dir} as pack dir.")
            analyze_tuples = []

            def handle_from_node(node):
                node_results = self.__handle_from_node(node, local_store_parent_dir)
                analyze_tuples.append((node.get("ip"), node_results))

            if self.is_ssh:
                nodes_new = []
                for node in self.nodes:
                    if node["ip"] in self.ip_list:
                        nodes_new.append(node)
                self.nodes = nodes_new
                for node in self.nodes:
                    handle_from_node(node)

            self._log_verbose(str(analyze_tuples))
            table_data = []
            headers = ['IP', 'Tenant Name', 'From_Time', 'To_Time', 'Is Queue', 'Queue Limit', 'Over Queue Limit Count', 'Max Queue']
            for ip, info in analyze_tuples:
                row = [ip, info['tenant_name'], info['from_datetime_timestamp'], info['to_datetime_timestamp'], info['is_queue'], info['queue_limit'], info['over_queue_limit'], info['max_queue']]
                table_data.append(row)
            queue_result = tabulate(table_data, headers=headers, tablefmt="pretty")
            self._log_info("\nQueue Result:")
            self._log_info(queue_result)
            FileUtil.write_append(os.path.join(local_store_parent_dir, "result_details.txt"), str(queue_result))
            last_info = f"\nFor more details, please run cmd \033[32m' cat {os.path.join(local_store_parent_dir, 'result_details.txt')} '\033[0m\n"
            self._log_info(last_info)
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": queue_result})

        except Exception as e:
            return self._handle_error(e)

    def __handle_from_node(self, node, local_store_parent_dir):
        ssh_client = SshClient(self.context, node)
        try:
            node_results = []
            queue_limit = self.queue
            result_dict = {}
            remote_ip = node.get("ip") if self.is_ssh else '127.0.0.1'
            self._log_verbose(f"Sending Collect Shell Command to node {remote_ip} ...")
            DirectoryUtil.mkdir(path=local_store_parent_dir, stdio=self.stdio)
            local_store_dir = f"{local_store_parent_dir}/{ssh_client.get_name()}"
            DirectoryUtil.mkdir(path=local_store_dir, stdio=self.stdio)
        except Exception as e:
            raise Exception(f"failed to handle from node: {node}, error: {e}")

        from_datetime_timestamp = TimeUtils.timestamp_to_filename_time(TimeUtils.datetime_to_timestamp(self.from_time_str))
        to_datetime_timestamp = TimeUtils.timestamp_to_filename_time(TimeUtils.datetime_to_timestamp(self.to_time_str))
        gather_dir_name = f"ob_log_{ssh_client.get_name()}_{from_datetime_timestamp}_{to_datetime_timestamp}"
        gather_dir_full_path = f"/tmp/{gather_dir_name}"
        mkdir_info = mkdir(ssh_client, gather_dir_full_path)
        if mkdir_info:
            self._log_error(f"failed to handle from node: {node}, error: {mkdir_info}")
            return result_dict

        log_list = self.__handle_log_list(ssh_client, node)
        self._log_info(FileUtil.show_file_list_tabulate(remote_ip, log_list, self.stdio))
        for log_name in log_list:
            if self.directly_analyze_files:
                self.__pharse_offline_log_file(ssh_client, log_name=log_name, local_store_dir=local_store_dir)
                analyze_log_full_path = "{0}/{1}".format(local_store_dir, str(log_name).strip(".").replace("/", "_"))
            else:
                self.__pharse_log_file(ssh_client, node=node, log_name=log_name, gather_path=gather_dir_full_path, local_store_dir=local_store_dir)
                analyze_log_full_path = "{0}/{1}".format(local_store_dir, log_name)
            self.stdio.start_loading('analyze log start')
            file_result = self.__parse_log_lines(analyze_log_full_path)
            self.stdio.stop_loading('analyze log sucess')
            node_results.append(file_result)
        delete_file(ssh_client, gather_dir_full_path, self.stdio)
        ssh_client.ssh_close()
        self.__write_to_csv(local_store_parent_dir, node_results)
        count, max_queue_value = self.count_and_find_max_queues(node_results, queue_limit)
        self._log_verbose(f"count:{count}, max_queue_value:{max_queue_value}")
        result_dict['tenant_name'] = self.tenant
        if max_queue_value > queue_limit:
            result_dict['is_queue'] = 'yes'
        else:
            result_dict['is_queue'] = 'no'
        result_dict['queue_limit'] = queue_limit
        result_dict['over_queue_limit'] = count
        result_dict['max_queue'] = max_queue_value
        result_dict['from_datetime_timestamp'] = from_datetime_timestamp
        result_dict['to_datetime_timestamp'] = to_datetime_timestamp
        return result_dict

    def count_and_find_max_queues(self, data, queue_limit):
        count = 0
        max_queue_value = 0
        for sublist in data:
            for item in sublist:
                for key, value in item.items():
                    if 'queue' in key:
                        value = int(value)
                        if value > queue_limit:
                            count += 1
                            if value > max_queue_value:
                                max_queue_value = value

        return count, max_queue_value

    def __handle_log_list(self, ssh_client, node):
        if self.directly_analyze_files:
            log_list = self.__get_log_name_list_offline()
        else:
            log_list = self.__get_log_name_list(ssh_client, node)
        if len(log_list) > self.file_number_limit:
            self._log_warn(f"{node.get('ip')} The number of log files is {len(log_list)}, out of range (0,{self.file_number_limit}]")
            return log_list
        elif len(log_list) == 0:
            self._log_warn(f"{node.get('ip')} The number of log files is {len(log_list)}, No files found, Please adjust the query limit")
            return log_list
        return log_list

    def __get_log_name_list(self, ssh_client, node):
        """
        :param ssh_client:
        :return: log_name_list
        """
        home_path = node.get("home_path")
        log_path = os.path.join(home_path, "log")
        get_oblog = "ls -1 -F %s/*%s.log* | grep -E 'observer.log(\.[0-9]+){0,1}$' | grep -v 'wf'|awk -F '/' '{print $NF}'" % (log_path, self.scope)
        log_name_list = []
        log_files = ssh_client.exec_cmd(get_oblog)
        if log_files:
            log_name_list = get_logfile_name_list(ssh_client, self.from_time_str, self.to_time_str, log_path, log_files, self.stdio)
        else:
            self._log_error("Unable to find the log file. Please provide the correct --ob_install_dir, the default is [/home/admin/oceanbase]")
        return log_name_list

    def __get_log_name_list_offline(self):
        """
        :param:
        :return: log_name_list
        """
        log_name_list = []
        if self.analyze_files_list and len(self.analyze_files_list) > 0:
            for path in self.analyze_files_list:
                if os.path.exists(path):
                    if os.path.isfile(path):
                        log_name_list.append(path)
                    else:
                        log_names = FileUtil.find_all_file(path)
                        if len(log_names) > 0:
                            log_name_list.extend(log_names)
        self._log_verbose(f"get log list {log_name_list}")
        return log_name_list

    def __pharse_log_file(self, ssh_client, node, log_name, gather_path, local_store_dir):
        home_path = node.get("home_path")
        log_path = os.path.join(home_path, "log")
        local_store_path = f"{local_store_dir}/{log_name}"
        obs_log_path = f"{log_path}/{log_name}"
        gather_log_path = f"{gather_path}/{log_name}"
        self._log_verbose(f"obs_log_path {obs_log_path}")
        self._log_verbose(f"gather_log_path {gather_log_path}")
        self._log_verbose(f"local_store_path {local_store_path}")
        self._log_verbose(f"log_name {log_name}")
        pattern = "dump tenant info(tenant={id:tenant_id,"
        search_pattern = pattern.replace("{id:tenant_id,", f"{{id:{self.tenant_id},")
        search_pattern = '"' + search_pattern + '"'
        self._log_verbose(f"search_pattern = [{search_pattern}]")
        command = ['grep', search_pattern, obs_log_path]
        grep_cmd = ' '.join(command) + f' >> {gather_log_path}'
        self._log_verbose(f"grep files, run cmd = [{grep_cmd}]")
        ssh_client.exec_cmd(grep_cmd)
        log_full_path = f"{gather_path}/{log_name}"
        download_file(ssh_client, log_full_path, local_store_path, self.stdio)

    def __pharse_offline_log_file(self, ssh_client, log_name, local_store_dir):
        """
        :param ssh_helper, log_name
        :return:
        """

        ssh_client = LocalClient(context=self.context, node={"ssh_type": "local"})
        local_store_path = f"{local_store_dir}/{str(log_name).strip('.').replace('/', '_')}"
        grep_cmd = f"grep -e 'dump tenant info(tenant={{id:{self.tenant_id},' {log_name} >> {local_store_path} "
        self._log_verbose(f"grep files, run cmd = [{grep_cmd}]")
        ssh_client.exec_cmd(grep_cmd)

    def __parse_log_lines(self, file_full_path):
        """
        Process the observer's log line by line
        """
        log_lines = []
        with open(file_full_path, 'r', encoding='utf8', errors='ignore') as file:
            for line in file:
                log_lines.append(line.strip())
        pattern_timestamp = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\]'
        pattern_req_queue = r'req_queue:total_size=(\d+)'
        pattern_multi_level_queue = r'multi_level_queue:total_size=(\d+)'
        pattern_group_id = r'group_id = (\d+),queue_size = (\d+)'

        # get group_id
        all_group_ids = set()
        for log in log_lines:
            matches = re.findall(pattern_group_id, log)
            for match in matches:
                all_group_ids.add(int(match[0]))

        results = []
        group_id_columns = {f'group_id_{gid}_queue_size': 'NA' for gid in all_group_ids}

        for log in log_lines:
            timestamp = re.search(pattern_timestamp, log).group(1)
            req_queue_size = re.search(pattern_req_queue, log).group(1) if re.search(pattern_req_queue, log) else 'NA'
            multi_level_queue_size = re.search(pattern_multi_level_queue, log).group(1) if re.search(pattern_multi_level_queue, log) else 'NA'

            group_info = {}
            matches = re.findall(pattern_group_id, log)
            for match in matches:
                group_id, queue_size = match
                group_info[f'group_id_{group_id}_queue_size'] = queue_size

            result = {
                'timestamp': timestamp,
                'req_queue_total_size': req_queue_size,
                'multi_level_queue_total_size': multi_level_queue_size,
                **group_info,
                **{k: 'NA' for k in group_id_columns if k not in group_info},
            }

            results.append(result)
        return results

    def __write_to_csv(self, local_store_parent_dir, data):
        try:
            if not data or not isinstance(data, list) or not data[0] or not isinstance(data[0], list):
                raise ValueError("Data is not in the expected format. It should be a non-empty list of lists containing dictionaries.")
            fieldnames = data[0][0].keys()
            file_path = os.path.join(local_store_parent_dir, "node_results.csv")
            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                for row in data[0]:
                    writer.writerow(row)
        except ValueError as ve:
            self.stdio.exception(f"ValueError: {ve}")
        except Exception as e:
            self.stdio.exception(f"an unexpected error occurred: {e}")
