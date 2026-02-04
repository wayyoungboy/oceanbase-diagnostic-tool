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
@time: 2024/6/16
@file: analyze_parameter.py
@desc:
"""
import os
from src.common.base_handler import BaseHandler
from src.common.command import get_observer_version_by_sql
from src.common.tool import DirectoryUtil, TimeUtils, Util, StringUtils
from src.common.obdiag_exception import OBDIAGFormatException
from src.common.ob_connector import OBConnector
import csv
from prettytable import PrettyTable
import json
import datetime
from colorama import Fore, Style

from src.common.result_type import ObdiagResult


class AnalyzeParameterHandler(BaseHandler):
    def _init(self, analyze_type='default', **kwargs):
        """Subclass initialization"""
        self.export_report_path = None
        self.parameter_file_name = None
        self.ob_cluster = self.context.cluster_config
        self.analyze_type = analyze_type

        if self.context.get_variable("gather_timestamp", None):
            self.analyze_timestamp = self.context.get_variable("gather_timestamp")
        else:
            self.analyze_timestamp = TimeUtils.get_current_us_timestamp()

        self.observer_nodes = self.context.cluster_config.get("servers")

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
            raise OBDIAGFormatException(f"Failed to connect to database: {e}")

    def get_version(self):
        observer_version = ""
        try:
            observer_version = get_observer_version_by_sql(self.context, self.ob_cluster)
        except Exception as e:
            self._log_warn(f"failed to get observer version:{e}")
        self._log_verbose(f"get observer version: {observer_version}")
        return observer_version

    def handle(self) -> ObdiagResult:
        """Main handle logic"""
        self._validate_initialized()

        try:
            if self.analyze_type == 'default':
                if not self.init_option_default():
                    return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="init option failed")
            else:
                if not self.init_option_diff():
                    return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="init option failed")
            self._log_verbose(f"Use {self.export_report_path} as pack dir.")
            DirectoryUtil.mkdir(path=self.export_report_path, stdio=self.stdio)
            return self.execute()

        except Exception as e:
            return self._handle_error(e)

    def check_file_valid(self):
        with open(self.parameter_file_name, 'r') as f:
            header = f.readline()
            flag = 1
            if header:
                header = header.strip()
            if not header:
                flag = 0
            if not header.startswith('VERSION'):
                flag = 0
            if not header.endswith('ISDEFAULT'):
                flag = 0
            if flag == 0:
                self._log_error(f'args --file [{os.path.abspath(self.parameter_file_name)}] is not a valid parameter file, Please specify it again')
                return False
            else:
                return True

    def init_option_default(self):
        store_dir_option = self._get_option('store_dir')
        offline_file_option = self._get_option('file')

        if store_dir_option and store_dir_option != "./":
            if not os.path.exists(os.path.abspath(store_dir_option)):
                self._log_warn(f'args --store_dir [{os.path.abspath(store_dir_option)}] incorrect: No such directory, Now create it')
                os.makedirs(os.path.abspath(store_dir_option))
            self.export_report_path = os.path.abspath(store_dir_option)
        else:
            # Default to current directory if not specified
            self.export_report_path = "./"

        # Create timestamped subdirectory similar to gather
        target_dir = "obdiag_analyze_{0}".format(TimeUtils.timestamp_to_filename_time(TimeUtils.get_current_us_timestamp()))
        self.export_report_path = os.path.join(self.export_report_path, target_dir)
        if not os.path.exists(self.export_report_path):
            os.makedirs(self.export_report_path, exist_ok=True)

        if offline_file_option:
            if not os.path.exists(os.path.abspath(offline_file_option)):
                self._log_error(f'args --file [{os.path.abspath(offline_file_option)}] not exist: No such file, Please specify it again')
                return False
            else:
                self.parameter_file_name = os.path.abspath(offline_file_option)
                if not self.check_file_valid():
                    return False
        return True

    def init_option_diff(self):
        store_dir_option = self._get_option('store_dir')
        offline_file_option = self._get_option('file')

        if store_dir_option and store_dir_option != "./":
            if not os.path.exists(os.path.abspath(store_dir_option)):
                self._log_warn(f'args --store_dir [{os.path.abspath(store_dir_option)}] incorrect: No such directory, Now create it')
                os.makedirs(os.path.abspath(store_dir_option))
            self.export_report_path = os.path.abspath(store_dir_option)
        else:
            # Default to current directory if not specified
            self.export_report_path = "./"

        # Create timestamped subdirectory similar to gather
        target_dir = "obdiag_analyze_{0}".format(TimeUtils.timestamp_to_filename_time(TimeUtils.get_current_us_timestamp()))
        self.export_report_path = os.path.join(self.export_report_path, target_dir)
        if not os.path.exists(self.export_report_path):
            os.makedirs(self.export_report_path, exist_ok=True)

        if offline_file_option:
            if not os.path.exists(os.path.abspath(offline_file_option)):
                self._log_error(f'args --file [{os.path.abspath(offline_file_option)}] not exist: No such file, Please specify it again')
                return False
            else:
                self.parameter_file_name = os.path.abspath(offline_file_option)
                if not self.check_file_valid():
                    return False
        return True

    def analyze_parameter_default(self):
        observer_version = self.get_version()

        if StringUtils.compare_versions_greater(observer_version, "4.2.2.0"):
            if self.parameter_file_name is not None:
                self._log_warn("the version of OceanBase is greater than 4.2.2, an initialization parameter file will be ignored")
            sql = '''select substr(version(),8), svr_ip,svr_port,zone,scope,TENANT_ID,name,value,section,
EDIT_LEVEL, now(),default_value,isdefault from GV$OB_PARAMETERS where isdefault='NO' order by 5,2,3,4,7'''
            parameter_info = self.obconn.execute_sql(sql)
            report_default_tb = PrettyTable(["IP", "PORT", "ZONE", "CLUSTER", "TENANT_ID", "NAME", "DEFAULT_VALUE", "CURRENT_VALUE"])
            now = datetime.datetime.now()
            date_format = now.strftime("%Y-%m-%d-%H-%M-%S")
            file_name = f'{self.export_report_path}/parameter_default_{date_format}.table'
            fp = open(file_name, 'a+', encoding="utf8")

            # Prepare structured data for JSON output (when silent mode)
            structured_data = []

            for row in parameter_info:
                if row[5] is None:
                    tenant_id = 'None'
                else:
                    tenant_id = row[5]
                report_default_tb.add_row([row[1], row[2], row[3], row[4], tenant_id, row[6], row[11], row[7]])

                # Build structured data for JSON output
                if self.stdio and self.stdio.silent:
                    # Safely convert tenant_id
                    tenant_id_value = None
                    if tenant_id != 'None' and tenant_id:
                        try:
                            tenant_id_value = int(tenant_id)
                        except (ValueError, TypeError):
                            tenant_id_value = tenant_id

                    structured_data.append(
                        {
                            "ip": str(row[1]) if row[1] else None,
                            "port": int(row[2]) if row[2] else None,
                            "zone": str(row[3]) if row[3] else None,
                            "cluster": str(row[4]) if row[4] else None,
                            "tenant_id": tenant_id_value,
                            "name": str(row[6]) if row[6] else None,
                            "default_value": str(row[11]) if row[11] else None,
                            "current_value": str(row[7]) if row[7] else None,
                        }
                    )

            fp.write(report_default_tb.get_string() + "\n")
            self._log_info(report_default_tb.get_string())
            self._log_info("Analyze parameter default finished. For more details, please run cmd '" + Fore.YELLOW + f" cat {file_name} " + Style.RESET_ALL + "'")

            # Return structured JSON data in silent mode, table string otherwise
            if self.stdio and self.stdio.silent:
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": structured_data, "file_name": file_name})
            else:
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": report_default_tb.get_string(), "file_name": file_name})
        else:
            if self.parameter_file_name is None:
                self._log_error("the version of OceanBase is lower than 4.2.2, an initialization parameter file must be provided to find non-default values")
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="the version of OceanBase is lower than 4.2.2, an initialization parameter file must be provided to find non-default values")
            else:
                # Use version-specific table query
                if StringUtils.compare_versions_greater(observer_version, "4.0.0.0"):
                    sql = '''select substr(version(),8), svr_ip,svr_port,zone,scope,TENANT_ID,name,value,section,
EDIT_LEVEL, now(),'','' from GV$OB_PARAMETERS order by 5,2,3,4,7'''
                else:
                    # For versions < 4.0, use union of tenant and system parameter tables
                    sql = '''select version(), svr_ip,svr_port,zone,scope,TENANT_ID,name,value,section,
EDIT_LEVEL, now(), '','' from oceanbase.__all_virtual_tenant_parameter_info
union
select version(), svr_ip,svr_port,zone,scope,'None' tenant_id,name,value,section,
EDIT_LEVEL, now(), '','' from oceanbase.__all_virtual_sys_parameter_stat where scope='CLUSTER'
order by 5,2,3,4,7'''
                db_parameter_info = self.obconn.execute_sql(sql)
                db_parameter_dict = dict()
                for row in db_parameter_info:
                    key = str(row[1]) + '-' + str(row[2]) + '-' + str(row[3]) + '-' + str(row[4]) + '-' + str(row[5]) + '-' + str(row[6])
                    value = row[7]
                    db_parameter_dict[key] = value
                file_parameter_dict = dict()
                with open(self.parameter_file_name, 'r', newline='') as file:
                    reader = csv.reader(file)
                    for row in reader:
                        if row[0] == 'VERSION':
                            continue
                        key = str(row[1]) + '-' + str(row[2]) + '-' + str(row[3]) + '-' + str(row[4]) + '-' + str(row[5]) + '-' + str(row[6])
                        value = row[7]
                        file_parameter_dict[key] = value
                report_default_tb = PrettyTable(["IP", "PORT", "ZONE", "CLUSTER", "TENANT_ID", "NAME", "DEFAULT_VALUE", "CURRENT_VALUE"])
                now = datetime.datetime.now()
                date_format = now.strftime("%Y-%m-%d-%H-%M-%S")
                file_name = f'{self.export_report_path}/parameter_default_{date_format}.table'
                fp = open(file_name, 'a+', encoding="utf8")
                is_empty = True

                # Prepare structured data for JSON output (when silent mode)
                structured_data = []

                for key in db_parameter_dict:
                    if key in file_parameter_dict and db_parameter_dict[key] != file_parameter_dict[key]:
                        col_list = key.split('-')
                        # Fix: col_list[1] should be PORT, not col_list[0]
                        port = col_list[1] if len(col_list) > 1 else col_list[0]
                        report_default_tb.add_row([col_list[0], port, col_list[2], col_list[3], col_list[4], col_list[5], file_parameter_dict[key], db_parameter_dict[key]])
                        is_empty = False

                        # Build structured data for JSON output
                        if self.stdio and self.stdio.silent:
                            tenant_id_raw = col_list[4] if len(col_list) > 4 else None
                            # Safely convert tenant_id
                            tenant_id_value = None
                            if tenant_id_raw and tenant_id_raw != 'None':
                                try:
                                    tenant_id_value = int(tenant_id_raw)
                                except (ValueError, TypeError):
                                    tenant_id_value = tenant_id_raw

                            structured_data.append(
                                {
                                    "ip": col_list[0] if len(col_list) > 0 else None,
                                    "port": int(port) if port and port.isdigit() else None,
                                    "zone": col_list[2] if len(col_list) > 2 else None,
                                    "cluster": col_list[3] if len(col_list) > 3 else None,
                                    "tenant_id": tenant_id_value,
                                    "name": col_list[5] if len(col_list) > 5 else None,
                                    "default_value": file_parameter_dict[key],
                                    "current_value": db_parameter_dict[key],
                                }
                            )

                fp.write(report_default_tb.get_string() + "\n")
                if not is_empty:
                    self._log_info(report_default_tb.get_string())
                    self._log_info("Analyze parameter default finished. For more details, please run cmd '" + Fore.YELLOW + f" cat {file_name} " + Style.RESET_ALL + "'")

                    # Return structured JSON data in silent mode, table string otherwise
                    if self.stdio and self.stdio.silent:
                        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": structured_data, "file_name": file_name})
                    else:
                        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": report_default_tb.get_string(), "file_name": file_name})
                else:
                    self._log_info("Analyze parameter default finished. All parameter values are the same as the default values.")
                    # Return empty list in silent mode for consistency
                    if self.stdio and self.stdio.silent:
                        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": [], "file_name": file_name, "message": "All parameter values are the same as the default values"})
                    else:
                        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": "Analyze parameter default finished. All parameter values are the same as the default values.", "file_name": file_name})

    def alalyze_parameter_diff(self):
        if self.parameter_file_name is None:
            # Use version-specific table query
            observer_version = self.get_version()

            if StringUtils.compare_versions_greater(observer_version, "4.0.0.0"):
                sql = '''select substr(version(),8), svr_ip,svr_port,zone,scope,TENANT_ID,name,value,section,
EDIT_LEVEL, now(),'','' from GV$OB_PARAMETERS order by 5,2,3,4,7'''
            else:
                # For versions < 4.0, use union of tenant and system parameter tables
                sql = '''select version(), svr_ip,svr_port,zone,scope,TENANT_ID,name,value,section,
EDIT_LEVEL, now(), '','' from oceanbase.__all_virtual_tenant_parameter_info
union
select version(), svr_ip,svr_port,zone,scope,'None' tenant_id,name,value,section,
EDIT_LEVEL, now(), '','' from oceanbase.__all_virtual_sys_parameter_stat where scope='CLUSTER'
order by 5,2,3,4,7'''

            parameter_info = self.obconn.execute_sql(sql)
        else:
            parameter_info = []
            with open(self.parameter_file_name, 'r', newline='') as file:
                reader = csv.reader(file)
                for row in reader:
                    if row[0] == 'VERSION':
                        continue
                    parameter_info.append(row)
        tenants_dict = dict()
        for row in parameter_info:
            if row[5] is None:
                scope = 'CLUSTER'
            else:
                scope = row[5]
            tenant_id = str(scope)
            observer = str(row[1]) + ':' + str(row[2])
            name = row[6]
            value = row[7]
            if tenant_id not in tenants_dict:
                tenants_dict[tenant_id] = []
                tenants_dict[tenant_id].append({'observer': observer, 'name': name, 'value': value})
            else:
                tenants_dict[tenant_id].append({'observer': observer, 'name': name, 'value': value})
        diff_parameter_dict = dict()
        for tenant, parameters_list in tenants_dict.items():
            diff_parameter_dict[tenant] = []
            parameter_dict = dict()
            for parameter_info in parameters_list:
                name = parameter_info['name']
                observer = parameter_info['observer']
                value = parameter_info['value']
                if name not in parameter_dict:
                    parameter_dict[name] = []
                    parameter_dict[name].append({'observer': observer, 'value': value})
                else:
                    parameter_dict[name].append({'observer': observer, 'value': value})

            for name, value_list in parameter_dict.items():
                if name in ['local_ip', 'observer_id', 'zone']:
                    continue
                value_set = set()
                for value_info in value_list:
                    value_set.add(value_info['value'])
                if len(value_set) > 1:
                    diff_parameter_dict[tenant].append({'name': name, 'value_list': value_list})
        now = datetime.datetime.now()
        date_format = now.strftime("%Y-%m-%d-%H-%M-%S")
        file_name = self.export_report_path + '/parameter_diff_{0}.table'.format(date_format)
        fp = open(file_name, 'a+', encoding="utf8")
        is_empty = True
        report_diff_tbs = []

        # Prepare structured data for JSON output (when silent mode)
        structured_data = []

        for tenant, value_list in diff_parameter_dict.items():
            if len(value_list) > 0:
                report_diff_tb = PrettyTable(["name", "diff"])
                report_diff_tb.align["task_report"] = "l"
                if tenant == 'CLUSTER':
                    report_diff_tb.title = 'SCOPE:' + tenant
                else:
                    report_diff_tb.title = 'SCOPE:TENANT-' + tenant

                # Build structured data for JSON output
                tenant_data = {"scope": tenant, "parameters": []}

                for value_dict in value_list:
                    value_str_list = []
                    for value in value_dict['value_list']:
                        value_str = json.dumps(value)
                        value_str_list.append(value_str)
                    report_diff_tb.add_row([value_dict['name'], '\n'.join(value_str_list)])

                    # Add to structured data
                    if self.stdio and self.stdio.silent:
                        tenant_data["parameters"].append({"name": value_dict['name'], "diff": value_dict['value_list']})  # Already a list of dicts with observer and value

                fp.write(report_diff_tb.get_string() + "\n")
                self._log_info(report_diff_tb.get_string())
                is_empty = False
                report_diff_tbs.append(report_diff_tb.get_string())

                if self.stdio and self.stdio.silent and tenant_data["parameters"]:
                    structured_data.append(tenant_data)

        fp.close()
        if not is_empty:
            self._log_info("Analyze parameter diff finished. For more details, please run cmd '" + Fore.YELLOW + f" cat {file_name} " + Style.RESET_ALL + "'")

            # Return structured JSON data in silent mode, table string otherwise
            if self.stdio and self.stdio.silent:
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": structured_data, "store_dir": file_name})
            else:
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": report_diff_tbs, "store_dir": file_name})
        else:
            self._log_info("Analyze parameter diff finished. All parameter settings are consistent among observers")
            message = "Analyze parameter diff finished. All parameter settings are consistent among observers"
            if self.stdio and self.stdio.silent:
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": [], "message": message})
            else:
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": message})

    def execute(self):
        try:
            if self.analyze_type == 'default':
                return self.analyze_parameter_default()
            elif self.analyze_type == 'diff':
                return self.alalyze_parameter_diff()
        except Exception as e:
            self._log_error(f"parameter info analyze failed, error message: {e}")
