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
@file: analyze_variable.py
@desc:
"""
import os
from src.common.base_handler import BaseHandler
from src.common.tool import DirectoryUtil, TimeUtils, Util
from src.common.obdiag_exception import OBDIAGFormatException
from src.common.ob_connector import OBConnector
import csv
from prettytable import PrettyTable
import datetime
from colorama import Fore, Style

from src.common.result_type import ObdiagResult


class AnalyzeVariableHandler(BaseHandler):
    def _init(self, analyze_type='diff', **kwargs):
        """Subclass initialization"""
        self.export_report_path = None
        self.variable_file_name = None
        self.analyze_type = analyze_type
        self.ob_cluster = self.context.cluster_config

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

    def handle(self) -> ObdiagResult:
        """Main handle logic"""
        self._validate_initialized()

        try:
            if not self.init_option():
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="init option failed")
            self._log_verbose(f"Use {self.export_report_path} as pack dir.")
            DirectoryUtil.mkdir(path=self.export_report_path, stdio=self.stdio)
            return self.execute()

        except Exception as e:
            return self._handle_error(e)

    def check_file_valid(self):
        with open(self.variable_file_name, 'r') as f:
            header = f.readline()
            flag = 1
            if header:
                header = header.strip()
            if not header:
                flag = 0
            if not header.startswith('VERSION'):
                flag = 0
            if not header.endswith('RECORD_TIME'):
                flag = 0
            if flag == 0:
                self._log_error(f'args --file [{os.path.abspath(self.variable_file_name)}] is not a valid variable file, Please specify it again')
                return False
            else:
                return True

    def init_option(self):
        store_dir_option = self._get_option('store_dir')
        offline_file_option = self._get_option('file')

        if offline_file_option:
            if not os.path.exists(os.path.abspath(offline_file_option)):
                self._log_error(f'args --file [{os.path.abspath(offline_file_option)}] not exist: No such file, Please specify it again')
                return False
            else:
                self.variable_file_name = os.path.abspath(offline_file_option)
                if not self.check_file_valid():
                    return False
        else:
            self._log_error("args --file need provided to find the parts where variables have changed.")
            return False

        if store_dir_option and store_dir_option != "./":
            if not os.path.exists(os.path.abspath(store_dir_option)):
                self._log_warn(f'args --store_dir [{os.path.abspath(store_dir_option)}] incorrect: No such directory, Now create it')
                os.makedirs(os.path.abspath(store_dir_option))
            self.export_report_path = os.path.abspath(store_dir_option)
        else:
            store_dir_option = './variable_report'
            if not os.path.exists(os.path.abspath(store_dir_option)):
                self._log_warn(f'The report directory is not specified, and a "variable_report" directory will be created in the current directory.')
                os.makedirs(os.path.abspath(store_dir_option))
            self.export_report_path = os.path.abspath(store_dir_option)

        return True

    def analyze_variable(self):
        sql = '''select version(), tenant_id, zone, name,gmt_modified, value, flags, min_val, max_val, now() 
        from oceanbase.__all_virtual_sys_variable order by 2, 4, 5'''
        db_variable_info = self.obconn.execute_sql(sql)
        db_variable_dict = dict()
        for row in db_variable_info:
            key = str(row[1]) + '-' + str(row[3])
            db_variable_dict[key] = str(row[5])
        file_variable_dict = dict()
        last_gather_time = ''
        with open(self.variable_file_name, 'r', newline='') as file:
            reader = csv.reader(file)
            for row in reader:
                if row[0] == 'VERSION':
                    continue
                key = str(row[1]) + '-' + str(row[3])
                file_variable_dict[key] = str(row[5])
                if not last_gather_time:
                    last_gather_time = row[-1]
        report_default_tb = PrettyTable(["VERSION", "TENANT_ID", "ZONE", "NAME", "LAST_VALUE", "CURRENT_VALUE"])
        changed_variables_dict = dict()
        for key in db_variable_dict:
            if key in file_variable_dict and db_variable_dict[key] != file_variable_dict[key]:
                changed_variables_dict[key] = file_variable_dict[key]
        is_empty = True
        for k in changed_variables_dict:
            for row in db_variable_info:
                key = str(row[1]) + '-' + str(row[3])
                if k == key:
                    report_default_tb.add_row([row[0], row[1], row[2], row[3], changed_variables_dict[key], row[5]])
                    is_empty = False
        if not is_empty:
            now = datetime.datetime.now()
            date_format = now.strftime("%Y-%m-%d-%H-%M-%S")
            file_name = f'{self.export_report_path}/variables_changed_{date_format}.table'
            fp = open(file_name, 'a+', encoding="utf8")
            fp.write(report_default_tb.get_string() + "\n")
            fp.close()
            self._log_info(Fore.RED + f"Since {last_gather_time}, the following variables have changed：" + Style.RESET_ALL)
            self._log_info(report_default_tb.get_string())
            self._log_info("Analyze variables changed finished. For more details, please run cmd '" + Fore.YELLOW + f" cat {file_name} " + Style.RESET_ALL + "'")
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": report_default_tb.get_string()})
        else:
            self._log_info(f"Analyze variables changed finished. Since {last_gather_time}, No changes in variables")
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"result": f"Since {last_gather_time}, No changes in variables"})

    def execute(self):
        try:
            return self.analyze_variable()
        except Exception as e:
            self._log_error(f"variable info analyze failed, error message: {e}")
