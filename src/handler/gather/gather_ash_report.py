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
@time: 2024/4/28
@file: gather_ash_report.py
@desc:
"""
import datetime
import os
import traceback

from src.common.base_handler import BaseHandler
from src.common.command import get_observer_version
from src.common.ob_connector import OBConnector
from src.common.obdiag_exception import OBDIAGFormatException, OBDIAGException
from src.common.tool import DirectoryUtil, TimeUtils, Util, StringUtils
from src.common.result_type import ObdiagResult
from colorama import Fore, Style
from src.common.version import OBDIAG_VERSION


class GatherAshReportHandler(BaseHandler):
    def _init(self, gather_pack_dir='./', **kwargs):
        """Subclass initialization"""
        self.result_summary_file_name = None
        self.report_type = None
        self.wait_class = None
        self.sql_id = None
        self.ash_report_file_name = None
        self.from_time_str = None
        self.to_time_str = None
        self.ash_sql = None
        self.trace_id = None
        self.svr_ip = None
        self.svr_port = None
        self.tenant_id = None
        self.gather_pack_dir = gather_pack_dir
        self.ob_cluster = self.context.cluster_config
        self.ob_version = None

        if self.context.get_variable("gather_timestamp", None):
            self.gather_timestamp = self.context.get_variable("gather_timestamp")
        else:
            self.gather_timestamp = TimeUtils.get_current_us_timestamp()

        self.cluster = self.context.cluster_config
        self.observer_nodes = self.context.cluster_config.get("servers")

        try:
            self.obconn = OBConnector(
                context=self.context,
                ip=self.cluster.get("db_host"),
                port=self.cluster.get("db_port"),
                username=self.cluster.get("tenant_sys").get("user"),
                password=self.cluster.get("tenant_sys").get("password"),
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
            if not self.version_check():
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="version check failed")
            if not self.init_option():
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="init option failed")
            self.__init_report_path()
            self.execute()
            return self.__print_result()

        except Exception as e:
            return self._handle_error(e)

    def version_check(self):
        observer_version = ""
        try:
            observer_version = get_observer_version(self.context)
        except Exception as e:
            self._log_verbose(traceback.format_exc())
            self._log_warn(f"ash Failed to get observer version:{e}")
            return False
        self.ob_version = observer_version
        self._log_verbose(f"ash.init get observer version: {observer_version}")
        if not (observer_version == "4.1.0.0" or StringUtils.compare_versions_greater(observer_version, "4.1.0.0")):
            self._log_error(f"observer version: {observer_version}, must greater than 4.1.0.0")
            return False
        return True

    def execute(self):
        try:
            # Check if version supports new parameters (4.3.5.0 and higher)
            if StringUtils.compare_versions_greater(self.ob_version, "4.3.5.0") or self.ob_version == "4.3.5.0":
                # 4.3.5.0+ supports 9 parameters: BTIME, ETIME, SQL_ID, TRACE_ID, WAIT_CLASS, REPORT_TYPE, SVR_IP, SVR_PORT, TENANT_ID
                ash_report_arg = (self.from_time_str, self.to_time_str, self.sql_id, self.trace_id, self.wait_class, self.report_type, self.svr_ip, self.svr_port, self.tenant_id)
            else:
                # Older versions only support 6 parameters: BTIME, ETIME, SQL_ID, TRACE_ID, WAIT_CLASS, REPORT_TYPE
                ash_report_arg = (self.from_time_str, self.to_time_str, self.sql_id, self.trace_id, self.wait_class, self.report_type)
            self._log_verbose(f"ash report arg: {ash_report_arg}")
            ash_report_data = self.obconn.callproc("DBMS_WORKLOAD_REPOSITORY.ASH_REPORT", args=ash_report_arg)
            if not ash_report_data or len(ash_report_data) == 0:
                self._log_error("ash report data is empty")
                raise OBDIAGException("ash report data is empty")
            ash_report = ash_report_data[0][0]
            if len(ash_report) > 1:
                self._log_verbose(f"ash report: \n{ash_report}")
            else:
                raise OBDIAGException("ash report data is empty")

            # save ash_report_data
            self.ash_report_file_name = f"ash_report_{TimeUtils.timestamp_to_filename_time(self.gather_timestamp)}."
            # Add suffix name
            if self.report_type == "html":
                self.ash_report_file_name += "html"
            elif self.report_type == "text":
                self.ash_report_file_name += "txt"

            self.ash_report_file_name = os.path.join(self.report_path, self.ash_report_file_name)

            with open(self.ash_report_file_name, 'w+') as f:
                f.write(f"obdiag version: {OBDIAG_VERSION}\n")
                f.write(f"observer version: {self.ob_version}\n")
                f.write(ash_report)
            self._log_info("save ash report file name: " + Fore.YELLOW + f"{self.ash_report_file_name}" + Style.RESET_ALL)
            self.result_summary_file_name = os.path.join(self.report_path, "result_summary.txt")
            with open(self.result_summary_file_name, 'w+') as f:
                f.write(self.ash_report_file_name)

        except Exception as e:
            self._log_verbose(traceback.format_exc())
            self._log_error(f"ash report gather failed, error message: {e}")

    def __init_report_path(self):
        try:
            self.report_path = os.path.join(self.gather_pack_dir, f"obdiag_gather_pack_{TimeUtils.timestamp_to_filename_time(self.gather_timestamp)}")
            self._log_verbose(f"Use {self.report_path} as pack dir.")
            DirectoryUtil.mkdir(path=self.report_path, stdio=self.stdio)
        except Exception as e:
            self._log_verbose(traceback.format_exc())
            self._log_error(f"init_report_path failed, error:{e}")

    def init_option(self):
        from_option = self._get_option('from')
        to_option = self._get_option('to')
        trace_id_option = self._get_option('trace_id')
        sql_id_option = self._get_option('sql_id')
        report_type_option = self._get_option('report_type')
        wait_class_option = self._get_option('wait_class')
        store_dir_option = self._get_option('store_dir')

        since_option = "30m"
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
        elif from_option is None or to_option is None:
            now_time = datetime.datetime.now()
            self.to_time_str = (now_time + datetime.timedelta(minutes=0)).strftime('%Y-%m-%d %H:%M:%S')
            self.from_time_str = (now_time - datetime.timedelta(seconds=TimeUtils.parse_time_length_to_sec(since_option))).strftime('%Y-%m-%d %H:%M:%S')
            self._log_info(f'gather from_time: {self.from_time_str}, to_time: {self.to_time_str}')
        else:
            self._log_info('No time option provided, default processing is based on the last 30 minutes')
            now_time = datetime.datetime.now()
            self.to_time_str = (now_time + datetime.timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
            self.from_time_str = (now_time - datetime.timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
            self._log_info(f'gather from_time: {self.from_time_str}, to_time: {self.to_time_str}')

        if store_dir_option:
            if not os.path.exists(os.path.abspath(store_dir_option)):
                self._log_warn(f'args --store_dir [{os.path.abspath(store_dir_option)}] incorrect: No such directory, Now create it')
                os.makedirs(os.path.abspath(store_dir_option))
            self.gather_pack_dir = os.path.abspath(store_dir_option)

        if sql_id_option:
            self.sql_id = sql_id_option
        else:
            self.sql_id = None
        if trace_id_option:
            self.trace_id = trace_id_option
        else:
            self.trace_id = None

        if report_type_option:
            self.report_type = report_type_option.strip().lower()
            report_type_list = ["text", "html"]
            if self.report_type not in report_type_list:
                raise ValueError("Invalid argument for report type, Now just support TEXT and HTML")
            if self.report_type != "text":
                if not (self.ob_version == "4.2.4.0" or StringUtils.compare_versions_greater(self.ob_version, "4.2.4.0")):
                    if self.report_type == "html":
                        self._log_warn(f"observer version: {self.ob_version}, html report is not supported. must greater than 4.2.4.0. The report_type reset 'text'")
                        self.report_type = "text"
        else:
            self.report_type = None

        if wait_class_option:
            self.wait_class = wait_class_option
        else:
            self.wait_class = None

        if store_dir_option:
            self.gather_pack_dir = store_dir_option
        else:
            self.gather_pack_dir = "/"

        # Parse new parameters for 4.3.5.0 and higher
        svr_ip_option = self._get_option('svr_ip')
        svr_port_option = self._get_option('svr_port')
        tenant_id_option = self._get_option('tenant_id')

        if svr_ip_option:
            self.svr_ip = svr_ip_option
        else:
            self.svr_ip = None
        if svr_port_option:
            self.svr_port = svr_port_option
        else:
            self.svr_port = None
        if tenant_id_option:
            self.tenant_id = tenant_id_option
        else:
            self.tenant_id = None

        # Check version for new parameters
        if (self.svr_ip or self.svr_port or self.tenant_id) and not (StringUtils.compare_versions_greater(self.ob_version, "4.3.5.0") or self.ob_version == "4.3.5.0"):
            self._log_warn(f"observer version: {self.ob_version}, svr_ip/svr_port/tenant_id parameters are only supported in version 4.3.5.0 or higher. These parameters will be ignored.")
            self.svr_ip = None
            self.svr_port = None
            self.tenant_id = None

        self._log_info(
            f"from_time: {self.from_time_str}, to_time: {self.to_time_str}, sql_id: {self.sql_id}, trace_id: {self.trace_id}, report_type: {self.report_type}, wait_class: {self.wait_class}, store_dir: {self.gather_pack_dir}, svr_ip: {self.svr_ip}, svr_port: {self.svr_port}, tenant_id: {self.tenant_id}"
        )

        return True

    def __print_result(self):
        self._log_info(Fore.YELLOW + f"\nGather ash_report results stored in this directory: {self.report_path}" + Style.RESET_ALL)
        self._log_info("")
        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"store_dir": self.report_path})
