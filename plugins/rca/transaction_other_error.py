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
@time: 2024/05/20
@file: transaction_other_error.py
@desc: Root cause analysis for transaction other errors.
       Handles error codes: -4013, -4030, -4121, -4122, -4124, -4019
       Reference: [4.0] 事务问题通用排查手册
"""
import os

from src.handler.rca.rca_exception import (
    RCAInitException,
    RCAExecuteException,
    RCANotNeedExecuteException,
)
from src.handler.rca.rca_handler import RcaScene
from src.common.tool import StringUtils

# Error code mapping based on the manual
ERROR_CODE_MAP = {
    "-4013": {"type": "memory", "msg": "No memory or reach tenant memory limit"},
    "-4030": {"type": "memory", "msg": "Over tenant memory limits"},
    "-4121": {"type": "rpc", "msg": "RPC send error"},
    "-4122": {"type": "rpc", "msg": "RPC post error"},
    "-4124": {"type": "rpc", "msg": "Connect error"},
    "-4019": {"type": "overflow", "msg": "Size overflow"},
}


class TransactionOtherErrorScene(RcaScene):
    def __init__(self):
        super().__init__()
        self.error_code = None
        self.error_info = None
        self.work_path = self.store_dir
        self.all_log_files = []

    def init(self, context):
        super().init(context)
        # observer version >= 4.0.0.0
        observer_version = self.observer_version
        if observer_version is None or len(observer_version.strip()) == 0:
            raise RCAInitException("observer version is None. Please check the NODES conf.")
        if not (observer_version == "4.0.0.0" or StringUtils.compare_versions_greater(observer_version, "4.0.0.0")):
            self.stdio.error("observer version is {0}, which is less than 4.0.0.0.".format(observer_version))
            raise RCAInitException("observer version is {0}, which is less than 4.0.0.0.".format(observer_version))
        if self.ob_connector is None:
            raise RCAInitException("ob_connector is None. Please check the NODES conf.")
        self.work_path = context.get_variable("store_dir")
        if not os.path.exists(self.work_path):
            os.makedirs(self.work_path)

        self.error_code = self.input_parameters.get("error_code")
        if not self.error_code:
            raise RCANotNeedExecuteException("error_code is empty. Please provide error_code by --env error_code=-4030")

        # Normalize error code format
        if not self.error_code.startswith("-"):
            self.error_code = "-" + self.error_code

        if self.error_code not in ERROR_CODE_MAP:
            supported_codes = ", ".join(ERROR_CODE_MAP.keys())
            raise RCANotNeedExecuteException("error_code {0} is not supported. Supported error codes: {1}".format(self.error_code, supported_codes))

        self.error_info = ERROR_CODE_MAP[self.error_code]
        self.record.add_record("error_code: {0}, type: {1}, msg: {2}".format(self.error_code, self.error_info["type"], self.error_info["msg"]))

    def verbose(self, info):
        self.stdio.verbose("[TransactionOtherErrorScene] {0}".format(info))

    def execute(self):
        try:
            syslog_level_data = self.ob_connector.execute_sql_return_cursor_dictionary('SHOW PARAMETERS like "syslog_level"').fetchall()
            self.record.add_record("syslog_level data is {0}".format(syslog_level_data[0].get("value") or None))

            error_type = self.error_info["type"]

            # Performance optimization: gather logs once, then analyze locally
            # This avoids multiple network transfers and file I/O operations
            work_path_all_logs = os.path.join(self.work_path, "all_logs")
            if not os.path.exists(work_path_all_logs):
                os.makedirs(work_path_all_logs)

            self.stdio.verbose("Gathering all relevant logs once for performance optimization")
            self.gather_log.set_parameters("scope", "observer")
            # Don't set grep here - gather all logs, then filter locally
            all_logs = self.gather_log.execute(save_path=work_path_all_logs)

            if not all_logs or len(all_logs) == 0:
                self.record.add_record("No logs gathered")
                self.record.add_suggest("No logs found. Please check log collection configuration.")
                return

            self.stdio.verbose("Gathered {0} log files, analyzing locally".format(len(all_logs)))
            self.record.add_record("Gathered {0} log files to {1}".format(len(all_logs), work_path_all_logs))

            # Store log files for local analysis
            self.all_log_files = all_logs

            if error_type == "memory":
                self._handle_memory_error()
            elif error_type == "rpc":
                self._handle_rpc_error()
            elif error_type == "overflow":
                self._handle_overflow_error()

        except RCANotNeedExecuteException:
            raise
        except Exception as e:
            raise RCAExecuteException("TransactionOtherErrorScene execute error: {0}".format(e))
        finally:
            self.stdio.verbose("end TransactionOtherErrorScene execute")

    def _handle_memory_error(self):
        """Handle memory related errors (-4013, -4030)"""
        self.record.add_record("Handling memory error: {0}".format(self.error_code))

        if self.error_code == "-4013":
            self.record.add_suggest("Error -4013: No memory or reach tenant memory limit. " "This is an OS-level memory issue. Please check system memory usage.")
        elif self.error_code == "-4030":
            self.record.add_suggest("Error -4030: Over tenant memory limits. " "Please expand tenant memory or check for memory leaks.")

        # Analyze MEMORY logs locally from already gathered logs
        work_path_memory = os.path.join(self.work_path, "MEMORY_logs")
        if not os.path.exists(work_path_memory):
            os.makedirs(work_path_memory)

        memory_logs = []
        for log_file in self.all_log_files:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines:
                        if "MEMORY" in line:
                            memory_logs.append(line)
            except Exception as e:
                self.verbose("Error reading log file {0}: {1}".format(log_file, e))

        if memory_logs:
            # Save filtered logs to separate file
            memory_log_file = os.path.join(work_path_memory, "memory_filtered.log")
            with open(memory_log_file, "w", encoding="utf-8") as f:
                f.writelines(memory_logs)
            self.record.add_record("Found {0} MEMORY log entries, saved to: {1}".format(len(memory_logs), work_path_memory))
            self.record.add_suggest("Please check memory logs in {0} for memory usage during the error time.".format(work_path_memory))
        else:
            self.record.add_record("No MEMORY logs found in gathered logs")

        # Check current memory status
        try:
            memory_sql = """
            SELECT tenant_id, svr_ip, 
                   round(hold/1024/1024/1024, 2) as hold_gb,
                   round(limit_value/1024/1024/1024, 2) as limit_gb,
                   round(hold/limit_value * 100, 2) as usage_percent
            FROM oceanbase.__all_virtual_memory_info 
            WHERE mod_name = 'OB_TENANT_MEMORY'
            ORDER BY usage_percent DESC
            LIMIT 10;
            """
            memory_data = self.ob_connector.execute_sql_return_cursor_dictionary(memory_sql).fetchall()
            if len(memory_data) > 0:
                self.record.add_record("Current memory usage: {0}".format(memory_data))
                for row in memory_data:
                    if row.get("usage_percent", 0) > 90:
                        self.record.add_suggest("Tenant {0} on {1} has high memory usage: {2}%".format(row.get("tenant_id"), row.get("svr_ip"), row.get("usage_percent")))
        except Exception as e:
            self.verbose("Failed to check memory status: {0}".format(e))

    def _handle_rpc_error(self):
        """Handle RPC related errors (-4121, -4122, -4124)"""
        self.record.add_record("Handling RPC error: {0}".format(self.error_code))

        self.record.add_suggest("RPC errors ({0}: {1}) are most likely caused by network issues. " "Please use 'tsar' to check network conditions during the error time.".format(self.error_code, self.error_info["msg"]))

        # Analyze EASY SLOW logs locally from already gathered logs
        work_path_easy_slow = os.path.join(self.work_path, "EASY_SLOW")
        if not os.path.exists(work_path_easy_slow):
            os.makedirs(work_path_easy_slow)

        easy_slow_logs = []
        for log_file in self.all_log_files:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines:
                        if "EASY SLOW" in line:
                            easy_slow_logs.append(line)
            except Exception as e:
                self.verbose("Error reading log file {0}: {1}".format(log_file, e))

        if easy_slow_logs:
            # Save filtered logs to separate file
            easy_slow_log_file = os.path.join(work_path_easy_slow, "easy_slow_filtered.log")
            with open(easy_slow_log_file, "w", encoding="utf-8") as f:
                f.writelines(easy_slow_logs)
            easy_slow_count = len(easy_slow_logs)
            self.record.add_record("Found {0} EASY SLOW log entries, saved to: {1}".format(easy_slow_count, work_path_easy_slow))

            if easy_slow_count >= 1000:
                self.record.add_suggest("EASY SLOW log count over 1000! This indicates serious network latency issues.")
            else:
                self.record.add_suggest("Found EASY SLOW logs indicating network latency. " "Please check network conditions and logs in {0}".format(work_path_easy_slow))
        else:
            self.record.add_record("No EASY SLOW logs found in gathered logs")

        # Analyze post trans errors locally from already gathered logs
        work_path_post_trans = os.path.join(self.work_path, "post_trans")
        if not os.path.exists(work_path_post_trans):
            os.makedirs(work_path_post_trans)

        post_trans_logs = []
        for log_file in self.all_log_files:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines:
                        if "post trans" in line:
                            post_trans_logs.append(line)
            except Exception as e:
                self.verbose("Error reading log file {0}: {1}".format(log_file, e))

        if post_trans_logs:
            # Save filtered logs to separate file
            post_trans_log_file = os.path.join(work_path_post_trans, "post_trans_filtered.log")
            with open(post_trans_log_file, "w", encoding="utf-8") as f:
                f.writelines(post_trans_logs)
            self.record.add_record("Found {0} 'post trans' log entries, saved to: {1}".format(len(post_trans_logs), work_path_post_trans))
            self.record.add_suggest("Found transaction RPC send failures. Check logs in {0} for details.".format(work_path_post_trans))
        else:
            self.record.add_record("No 'post trans' logs found in gathered logs")

    def _handle_overflow_error(self):
        """Handle size overflow error (-4019)"""
        self.record.add_record("Handling overflow error: {0}".format(self.error_code))

        self.record.add_suggest("Error -4019: Size overflow. This is likely caused by a deadlock in OceanBase. " "Please use 'pstack' to analyze the observer process.")

        # Suggest gathering pstack
        self.record.add_suggest("To diagnose, please run: pstack <observer_pid> > pstack_output.txt " "and send the output to OceanBase community for analysis.")

    def get_scene_info(self):
        return {
            "name": "transaction_other_error",
            "info_en": "Root cause analysis for other transaction errors. Supports error codes: -4013 (No memory), -4030 (Over tenant memory), -4121 (RPC send error), -4122 (RPC post error), -4124 (Connect error), -4019 (Size overflow)",
            "info_cn": "事务其他错误的根因分析，支持错误码：-4013（系统内存不足），-4030（租户内存超限），-4121（RPC发送错误），-4122（RPC投递错误），-4124（连接错误），-4019（大小溢出）",
        }


transaction_other_error = TransactionOtherErrorScene()
