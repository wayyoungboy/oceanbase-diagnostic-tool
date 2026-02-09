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
@time: 2023/9/23
@file: analyze_log.py
@desc:
"""
import datetime
import glob
import os
import re
import tarfile

# Removed tabulate import - now using BaseHandler._generate_summary_table

from src.common.base_handler import BaseHandler
from src.common.ssh_client.local_client import LocalClient
from src.common.obdiag_exception import OBDIAGFormatException
from src.common.constant import const
from src.common.command import download_file
from src.common.ob_log_level import OBLogLevel
from src.handler.meta.ob_error import OB_RET_DICT
from src.common.tool import Util
from src.common.tool import DirectoryUtil
from src.common.tool import FileUtil
from src.common.tool import TimeUtils
from src.common.result_type import ObdiagResult
from src.handler.gather.gather_component_log import GatherComponentLogHandler


class AnalyzeLogHandler(BaseHandler):
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
        self.grep_args = None
        self.scope = None
        self.zip_encrypt = False
        self.log_level = OBLogLevel.WARN
        self.config_path = const.DEFAULT_CONFIG_PATH
        self.by_tenant = True  # Default: enable tenant statistics
        self.tenant_id_filter = None  # If specified, only analyze this tenant

        # Initialize config
        self.nodes = self.context.cluster_config['servers']

        # Initialize file limits as instance variables (not properties)
        # Use ConfigAccessor if available
        if self.config:
            self._file_number_limit = self.config.gather_file_number_limit
            self._file_size_limit = self.config.gather_file_size_limit
            self.config_path = self.config.basic_config_path
        else:
            # Fallback to direct config access
            if self.context.inner_config is None:
                self._file_number_limit = 20
                self._file_size_limit = 2 * 1024 * 1024 * 1024
            else:
                basic_config = self.context.inner_config['obdiag']['basic']
                self._file_number_limit = int(basic_config["file_number_limit"])
                self._file_size_limit = int(FileUtil.size(basic_config["file_size_limit"]))
                self.config_path = basic_config['config_path']

        # Initialize options
        options = self.context.options
        from_option = self._get_option('from')
        to_option = self._get_option('to')
        since_option = self._get_option('since')
        store_dir_option = self._get_option('store_dir')
        grep_option = self._get_option('grep')
        scope_option = self._get_option('scope')
        log_level_option = self._get_option('log_level')
        files_option = self._get_option('files')
        temp_dir_option = self._get_option('temp_dir')

        if files_option:
            self.is_ssh = False
            self.directly_analyze_files = True
            self.analyze_files_list = files_option

        if from_option is not None and to_option is not None:
            try:
                from_timestamp = TimeUtils.parse_time_str(from_option)
                to_timestamp = TimeUtils.parse_time_str(to_option)
                self.from_time_str = from_option
                self.to_time_str = to_option
            except OBDIAGFormatException:
                self._log_error(f'Error: Datetime is invalid. Must be in format yyyy-mm-dd hh:mm:ss. from_datetime={from_option}, to_datetime={to_option}')
                raise
            if to_timestamp <= from_timestamp:
                self._log_error('Error: from datetime is larger than to datetime, please check.')
                raise ValueError('from datetime is larger than to datetime')
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

        if grep_option is not None:
            self.grep_args = grep_option
        if scope_option:
            self.scope = scope_option
        if log_level_option:
            self.log_level = OBLogLevel().get_log_level(log_level_option)
        if temp_dir_option:
            self.gather_ob_log_temporary_dir = temp_dir_option

        tenant_id_option = self._get_option('tenant_id')
        if tenant_id_option is not None:
            self.tenant_id_filter = tenant_id_option.strip()
            self._log_verbose(f"tenant_id filter: {self.tenant_id_filter}")

    def handle(self) -> ObdiagResult:
        """Main handle logic"""
        self._validate_initialized()

        try:
            self._log_info("analyze nodes's log start. Please wait a moment...")
            self._log_info('analyze start')
            local_store_parent_dir = os.path.join(self.gather_pack_dir, "obdiag_analyze_{0}".format(TimeUtils.timestamp_to_filename_time(TimeUtils.get_current_us_timestamp())))
            self._log_verbose(f"Use {local_store_parent_dir} as pack dir.")
            analyze_tuples = []

            # When --files is not specified: use GatherComponentLogHandler to collect logs (compressed) first, then analyze locally
            if not self.directly_analyze_files:
                return self.__handle_with_gather(local_store_parent_dir)

            # --files specified: analyze local files only (no SSH)
            DirectoryUtil.mkdir(path=local_store_parent_dir, stdio=self.stdio)
            self._log_info("analyze nodes's log start. Please wait a moment...")
            self.stdio.start_loading('analyze start')
            resp, node_results, tenant_results_list = self.__handle_offline(local_store_parent_dir)
            analyze_tuples = [("127.0.0.1", False, resp["error"], node_results)]
            title, field_names, summary_list, summary_details_list = self.__get_overall_summary(analyze_tuples, True)
            analyze_info_nodes = []
            for summary in summary_list:
                analyze_info_node = {}
                field_names_nu = 0
                for m in field_names:
                    analyze_info_node[m] = summary[field_names_nu]
                    field_names_nu += 1
                    if field_names_nu == len(summary):
                        break
                analyze_info_nodes.append(analyze_info_node)
            # Use BaseHandler template method for table generation
            table_str = self._generate_summary_table(field_names, summary_list, title)
            self.stdio.stop_loading('analyze result success')
            # Note: _generate_summary_table already logs the table, so we don't need to print again
            with open(os.path.join(local_store_parent_dir, "result_details.txt"), 'a', encoding='utf-8') as fileobj:
                fileobj.write(u'{}'.format(table_str + "\n\nDetails:\n\n"))
            # build summary details
            summary_details_list_data = []
            for m in range(len(summary_details_list)):
                summary_details_list_data_once = {}
                for n in range(len(field_names)):
                    extend = "\n\n" if n == len(field_names) - 1 else "\n"
                    with open(os.path.join(local_store_parent_dir, "result_details.txt"), 'a', encoding='utf-8') as fileobj:
                        fileobj.write(u'{}'.format(field_names[n] + ": " + str(summary_details_list[m][n]) + extend))
                    summary_details_list_data_once[field_names[n]] = str(summary_details_list[m][n])
                summary_details_list_data.append(summary_details_list_data_once)
            if self.by_tenant and tenant_results_list:
                tenant_title, tenant_field_names, tenant_summary_list = self.__get_tenant_summary(tenant_results_list)
                if tenant_summary_list:
                    # Use BaseHandler template method for tenant table generation
                    tenant_table_str = self._generate_summary_table(tenant_field_names, tenant_summary_list, tenant_title)
                    # Note: _generate_summary_table already logs the table, so we don't need to print again
                    with open(os.path.join(local_store_parent_dir, "result_details.txt"), 'a', encoding='utf-8') as fileobj:
                        fileobj.write(u'{}'.format(tenant_table_str + "\n\n"))
                elif self.tenant_id_filter:
                    self.stdio.warn("No errors found for tenant: {0}".format(self.tenant_id_filter))
            last_info = "For more details, please run cmd \033[32m' cat {0} '\033[0m\n".format(os.path.join(local_store_parent_dir, "result_details.txt"))
            self.stdio.print(last_info)
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": analyze_info_nodes, "summary_details_list": summary_details_list_data, "store_dir": local_store_parent_dir})

        except Exception as e:
            return self._handle_error(e)

    def __handle_with_gather(self, local_store_parent_dir):
        """
        Use GatherComponentLogHandler to collect logs (compressed tar.gz) first, then extract and analyze locally.
        Reduces network transfer time compared to pulling raw logs.
        """
        DirectoryUtil.mkdir(path=local_store_parent_dir, stdio=self.stdio)
        gather_store_dir = os.path.join(local_store_parent_dir, "gathered_logs")
        DirectoryUtil.mkdir(path=gather_store_dir, stdio=self.stdio)

        self._log_info("gather log (compressed) start, then analyze locally...")
        self.stdio.start_loading("gather log start")
        handler = GatherComponentLogHandler()
        handler.init(
            self.context,
            target="observer",
            from_option=self.from_time_str,
            to_option=self.to_time_str,
            since=Util.get_option(self.context.options, 'since'),
            scope=self.scope,
            grep=self.grep_args,
            store_dir=gather_store_dir,
            temp_dir=self.gather_ob_log_temporary_dir,
            is_scene=True,
        )
        gather_result = handler.handle()
        self.stdio.stop_loading("gather succeed" if gather_result.is_success() else "gather failed")

        if not gather_result.is_success():
            self._log_error(f"gather log failed: {gather_result.error_data}")
            return gather_result

        tar_files = glob.glob(os.path.join(gather_store_dir, "*.tar.gz"))
        if not tar_files:
            self._log_warn(f"No tar.gz files found in gather result dir: {gather_store_dir}")
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="No log tar files gathered, please check gather config or time range")

        self._log_verbose(f"extract {len(tar_files)} tar file(s) to local")
        for tar_path in tar_files:
            try:
                with tarfile.open(tar_path, 'r:gz') as tar:
                    tar.extractall(path=local_store_parent_dir)
            except Exception as e:
                self.stdio.exception(f"extract tar failed: {tar_path}, error: {e}")
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data=f"extract gather tar failed: {str(e)}")

        analyze_tuples = []
        tenant_results_list = []
        self.stdio.start_loading("analyze log start")
        for name in os.listdir(local_store_parent_dir):
            node_dir = os.path.join(local_store_parent_dir, name)
            if name == "gathered_logs" or not os.path.isdir(node_dir):
                continue
            node_name = self.__parse_node_name_from_gather_dir(name)
            log_files = [f for f in os.listdir(node_dir) if os.path.isfile(os.path.join(node_dir, f))]
            node_results = []
            for log_f in sorted(log_files):
                full_path = os.path.join(node_dir, log_f)
                try:
                    file_result, tenant_result = self.__parse_log_lines(full_path)
                    node_results.append(file_result)
                    tenant_results_list.append(tenant_result)
                except Exception as e:
                    self._log_verbose(f"parse log file {full_path} failed: {e}")
            analyze_tuples.append((node_name, False, "", node_results))

        self.stdio.stop_loading("succeed")
        title, field_names, summary_list, summary_details_list = self.__get_overall_summary(analyze_tuples, False)
        analyze_info_nodes = []
        for summary in summary_list:
            analyze_info_node = {}
            field_names_nu = 0
            for m in field_names:
                analyze_info_node[m] = summary[field_names_nu]
                field_names_nu += 1
                if field_names_nu == len(summary):
                    break
            analyze_info_nodes.append(analyze_info_node)
        # Use BaseHandler template method for summary table generation
        table_str = self._generate_summary_table(field_names, summary_list, title)
        # Note: _generate_summary_table already logs the table, so we don't need to print again
        with open(os.path.join(local_store_parent_dir, "result_details.txt"), 'a', encoding='utf-8') as fileobj:
            fileobj.write(u'{}'.format(table_str + "\n\nDetails:\n\n"))
        summary_details_list_data = []
        for m in range(len(summary_details_list)):
            summary_details_list_data_once = {}
            for n in range(len(field_names)):
                extend = "\n\n" if n == len(field_names) - 1 else "\n"
                with open(os.path.join(local_store_parent_dir, "result_details.txt"), 'a', encoding='utf-8') as fileobj:
                    fileobj.write(u'{}'.format(field_names[n] + ": " + str(summary_details_list[m][n]) + extend))
                summary_details_list_data_once[field_names[n]] = str(summary_details_list[m][n])
            summary_details_list_data.append(summary_details_list_data_once)
        if self.by_tenant and tenant_results_list:
            tenant_title, tenant_field_names, tenant_summary_list = self.__get_tenant_summary(tenant_results_list)
            if tenant_summary_list:
                # Use BaseHandler template method for tenant table generation
                tenant_table_str = self._generate_summary_table(tenant_field_names, tenant_summary_list, tenant_title)
                # Note: _generate_summary_table already logs the table, so we don't need to print again
                with open(os.path.join(local_store_parent_dir, "result_details.txt"), 'a', encoding='utf-8') as fileobj:
                    fileobj.write(u'{}'.format(tenant_table_str + "\n\n"))
            elif self.tenant_id_filter:
                self.stdio.warn("No errors found for tenant: {0}".format(self.tenant_id_filter))
        last_info = "For more details, please run cmd \033[32m' cat {0} '\033[0m\n".format(os.path.join(local_store_parent_dir, "result_details.txt"))
        self.stdio.print(last_info)
        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": analyze_info_nodes, "summary_details_list": summary_details_list_data, "store_dir": local_store_parent_dir})

    def __parse_node_name_from_gather_dir(self, dir_name):
        """
        Parse node display name from gather tar inner dir name.
        Format: observer_log_10.0.0.1_2881_20250101120000_20250102120000_abc123 -> 10.0.0.1_2881
        """
        match = re.match(r'^observer_log_(.+)_\d+_\d+_[a-z0-9]{6}$', dir_name)
        if match:
            return match.group(1)
        return dir_name

    def __handle_offline(self, local_store_parent_dir):
        """
        Analyze local log files only (--files). No SSH, no remote node.
        """
        resp = {"skip": False, "error": ""}
        node_results = []
        local_store_dir = os.path.join(local_store_parent_dir, "127.0.0.1")
        DirectoryUtil.mkdir(path=local_store_dir, stdio=self.stdio)

        log_list = self.__get_log_name_list_offline()
        if len(log_list) > self._file_number_limit:
            resp["skip"] = True
            resp["error"] = "Too many files {0} > {1}, Please adjust the number of incoming files".format(len(log_list), self._file_number_limit)
            return resp, node_results, []
        if len(log_list) == 0:
            resp["skip"] = True
            resp["error"] = "No files found"
            return resp, node_results, []

        self.stdio.print(FileUtil.show_file_list_tabulate("127.0.0.1", log_list, self.stdio))
        self.stdio.start_loading("analyze log start")
        tenant_results_list = []
        for log_name in log_list:
            self.__pharse_offline_log_file(log_name=log_name, local_store_dir=local_store_dir)
            analyze_log_full_path = "{0}/{1}".format(local_store_dir, str(log_name).strip(".").replace("/", "_"))
            file_result, tenant_result = self.__parse_log_lines(analyze_log_full_path)
            node_results.append(file_result)
            tenant_results_list.append(tenant_result)
        self.stdio.stop_loading("succeed")
        return resp, node_results, tenant_results_list

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
        self.stdio.verbose("get log list {}".format(log_name_list))
        return log_name_list

    def __pharse_offline_log_file(self, log_name, local_store_dir):
        """
        Copy or grep local log file to local_store_dir for parsing.
        """
        local_client = LocalClient(context=self.context, node={"ssh_type": "local"})
        local_store_path = "{0}/{1}".format(local_store_dir, str(log_name).strip(".").replace("/", "_"))
        if self.grep_args is not None:
            grep_cmd = "grep -e '{grep_args}' {log_name} >> {local_store_path} ".format(grep_args=self.grep_args, log_name=log_name, local_store_path=local_store_path)
            self.stdio.verbose("grep files, run cmd = [{0}]".format(grep_cmd))
            local_client.exec_cmd(grep_cmd)
        else:
            download_file(local_client, log_name, local_store_path, self.stdio)

    def __get_tenant_from_log_line(self, log_line):
        """
        Extract tenant identifier from OceanBase observer log line.
        Tries tname= (tenant name) first, then tenant_id= (numeric).
        :param log_line: raw log line
        :return: tenant string, or "_unknown_" when not found
        """
        if not log_line:
            return "_unknown_"
        # tname=tenant_name (common in OB log)
        tname_pattern = r"tname=([^,\s)\]]+)"
        tname_match = re.search(tname_pattern, log_line)
        if tname_match:
            return tname_match.group(1).strip()
        # tenant_id=123 or tenant_id:123
        tid_pattern = r"tenant_id[=:](\d+)"
        tid_match = re.search(tid_pattern, log_line, re.IGNORECASE)
        if tid_match:
            return "tenant_id:" + tid_match.group(1)
        return "_unknown_"

    def __get_observer_ret_code(self, log_line):
        """
        Get the ret code from the observer log
        :param log_line
        :return: ret_code
        """
        prefix = "ret=-"
        idx = log_line.find(prefix)
        if idx < 0:
            return ""
        start = idx + len(prefix)
        if start >= len(log_line):
            return ""
        end = start
        while end < len(log_line):
            c = log_line[end]
            if c < '0' or c > '9':
                break
            end = end + 1
        return "-" + log_line[start:end]

    def __parse_log_lines(self, file_full_path):
        """
        Process the observer's log line by line.
        :param file_full_path
        :return: (error_dict, tenant_error_dict). tenant_error_dict is {} when by_tenant is False.
                 tenant_error_dict[tenant][ret_code] = {file_name, count, first_found_time, last_found_time, trace_id_list}
        """
        error_dict = {}
        tenant_error_dict = {}
        self.crash_error = ""
        self.stdio.verbose("start parse log {0}".format(file_full_path))
        with open(file_full_path, 'r', encoding='utf8', errors='ignore') as file:
            line_num = 0
            for line in file:
                line_num = line_num + 1
                line = line.strip()
                if line:
                    ## CRASH ERROR log
                    if line.find("CRASH ERROR") != -1:
                        ret_code = "CRASH_ERROR"
                        line_time = ""
                        trace_id = ""
                        ## extract tname
                        tname_pattern = r"tname=([^,]+)"
                        tname_match = re.search(tname_pattern, line)
                        if tname_match:
                            error = tname_match.group(1)
                            if error != self.crash_error and self.crash_error != '':
                                self.crash_error = "{0},{1}".format(self.crash_error, error)
                            else:
                                self.crash_error = "{0}{1}".format("crash thread:", error)
                            self.stdio.print("crash_error:{0}".format(self.crash_error))
                        if error_dict.get(ret_code) is None:
                            error_dict[ret_code] = {"file_name": file_full_path, "count": 1, "first_found_time": line_time, "last_found_time": line_time, "trace_id_list": {trace_id} if len(trace_id) > 0 else {}}
                        else:
                            count = error_dict[ret_code]["count"] + 1
                            error_dict[ret_code] = {"file_name": file_full_path, "count": count, "first_found_time": line_time, "last_found_time": line_time, "trace_id_list": trace_id}
                        if self.by_tenant:
                            tenant = self.__get_tenant_from_log_line(line)
                            self.__merge_tenant_error(tenant_error_dict, tenant, ret_code, file_full_path, line_time, line_time, trace_id)
                        continue
                    line_time = self.__get_time_from_ob_log_line(line)
                    if len(line_time) == 0:
                        continue
                    real_level = self.__get_log_level(line)
                    if real_level < self.log_level:
                        continue
                    ret_code = self.__get_observer_ret_code(line)
                    if len(ret_code) > 1:
                        trace_id = self.__get_trace_id(line)
                        if trace_id is None:
                            continue
                        if error_dict.get(ret_code) is None:
                            error_dict[ret_code] = {"file_name": file_full_path, "count": 1, "first_found_time": line_time, "last_found_time": line_time, "trace_id_list": {trace_id} if len(trace_id) > 0 else {}}
                        else:
                            count = error_dict[ret_code]["count"] + 1
                            first_found_time = error_dict[ret_code]["first_found_time"] if error_dict[ret_code]["first_found_time"] < line_time else line_time
                            last_found_time = error_dict[ret_code]["last_found_time"] if error_dict[ret_code]["last_found_time"] > line_time else line_time
                            trace_id_list = list(error_dict[ret_code]["trace_id_list"])
                            if not (trace_id in trace_id_list):
                                trace_id_list.append(trace_id)
                            error_dict[ret_code] = {"file_name": file_full_path, "count": count, "first_found_time": first_found_time, "last_found_time": last_found_time, "trace_id_list": trace_id_list}
                        if self.by_tenant:
                            tenant = self.__get_tenant_from_log_line(line)
                            self.__merge_tenant_error(tenant_error_dict, tenant, ret_code, file_full_path, line_time, line_time, trace_id)
        self.stdio.verbose("complete parse log {0}".format(file_full_path))
        return (error_dict, tenant_error_dict)

    def __merge_tenant_error(self, tenant_error_dict, tenant, ret_code, file_name, line_time_first, line_time_last, trace_id):
        """Merge one error occurrence into tenant_error_dict[tenant][ret_code]."""
        # Filter by tenant_id if specified
        if self.tenant_id_filter is not None:
            # Support both tenant name and tenant_id:xxx format
            if tenant == "_unknown_":
                return  # Skip unknown tenants when filter is specified
            # Check if tenant matches filter (exact match or tenant_id:xxx format)
            filter_match = False
            if tenant == self.tenant_id_filter:
                filter_match = True
            elif self.tenant_id_filter.startswith("tenant_id:"):
                # Filter format: tenant_id:123, match against tenant_id:xxx
                if tenant.startswith("tenant_id:") and tenant == self.tenant_id_filter:
                    filter_match = True
            elif tenant.startswith("tenant_id:"):
                # Extract numeric ID from tenant (tenant_id:123) and compare with filter (could be "123" or "tenant_id:123")
                tenant_id_num = tenant.replace("tenant_id:", "")
                if tenant_id_num == self.tenant_id_filter or self.tenant_id_filter == "tenant_id:" + tenant_id_num:
                    filter_match = True
            if not filter_match:
                return  # Skip this tenant if it doesn't match filter

        if tenant not in tenant_error_dict:
            tenant_error_dict[tenant] = {}
        if ret_code not in tenant_error_dict[tenant]:
            tenant_error_dict[tenant][ret_code] = {
                "file_name": file_name,
                "count": 0,
                "first_found_time": line_time_first,
                "last_found_time": line_time_last,
                "trace_id_list": [],
            }
        rec = tenant_error_dict[tenant][ret_code]
        rec["count"] += 1
        if rec["first_found_time"] > line_time_first or not rec["first_found_time"]:
            rec["first_found_time"] = line_time_first
        if rec["last_found_time"] < line_time_last:
            rec["last_found_time"] = line_time_last
        if trace_id and trace_id not in rec["trace_id_list"]:
            rec["trace_id_list"].append(trace_id)

    def __get_time_from_ob_log_line(self, log_line):
        """
        Get the time from the observer's log line
        :param log_line
        :return: time_str
        """
        time_str = ""
        if len(log_line) >= 28:
            time_str = log_line[1 : log_line.find(']')]
        return time_str

    def __get_trace_id(self, log_line):
        """
        Get the trace_id from the observer's log line
        :param log_line
        :return: trace_id
        """
        pattern = re.compile(r'\[Y(.*?)\]')
        find = pattern.search(log_line)
        if find and find.group(1):
            return find.group(1).strip('[').strip(']')

    def __get_log_level(self, log_line):
        """
        Get the log level from the observer's log line
        :param log_line
        :return: log level
        """
        level_lits = ["DEBUG ", "TRACE ", "INFO ", "WDIAG ", "WARN ", "EDIAG ", "ERROR ", "FATAL "]
        length = len(log_line)
        if length > 38:
            length = 38
        for level in level_lits:
            idx = log_line[:length].find(level)
            if idx != -1:
                return OBLogLevel().get_log_level(level.rstrip())
        return 0

    def __get_overall_summary(self, node_summary_tuples, is_files=False):
        """
        generate overall summary from all node summary tuples
        :param node_summary_tuple
        :return: a string indicating the overall summary
        """
        field_names = ["Node", "Status", "FileName", "First Found Time", "ErrorCode", "Message", "Count"]
        t = []
        t_details = []
        field_names_details = field_names
        field_names_details.extend(["Last Found Time", "Cause", "Solution", "Trace_IDS"])
        for tup in node_summary_tuples:
            is_empty = True
            node = tup[0]
            is_err = tup[2]
            node_results = tup[3]
            if is_err:
                is_empty = False
                t.append([node, "Error:" + tup[2] if is_err else "Completed", None, None, None, None])
                t_details.append([node, "Error:" + tup[2] if is_err else "Completed", None, None, None, None, None, None, None, None, None])
            for log_result in node_results:
                for ret_key, ret_value in log_result.items():
                    if ret_key is not None:
                        error_code_info = OB_RET_DICT.get(ret_key, "")
                        message = ""
                        if ret_key == "CRASH_ERROR":
                            message = self.crash_error
                        elif error_code_info == "":
                            continue
                        else:
                            message = error_code_info[1]
                        if len(error_code_info) > 3:
                            is_empty = False
                            t.append([node, "Error:" + tup[2] if is_err else "Completed", ret_value["file_name"], ret_value["first_found_time"], ret_key, message, ret_value["count"]])
                            t_details.append(
                                [
                                    node,
                                    "Error:" + tup[2] if is_err else "Completed",
                                    ret_value["file_name"],
                                    ret_value["first_found_time"],
                                    ret_key,
                                    message,
                                    ret_value["count"],
                                    ret_value["last_found_time"],
                                    error_code_info[2],
                                    error_code_info[3],
                                    str(ret_value["trace_id_list"]),
                                ]
                            )
            if is_empty:
                t.append([node, "PASS", None, None, None, None, None])
                t_details.append([node, "PASS", None, None, None, None, None, None, None, None, None])
        title = "\nAnalyze OceanBase Offline Log Summary:\n" if is_files else "\nAnalyze OceanBase Online Log Summary:\n"
        t.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=False)
        t_details.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=False)
        return title, field_names, t, t_details

    def __merge_tenant_results(self, tenant_results_list):
        """
        Merge list of tenant_error_dict from multiple files into one.
        tenant_results_list: list of dict[tenant][ret_code] = {file_name, count, first_found_time, last_found_time, trace_id_list}
        """
        merged = {}
        for tenant_dict in tenant_results_list:
            for tenant, ret_dict in tenant_dict.items():
                if tenant not in merged:
                    merged[tenant] = {}
                for ret_code, rec in ret_dict.items():
                    if ret_code not in merged[tenant]:
                        merged[tenant][ret_code] = {
                            "file_name": rec["file_name"],
                            "count": 0,
                            "first_found_time": rec["first_found_time"],
                            "last_found_time": rec["last_found_time"],
                            "trace_id_list": list(rec["trace_id_list"]) if isinstance(rec["trace_id_list"], list) else [],
                        }
                    else:
                        m = merged[tenant][ret_code]
                        m["count"] += rec["count"]
                        if rec["first_found_time"] and (not m["first_found_time"] or m["first_found_time"] > rec["first_found_time"]):
                            m["first_found_time"] = rec["first_found_time"]
                        if rec["last_found_time"] and (not m["last_found_time"] or m["last_found_time"] < rec["last_found_time"]):
                            m["last_found_time"] = rec["last_found_time"]
                        for tid in rec["trace_id_list"] if isinstance(rec["trace_id_list"], list) else []:
                            if tid and tid not in m["trace_id_list"]:
                                m["trace_id_list"].append(tid)
        return merged

    def __get_tenant_summary(self, tenant_results_list):
        """
        Build summary table by tenant dimension from merged tenant_error_dict.
        :param tenant_results_list: list of tenant_error_dict per file
        :return: (title, field_names, summary_list)
        """
        merged = self.__merge_tenant_results(tenant_results_list)
        field_names = ["Tenant", "ErrorCode", "Message", "Count", "First Found Time", "Last Found Time"]
        if self.tenant_id_filter:
            title = "\nAnalyze OceanBase Log Summary (By Tenant - Filtered: {0}):\n".format(self.tenant_id_filter)
        else:
            title = "\nAnalyze OceanBase Log Summary (By Tenant):\n"
        summary_list = []
        for tenant, ret_dict in sorted(merged.items()):
            # Additional filter check in summary (should already be filtered in __merge_tenant_error, but double-check)
            if self.tenant_id_filter is not None:
                filter_match = False
                if tenant == self.tenant_id_filter:
                    filter_match = True
                elif self.tenant_id_filter.startswith("tenant_id:"):
                    if tenant.startswith("tenant_id:") and tenant == self.tenant_id_filter:
                        filter_match = True
                elif tenant.startswith("tenant_id:"):
                    tenant_id_num = tenant.replace("tenant_id:", "")
                    if tenant_id_num == self.tenant_id_filter or self.tenant_id_filter == "tenant_id:" + tenant_id_num:
                        filter_match = True
                if not filter_match:
                    continue

            for ret_code, rec in ret_dict.items():
                error_code_info = OB_RET_DICT.get(ret_code, "")
                message = ""
                if ret_code == "CRASH_ERROR":
                    message = getattr(self, "crash_error", "") or "crash thread"
                elif error_code_info != "":
                    message = error_code_info[1] if len(error_code_info) > 1 else ""
                if not error_code_info and ret_code != "CRASH_ERROR":
                    continue
                summary_list.append(
                    [
                        tenant,
                        ret_code,
                        message,
                        rec["count"],
                        rec.get("first_found_time") or "",
                        rec.get("last_found_time") or "",
                    ]
                )
        summary_list.sort(key=lambda x: (x[0], x[1], x[3]), reverse=False)
        return title, field_names, summary_list
