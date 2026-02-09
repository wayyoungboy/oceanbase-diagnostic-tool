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
@file: transaction_rollback.py
@desc: Root cause analysis for transaction rollback errors.
       Error codes: 6002 (internal: -6224, -6223, -6211, -6213)
       - -6224: transaction need rollback
       - -6223: Transaction exiting
       - -6211: Transaction is killed
       - -6213: Transaction context does not exist
       Reference: [4.0] 事务问题通用排查手册
"""
import datetime
import os
import re

from src.handler.rca.rca_exception import (
    RCAInitException,
    RCAExecuteException,
)
from src.handler.rca.rca_handler import RcaScene
from src.common.tool import StringUtils


class TransactionRollbackScene(RcaScene):
    def __init__(self):
        super().__init__()
        self.work_path = self.store_dir
        self.trans_is_killed_log = None
        self.rollback_reason = None
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

    def verbose(self, info):
        self.stdio.verbose("[TransactionRollbackScene] {0}".format(info))

    def execute(self):
        try:
            # get the syslog_level
            syslog_level_data = self.ob_connector.execute_sql_return_cursor_dictionary(' SHOW PARAMETERS like "syslog_level"').fetchall()
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

            # Step 1: gather log about "trans is killed"
            self.verbose("Step 1: Searching for 'trans is killed' logs")
            work_path_trans_is_killed = os.path.join(self.work_path, "trans_is_killed")
            if not os.path.exists(work_path_trans_is_killed):
                os.makedirs(work_path_trans_is_killed)

            trans_is_killed_logs = []
            trans_id = None
            for log_file in self.all_log_files:
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        for line in lines:
                            if "trans is killed" in line:
                                trans_is_killed_logs.append(line)
                                if not self.trans_is_killed_log:
                                    self.trans_is_killed_log = line
                                    # Try to extract trans_id
                                    match = re.search(r'trans_id[=:]\{?txid:(\d+)\}?', line)
                                    if match:
                                        trans_id = match.group(1)
                except Exception as e:
                    self.verbose("Error reading log file {0}: {1}".format(log_file, e))

            if trans_is_killed_logs:
                # Save filtered logs to separate file
                trans_is_killed_log_file = os.path.join(work_path_trans_is_killed, "trans_is_killed_filtered.log")
                with open(trans_is_killed_log_file, "w", encoding="utf-8") as f:
                    f.writelines(trans_is_killed_logs)
                self.record.add_record("Found {0} 'trans is killed' log entries in {1}".format(len(trans_is_killed_logs), work_path_trans_is_killed))
                if self.trans_is_killed_log:
                    self.record.add_record("Found trans is killed log: {0}".format(self.trans_is_killed_log[:500]))
                if trans_id:
                    self.record.add_record("Extracted trans_id: {0}".format(trans_id))
            else:
                self.record.add_record("No log found about 'trans is killed'")
                self.record.add_suggest("No 'trans is killed' log found. The transaction rollback may be caused by other reasons. " "Please check 'sending error packet' logs for more details.")
                return

            # Step 2: Check for leader switch (switch to follower forcedly)
            self.verbose("Step 2: Checking for leader switch")
            leader_switch_found = self._check_leader_switch()

            # Step 3: Check for transaction timeout
            self.verbose("Step 3: Checking for transaction timeout")
            timeout_found = self._check_transaction_timeout()

            # Step 4: Check election errors if leader switch was found
            if leader_switch_found:
                self.verbose("Step 4: Checking election logs for errors")
                self._check_election_errors()

            # Provide final suggestion based on findings
            if not leader_switch_found and not timeout_found:
                self.record.add_suggest("Could not determine the exact reason for transaction rollback. " "Please check the transaction logs and contact OceanBase community for further analysis.")

        except Exception as e:
            raise RCAExecuteException("TransactionRollbackScene execute error: {0}".format(e))
        finally:
            self.stdio.verbose("end TransactionRollbackScene execute")

    def _check_leader_switch(self):
        """Check for leader switch logs"""
        work_path_switch = os.path.join(self.work_path, "switch_to_follower")
        if not os.path.exists(work_path_switch):
            os.makedirs(work_path_switch)

        # Analyze logs locally from already gathered logs
        switch_logs = []
        for log_file in self.all_log_files:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines:
                        if "switch to follower forcedly success" in line:
                            switch_logs.append(line)
            except Exception as e:
                self.verbose("Error reading log file {0}: {1}".format(log_file, e))

        if switch_logs:
            # Save filtered logs to separate file
            switch_log_file = os.path.join(work_path_switch, "switch_to_follower_filtered.log")
            with open(switch_log_file, "w", encoding="utf-8") as f:
                f.writelines(switch_logs)
            self.record.add_record("Found {0} 'switch to follower forcedly success' log entries in {1}".format(len(switch_logs), work_path_switch))
            self.rollback_reason = "leader_switch"
            self.record.add_suggest(
                "Transaction was killed due to LEADER SWITCH (leader revoke). "
                "The transaction was active when the leader changed to follower. "
                "This is expected behavior during leader changes. "
                "Please check if there were planned or unexpected leader switches."
            )
            return True
        else:
            self.record.add_record("No 'switch to follower forcedly success' logs found in gathered logs")
            return False

    def _check_transaction_timeout(self):
        """Check for transaction timeout"""
        work_path_expired = os.path.join(self.work_path, "trans_expired_time")
        if not os.path.exists(work_path_expired):
            os.makedirs(work_path_expired)

        # Analyze logs locally from already gathered logs
        expired_logs = []
        for log_file in self.all_log_files:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines:
                        if "trans_expired_time" in line:
                            expired_logs.append(line)
            except Exception as e:
                self.verbose("Error reading log file {0}: {1}".format(log_file, e))

        if not expired_logs:
            self.record.add_record("No 'trans_expired_time' logs found in gathered logs")
            return False

        # Save filtered logs to separate file
        expired_log_file = os.path.join(work_path_expired, "trans_expired_time_filtered.log")
        with open(expired_log_file, "w", encoding="utf-8") as f:
            f.writelines(expired_logs)
        self.record.add_record("Found {0} 'trans_expired_time' log entries in {1}".format(len(expired_logs), work_path_expired))

        # Analyze timeout conditions
        for line in expired_logs:
            try:
                # Extract trans_expired_time value
                match = re.search(r'trans_expired_time[=:](\d+)', line)
                if match:
                    expired_time_us = int(match.group(1))
                    # Convert to datetime (microseconds to seconds)
                    expired_time_s = expired_time_us / 1e6
                    expired_datetime = datetime.datetime.utcfromtimestamp(expired_time_s)

                    # Extract log timestamp
                    log_time_match = re.search(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\]', line)
                    if log_time_match:
                        log_time_str = log_time_match.group(1)
                        log_datetime = datetime.datetime.strptime(log_time_str[:26], '%Y-%m-%d %H:%M:%S.%f')

                        if expired_datetime <= log_datetime:
                            self.record.add_record("trans_expired_time ({0}) <= log_time ({1})".format(expired_datetime, log_datetime))
                            self.rollback_reason = "timeout"
                            self.record.add_suggest("Transaction was killed due to TIMEOUT. " "The transaction expired before completion. " "Please check and adjust transaction timeout settings: " "ob_trx_timeout, ob_query_timeout, ob_trx_idle_timeout.")
                            return True
            except Exception as e:
                self.verbose("Error parsing log line: {0}".format(e))

        return False

    def _check_election_errors(self):
        """Check election logs for errors that may have caused leader switch"""
        work_path_election = os.path.join(self.work_path, "election_errors")
        if not os.path.exists(work_path_election):
            os.makedirs(work_path_election)

        # Analyze election logs locally from already gathered logs
        # Note: We need to check if election logs were included in the initial gather
        # If scope was "observer", election logs should be included
        election_logs = []
        error_found = False
        for log_file in self.all_log_files:
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    for line in lines:
                        if "election" in line.lower():
                            election_logs.append(line)
                            if "ERROR" in line or "error" in line.lower():
                                error_found = True
            except Exception as e:
                self.verbose("Error reading log file {0}: {1}".format(log_file, e))

        if election_logs:
            # Save filtered logs to separate file
            election_log_file = os.path.join(work_path_election, "election_filtered.log")
            with open(election_log_file, "w", encoding="utf-8") as f:
                f.writelines(election_logs)

            if error_found:
                self.record.add_record("Found ERROR in election logs ({0} entries)".format(len(election_logs)))
                self.record.add_suggest("Election errors detected. The leader switch may have been caused by " "abnormal conditions (network issues, disk problems, etc.). " "Please check election logs in {0} for details.".format(work_path_election))
            else:
                self.record.add_record("Found {0} election log entries, but no ERROR found".format(len(election_logs)))
                self.record.add_suggest("No election errors found. The leader switch may have been triggered by " "RS scheduling (auto leader rebalancing). " "Please check if auto_leader_switch is enabled.")
        else:
            self.record.add_record("No election logs found in gathered logs. " "Note: If election logs are needed, set scope='election' in gather_log configuration.")

    def get_scene_info(self):
        return {
            "name": "transaction_rollback",
            "info_en": "Root cause analysis for transaction rollback errors. Analyzes whether rollback was caused by leader switch or timeout. Error code: 6002 (internal: -6224, -6223, -6211, -6213)",
            "info_cn": "事务回滚报错的根因分析，分析回滚是由切主还是超时导致。对应错误码6002（内部错误码-6224/-6223/-6211/-6213）",
        }


transaction_rollback = TransactionRollbackScene()
