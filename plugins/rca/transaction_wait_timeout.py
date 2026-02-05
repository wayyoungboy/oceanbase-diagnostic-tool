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
@file: transaction_wait_timeout.py
@desc: Root cause analysis for lock wait timeout.
       NOTE: This scene is now integrated into lock_conflict scene.
       Supports: "Shared lock conflict" (-6004) and "Lock wait timeout exceeded" (-6003)
       Reference: [4.0] 事务问题通用排查手册
"""
import os
import re

from src.handler.rca.rca_exception import (
    RCAInitException,
    RCAExecuteException,
    RCANotNeedExecuteException,
)
from src.handler.rca.rca_handler import RcaScene
from src.common.tool import StringUtils


class TransactionWaitTimeoutScene(RcaScene):
    def __init__(self):
        super().__init__()
        self.conflict_tx_id_value = None
        self.data_trans_id_value = None
        self.error_msg_type = None
        self.error_msg = None
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

        self.error_msg = self.input_parameters.get("error_msg")
        if not self.error_msg:
            raise RCANotNeedExecuteException('error_msg is empty. Please provide error_msg by --env error_msg="Shared lock conflict" or --env error_msg="Lock wait timeout exceeded"')

        if "Shared lock conflict" in self.error_msg:
            self.record.add_record("Error type: Shared lock conflict (-6004)")
            self.error_msg_type = "Shared lock conflict"
        elif "Lock wait timeout exceeded" in self.error_msg:
            self.record.add_record("Error type: Lock wait timeout exceeded (-6003)")
            self.error_msg_type = "Lock wait timeout exceeded"
        else:
            raise RCANotNeedExecuteException('error_msg should contain "Shared lock conflict" or "Lock wait timeout exceeded"')

        # Suggest using lock_conflict scene
        self.stdio.warn("[TransactionWaitTimeoutScene] NOTE: This scene is integrated into 'lock_conflict'. " "You can also use: obdiag rca run --scene=lock_conflict --env error_msg='{0}'".format(self.error_msg))

    def verbose(self, info):
        self.stdio.verbose("[TransactionWaitTimeoutScene] {0}".format(info))

    def execute(self):
        # Deprecation warning: This scene is deprecated, use lock_conflict instead
        self.stdio.warn("[DEPRECATED] The 'transaction_wait_timeout' scene is deprecated and will be removed in a future version.")
        self.stdio.warn("Please use 'lock_conflict' scene instead: obdiag rca run --scene=lock_conflict --env error_msg=\"...\"")
        self.record.add_record("[DEPRECATED] This scene is deprecated. Use 'lock_conflict' scene instead.")
        try:
            syslog_level_data = self.ob_connector.execute_sql_return_cursor_dictionary('SHOW PARAMETERS like "syslog_level"').fetchall()
            self.record.add_record("syslog_level data is {0}".format(syslog_level_data[0].get("value") or None))

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

            if self.error_msg_type == "Shared lock conflict":
                self._analyze_shared_lock_conflict()
            elif self.error_msg_type == "Lock wait timeout exceeded":
                self._analyze_lock_wait_timeout()

        except RCANotNeedExecuteException:
            raise
        except Exception as e:
            raise RCAExecuteException("TransactionWaitTimeoutScene execute error: {0}".format(e))
        finally:
            self.stdio.verbose("end TransactionWaitTimeoutScene execute")

    def _analyze_shared_lock_conflict(self):
        """Analyze Shared lock conflict by searching logs"""
        # Analyze logs locally from already gathered logs
        work_path_lock = os.path.join(self.work_path, "lock_for_read")
        if not os.path.exists(work_path_lock):
            os.makedirs(work_path_lock)

        lock_for_read_logs = []
        data_trans_id_line = None
        for log_file in self.all_log_files:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines:
                        if "lock_for_read need retry" in line:
                            lock_for_read_logs.append(line)
                        if "data_trans_id" in line and not self.data_trans_id_value:
                            data_trans_id_line = line
                            match = re.search(r"data_trans_id_:\{txid:(\d+)\}", line)
                            if match:
                                self.data_trans_id_value = match.group(1)
            except Exception as e:
                self.verbose("Error reading log file {0}: {1}".format(log_file, e))

        if not lock_for_read_logs:
            self.record.add_record("No 'lock_for_read need retry' logs found in gathered logs")
            self.record.add_suggest("No lock_for_read logs found. Please check if syslog_level includes WDIAG.")
            return

        # Save filtered logs to separate file
        lock_log_file = os.path.join(work_path_lock, "lock_for_read_filtered.log")
        with open(lock_log_file, "w", encoding="utf-8") as f:
            f.writelines(lock_for_read_logs)
        self.record.add_record("Found {0} 'lock_for_read need retry' log entries in {1}".format(len(lock_for_read_logs), work_path_lock))

        if self.data_trans_id_value:
            self.record.add_record("Found blocking transaction: tx_id={0}".format(self.data_trans_id_value))

            # Extract logs for the blocking transaction from already gathered logs
            work_path_tx = os.path.join(self.work_path, "data_trans_id_{0}".format(self.data_trans_id_value))
            if not os.path.exists(work_path_tx):
                os.makedirs(work_path_tx)

            tx_logs = []
            for log_file in self.all_log_files:
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        for line in lines:
                            if self.data_trans_id_value in line:
                                tx_logs.append(line)
                except Exception as e:
                    self.verbose("Error reading log file {0}: {1}".format(log_file, e))

            if tx_logs:
                tx_log_file = os.path.join(work_path_tx, "tx_{0}_filtered.log".format(self.data_trans_id_value))
                with open(tx_log_file, "w", encoding="utf-8") as f:
                    f.writelines(tx_logs)
                self.record.add_record("Found {0} log entries for tx_id={1}, saved to {2}".format(len(tx_logs), self.data_trans_id_value, work_path_tx))

            self.record.add_suggest(
                "Shared lock conflict caused by transaction (tx_id:{0}) in commit phase. "
                "The read request is waiting for this transaction to complete its commit. "
                "Use 'obdiag rca run --scene=transaction_not_ending --env tx_id={0}' for further analysis. "
                "Logs saved to: {1}".format(self.data_trans_id_value, work_path_tx)
            )
        else:
            self.record.add_record("Could not extract data_trans_id from logs")
            if data_trans_id_line:
                self.record.add_record("Log line: {0}".format(data_trans_id_line[:500]))
            self.record.add_suggest("Please check logs in {0} for data_trans_id information".format(work_path_lock))

    def _analyze_lock_wait_timeout(self):
        """Analyze Lock wait timeout exceeded by searching logs"""
        # Analyze logs locally from already gathered logs
        work_path_mvcc = os.path.join(self.work_path, "mvcc_write_conflict")
        if not os.path.exists(work_path_mvcc):
            os.makedirs(work_path_mvcc)

        mvcc_logs = []
        conflict_tx_id_line = None
        for log_file in self.all_log_files:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines:
                        if "mvcc_write conflict" in line:
                            mvcc_logs.append(line)
                        if "conflict_tx_id" in line and not self.conflict_tx_id_value:
                            conflict_tx_id_line = line
                            match = re.search(r"conflict_tx_id=\{txid:(\d+)\}", line)
                            if match:
                                self.conflict_tx_id_value = match.group(1)
            except Exception as e:
                self.verbose("Error reading log file {0}: {1}".format(log_file, e))

        if not mvcc_logs:
            self.record.add_record("No 'mvcc_write conflict' logs found in gathered logs")
            self.record.add_suggest("No mvcc_write conflict logs found. Please check if syslog_level includes INFO.")
            return

        # Save filtered logs to separate file
        mvcc_log_file = os.path.join(work_path_mvcc, "mvcc_write_conflict_filtered.log")
        with open(mvcc_log_file, "w", encoding="utf-8") as f:
            f.writelines(mvcc_logs)
        self.record.add_record("Found {0} 'mvcc_write conflict' log entries in {1}".format(len(mvcc_logs), work_path_mvcc))

        if self.conflict_tx_id_value:
            self.record.add_record("Found blocking transaction: conflict_tx_id={0}".format(self.conflict_tx_id_value))
            self.record.add_suggest(
                "Lock wait timeout caused by transaction (tx_id:{0}) holding row lock and not completing. "
                "To resolve: "
                "1) Wait for the transaction to complete; "
                "2) Kill the blocking session; "
                "3) Use 'obdiag rca run --scene=transaction_not_ending --env tx_id={0}' for further analysis.".format(self.conflict_tx_id_value)
            )
        else:
            self.record.add_record("Could not extract conflict_tx_id from logs")
            if conflict_tx_id_line:
                self.record.add_record("Log line: {0}".format(conflict_tx_id_line[:500]))
            self.record.add_suggest("Please check logs in {0} for conflict_tx_id information".format(work_path_mvcc))

    def get_scene_info(self):
        return {
            "name": "transaction_wait_timeout",
            "info_en": "[Deprecated] Root cause analysis for lock wait timeout. Supports 'Shared lock conflict' (-6004) and 'Lock wait timeout exceeded' (-6003). Please use 'lock_conflict' scene instead: obdiag rca run --scene=lock_conflict --env error_msg=\"...\"",
            "info_cn": "[已废弃] 锁等待超时的根因分析，支持'Shared lock conflict'(-6004)和'Lock wait timeout exceeded'(-6003)。请使用'lock_conflict'场景: obdiag rca run --scene=lock_conflict --env error_msg=\"...\"",
        }


transaction_wait_timeout = TransactionWaitTimeoutScene()
