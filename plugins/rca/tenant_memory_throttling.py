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
@time: 2026/01/22
@file: tenant_memory_throttling.py
@desc: 租户内存不足导致限速的根因分析
       当日志中出现 errcode=-4019 和 push request to queue fail 时，
       判断为租户内存不够导致限速，限速导致事务超时被杀，最终导致inner sql超时失败。
"""
import os
import re

from src.handler.rca.rca_exception import RCAInitException, RCAExecuteException, RCANotNeedExecuteException
from src.handler.rca.rca_handler import RcaScene, RCA_ResultRecord
from src.common.tool import StringUtils


class TenantMemoryThrottlingScene(RcaScene):
    def __init__(self):
        super().__init__()
        self.logs_name = None
        self.work_path = None
        self.tenant_id = None
        self.trace_id = None

    def init(self, context):
        super().init(context)
        # observer version >= 4.0.0.0
        observer_version = self.observer_version
        if observer_version is None or len(observer_version.strip()) == 0:
            raise RCAInitException("observer version is None. Please check the NODES conf.")
        if not (observer_version == "4.0.0.0" or StringUtils.compare_versions_greater(observer_version, "4.0.0.0")):
            self.stdio.error("observer version is {0}, which is less than 4.0.0.0.".format(observer_version))
            raise RCAInitException("observer version is {0}, which is less than 4.0.0.0.".format(observer_version))

        self.work_path = context.get_variable('store_dir')
        if not os.path.exists(self.work_path):
            os.makedirs(self.work_path)

        # 获取可选的参数
        self.tenant_id = self.input_parameters.get('tenant_id')
        self.trace_id = self.input_parameters.get('trace_id')

        self.record.add_record("Start checking tenant memory throttling scene")
        if self.tenant_id:
            self.record.add_record("Specified tenant_id: {0}".format(self.tenant_id))
        if self.trace_id:
            self.record.add_record("Specified trace_id: {0}".format(self.trace_id))

    def verbose(self, info):
        self.stdio.verbose("[TenantMemoryThrottlingScene] {0}".format(info))

    def execute(self):
        try:
            # 收集日志
            self.gather_log.set_parameters("scope", "observer")
            log_path = os.path.join(self.work_path, "all_log")
            if not os.path.exists(log_path):
                os.makedirs(log_path)

            # 如果有trace_id，则按trace_id收集日志
            if self.trace_id:
                self.gather_log.grep(self.trace_id)

            self.logs_name = self.gather_log.execute(save_path=log_path)
            if self.logs_name is None or len(self.logs_name) <= 0:
                self.record.add_record("No log files found")
                raise RCANotNeedExecuteException("No log files found")
            else:
                self.record.add_record("Logs collected to {0}".format(log_path))

            # Check if key error patterns exist in logs
            if not self._check_error_patterns_in_log():
                self.record.add_record("Not found errcode=-4019 and push request to queue fail patterns in logs")
                raise RCANotNeedExecuteException("Not found related error patterns")

            self.record.add_record("Found errcode=-4019 and push request to queue fail patterns in logs")

            # If database connection exists, perform deeper analysis
            if self.ob_connector:
                self.record.add_record("Database connection exists, using SQL for deeper analysis")
                self._analyze_with_sql()
            else:
                self.record.add_record("No database connection, analyzing based on logs only")
                self._analyze_without_sql()

            # Provide suggestions
            self._provide_suggestions()

        except Exception as e:
            raise RCAExecuteException("TenantMemoryThrottlingScene execute error: {0}".format(e))
        finally:
            self.stdio.verbose("End TenantMemoryThrottlingScene execute")

    def _check_error_patterns_in_log(self):
        """Check if errcode=-4019 and push request to queue fail patterns exist in logs."""
        error_found = False
        error_4019_found = False
        queue_fail_found = False

        for log_name in self.logs_name:
            try:
                with open(log_name, "r", encoding="utf-8", errors="ignore") as f:
                    file_data = f.read()

                    # Check errcode=-4019
                    if "errcode=-4019" in file_data:
                        error_4019_found = True
                        self.record.add_record("Found errcode=-4019 in log {0}".format(os.path.basename(log_name)))

                    # Check push request to queue fail
                    if "push request to queue fail" in file_data.lower():
                        queue_fail_found = True
                        self.record.add_record("Found push request to queue fail in log {0}".format(os.path.basename(log_name)))

                    # Try to extract more context information
                    self._extract_context_from_log(file_data, log_name)

            except Exception as e:
                self.verbose("Error reading log file {0}: {1}".format(log_name, e))

        if error_4019_found and queue_fail_found:
            error_found = True
            self.record.add_record("Found both errcode=-4019 and push request to queue fail, matches tenant memory throttling scene")

        return error_found

    def _extract_context_from_log(self, file_data, log_name):
        """Extract more context information from logs."""
        lines = file_data.split('\n')

        for i, line in enumerate(lines):
            # Find lines containing errcode=-4019
            if "errcode=-4019" in line:
                self.record.add_record("Error line content: {0}".format(line.strip()))

                # Extract tenant ID if exists
                tenant_match = re.search(r'tenant[_\s]*id[=:]\s*(\d+)', line, re.IGNORECASE)
                if tenant_match:
                    found_tenant_id = tenant_match.group(1)
                    self.record.add_record("Extracted tenant_id from log: {0}".format(found_tenant_id))
                    if not self.tenant_id:
                        self.tenant_id = found_tenant_id

                # Extract other related information
                self._extract_related_info(lines, i, log_name)

            # Find lines containing push request to queue fail
            if "push request to queue fail" in line.lower():
                self.record.add_record("Queue fail line content: {0}".format(line.strip()))

                # Try to extract queue size and other information
                size_match = re.search(r'size[=:]\s*(\d+)', line)
                if size_match:
                    self.record.add_record("Queue size: {0}".format(size_match.group(1)))

                limit_match = re.search(r'limit[=:]\s*(\d+)', line)
                if limit_match:
                    self.record.add_record("Queue limit: {0}".format(limit_match.group(1)))

    def _extract_related_info(self, lines, error_line_index, log_name):
        """Extract related information near the error line."""
        # View a few lines before and after the error line
        start = max(0, error_line_index - 3)
        end = min(len(lines), error_line_index + 4)

        context_lines = lines[start:end]
        self.record.add_record("Error context (near line {0}):".format(error_line_index + 1))
        for j, context_line in enumerate(context_lines):
            relative_index = start + j
            self.record.add_record("  L{0}: {1}".format(relative_index + 1, context_line.strip()))

    def _analyze_with_sql(self):
        """Perform deeper analysis using SQL."""
        if not self.tenant_id:
            self.record.add_record("Tenant ID not specified, cannot perform deeper SQL analysis")
            return

        try:
            # 1. Check tenant memory usage
            self.record.add_record("Checking memory usage for tenant {0}".format(self.tenant_id))

            # 查询租户内存配置
            memory_sql = """
            SELECT 
                tenant_id,
                svr_ip,
                svr_port,
                zone,
                name as config_name,
                value as config_value,
                info
            FROM oceanbase.__all_virtual_tenant_parameter_info 
            WHERE tenant_id = {0} 
            AND name IN ('memstore_limit_percentage', 'writing_throttling_trigger_percentage', 
                        'writing_throttling_maximum_duration', 'freeze_trigger_percentage',
                        'memory_limit', 'system_memory')
            """.format(
                self.tenant_id
            )

            memory_config = self._execute_sql_with_save(memory_sql, "tenant_memory_config_{0}".format(self.tenant_id))

            if memory_config and len(memory_config) > 0:
                self.record.add_record("Tenant memory configuration:")
                for row in memory_config:
                    self.record.add_record("  {0}: {1} ({2})".format(row["config_name"], row["config_value"], row["info"]))

            # 2. Check current memory usage
            memory_usage_sql = """
            SELECT 
                tenant_id,
                svr_ip,
                svr_port,
                hold as total_memory_hold,
                used as memory_used,
                free_count as free_memory_count,
                round(used * 100.0 / hold, 2) as usage_percentage
            FROM oceanbase.__all_virtual_memory_info 
            WHERE tenant_id = {0}
            ORDER BY usage_percentage DESC
            LIMIT 10
            """.format(
                self.tenant_id
            )

            memory_usage = self._execute_sql_with_save(memory_usage_sql, "tenant_memory_usage_{0}".format(self.tenant_id))

            if memory_usage and len(memory_usage) > 0:
                self.record.add_record("Tenant memory usage (top 10 highest usage):")
                high_usage_found = False
                for row in memory_usage:
                    usage_percentage = float(row["usage_percentage"])
                    self.record.add_record("  {0}:{1} - Usage: {2}% (Used: {3}, Total: {4})".format(row["svr_ip"], row["svr_port"], usage_percentage, row["memory_used"], row["total_memory_hold"]))
                    if usage_percentage > 90:
                        high_usage_found = True
                        self.record.add_record("  Warning: Memory usage exceeds 90%, may cause throttling")

                if high_usage_found:
                    self.record.add_suggest("Found nodes with memory usage exceeding 90%, recommend expanding memory or optimizing memory usage")

            # 3. Check memstore usage
            memstore_sql = """
            SELECT 
                tenant_id,
                svr_ip,
                svr_port,
                active_memstore_used as active_memstore_used,
                total_memstore_used as total_memstore_used,
                major_freeze_trigger as major_freeze_trigger,
                memstore_limit as memstore_limit,
                freeze_cnt as freeze_count
            FROM oceanbase.__all_virtual_memstore_info 
            WHERE tenant_id = {0}
            AND is_active = 'YES'
            """.format(
                self.tenant_id
            )

            memstore_info = self._execute_sql_with_save(memstore_sql, "tenant_memstore_info_{0}".format(self.tenant_id))

            if memstore_info and len(memstore_info) > 0:
                self.record.add_record("Tenant Memstore usage:")
                memstore_throttle_found = False
                for row in memstore_info:
                    memstore_usage = 0
                    if row["memstore_limit"] and float(row["memstore_limit"]) > 0:
                        memstore_usage = float(row["total_memstore_used"]) * 100.0 / float(row["memstore_limit"])

                    self.record.add_record("  {0}:{1} - Memstore usage: {2:.2f}% (Used: {3}, Limit: {4})".format(row["svr_ip"], row["svr_port"], memstore_usage, row["total_memstore_used"], row["memstore_limit"]))

                    if memstore_usage > 80:
                        memstore_throttle_found = True
                        self.record.add_record("  Warning: Memstore usage exceeds 80%, may trigger write throttling")

                if memstore_throttle_found:
                    self.record.add_suggest("Memstore usage too high, recommend increasing memstore_limit or triggering major freeze")

            # 4. Check throttling related statistics
            throttle_sql = """
            SELECT 
                tenant_id,
                svr_ip,
                svr_port,
                name as throttle_name,
                value as throttle_value
            FROM oceanbase.__all_virtual_sysstat 
            WHERE tenant_id = {0}
            AND (name LIKE '%throttle%' OR name LIKE '%write%limit%' OR name LIKE '%memory%limit%'
                 OR name LIKE '%queue%full%' OR name LIKE '%reject%')
            AND value > 0
            ORDER BY value DESC
            """.format(
                self.tenant_id
            )

            throttle_stats = self._execute_sql_with_save(throttle_sql, "tenant_throttle_stats_{0}".format(self.tenant_id))

            if throttle_stats and len(throttle_stats) > 0:
                self.record.add_record("Tenant throttling related statistics:")
                for row in throttle_stats:
                    self.record.add_record("  {0}: {1}".format(row["throttle_name"], row["throttle_value"]))
                    if "throttle" in row["throttle_name"].lower() and int(row["throttle_value"]) > 100:
                        self.record.add_record("  Warning: Throttling triggered frequently, indicating high system pressure")

            # 5. Check transaction timeout related statistics
            transaction_sql = """
            SELECT 
                tenant_id,
                svr_ip,
                svr_port,
                name as stat_name,
                value as stat_value
            FROM oceanbase.__all_virtual_sysstat 
            WHERE tenant_id = {0}
            AND (name LIKE '%timeout%' OR name LIKE '%abort%' OR name LIKE '%kill%'
                 OR name LIKE '%transaction%fail%' OR name LIKE '%sql%fail%')
            AND value > 0
            ORDER BY value DESC
            LIMIT 20
            """.format(
                self.tenant_id
            )

            transaction_stats = self._execute_sql_with_save(transaction_sql, "tenant_transaction_stats_{0}".format(self.tenant_id))

            if transaction_stats and len(transaction_stats) > 0:
                self.record.add_record("Transaction timeout related statistics:")
                for row in transaction_stats:
                    self.record.add_record("  {0}: {1}".format(row["stat_name"], row["stat_value"]))

            # 6. Check recent memory allocation failures
            if self.trace_id:
                self._analyze_trace_specific_info()

        except Exception as e:
            self.record.add_record("Error during SQL analysis: {0}".format(e))
            self.verbose("SQL analysis error: {0}".format(e))

    def _analyze_without_sql(self):
        """Analysis without database connection."""
        self.record.add_record("No database connection, analyzing based on log patterns")

        # Analyze error patterns
        self.record.add_record("Analysis results:")
        self.record.add_record("1. errcode=-4019 indicates memory allocation failure")
        self.record.add_record("2. push request to queue fail indicates request queue is full")
        self.record.add_record("3. Both errors appearing together indicate tenant memory shortage causing throttling")

        # Try to extract more information from logs
        total_logs = len(self.logs_name)
        error_count = 0

        for log_name in self.logs_name:
            try:
                with open(log_name, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    # Count error occurrences
                    error_count += content.count("errcode=-4019")
            except Exception:
                pass

        if error_count > 0:
            self.record.add_record("Found {1} occurrences of errcode=-4019 error in {0} log files".format(total_logs, error_count))

    def _provide_suggestions(self):
        """Provide diagnostic suggestions."""
        self.record.add_suggest("Tenant memory throttling diagnosis completed")
        self.record.add_suggest("")
        self.record.add_suggest("[Problem Analysis]")
        self.record.add_suggest("1. errcode=-4019 indicates memory allocation failure, usually tenant memory shortage")
        self.record.add_suggest("2. push request to queue fail indicates request queue is full, system starts throttling")
        self.record.add_suggest("3. Throttling causes transaction processing to slow down, may trigger transaction timeout kill")
        self.record.add_suggest("4. Transaction timeout eventually causes inner SQL execution failure")
        self.record.add_suggest("")
        self.record.add_suggest("[Solutions]")
        self.record.add_suggest("1. Emergency measures:")
        self.record.add_suggest("   - Restart related tenant services to release memory")
        self.record.add_suggest("   - Expand memory for problematic tenants")
        self.record.add_suggest("   - Check and terminate SQL with high memory usage")
        self.record.add_suggest("")
        self.record.add_suggest("2. Long-term optimization:")
        self.record.add_suggest("   - Adjust tenant memory configuration, increase memory_limit")
        self.record.add_suggest("   - Optimize SQL to reduce memory usage")
        self.record.add_suggest("   - Set reasonable memstore_limit_percentage")
        self.record.add_suggest("   - Monitor memory usage and set alerts")
        self.record.add_suggest("")
        self.record.add_suggest("3. Detailed analysis:")
        self.record.add_suggest("   - Use obdiag gather scene run --scene=observer.perf_sql to analyze SQL performance")
        self.record.add_suggest("   - Check for memory leaks or memory fragmentation issues")
        self.record.add_suggest("   - Analyze memory usage patterns during business peaks")
        self.record.add_suggest("")
        self.record.add_suggest("[Related Commands]")
        self.record.add_suggest("1. View tenant memory configuration:")
        self.record.add_suggest("   SELECT * FROM oceanbase.__all_virtual_tenant_parameter_info WHERE tenant_id=<tenant_id> AND name LIKE '%memory%';")
        self.record.add_suggest("")
        self.record.add_suggest("2. View memory usage:")
        self.record.add_suggest("   SELECT * FROM oceanbase.__all_virtual_memory_info WHERE tenant_id=<tenant_id> ORDER BY used DESC LIMIT 10;")
        self.record.add_suggest("")
        self.record.add_suggest("3. View Memstore usage:")
        self.record.add_suggest("   SELECT * FROM oceanbase.__all_virtual_memstore_info WHERE tenant_id=<tenant_id>;")

    def _execute_sql_with_save(self, sql: str, save_file_name: str):
        """Execute SQL and save results."""
        try:
            cursor = self.ob_connector.execute_sql_return_cursor_dictionary(sql)
            data = cursor.fetchall()
            self.verbose("SQL执行结果: {0}".format(len(data)))

            if len(data) <= 0:
                self.record.add_record("SQL执行结果为空: {0}".format(sql[:100]))
                return []

            columns = [desc[0] for desc in cursor.description]
            data_save_path = os.path.join(self.work_path, "{}.txt".format(save_file_name))

            with open(data_save_path, 'w', encoding='utf-8') as f:
                f.write('\t'.join(columns) + '\n')
                for row in data:
                    line = ""
                    for item in row:
                        line += "{}\t".format(row[item])
                    f.write(line + '\n')

            return data
        except Exception as e:
            raise RCAExecuteException("执行SQL时出错: {0}".format(e))

    def get_scene_info(self):
        return {
            "name": "tenant_memory_throttling",
            "info_en": "[beta] Tenant memory throttling analysis. When logs contain errcode=-4019 and push request to queue fail, it indicates tenant memory shortage causing throttling, which leads to transaction timeout and inner SQL failure.",
            "info_cn": "[beta] 租户内存限速分析。当日志中出现 errcode=-4019 和 push request to queue fail 时，判断为租户内存不够导致限速，限速导致事务超时被杀，最终导致inner sql超时失败。",
            "example": "obdiag rca run --scene=tenant_memory_throttling --env tenant_id=1001 --env trace_id=Y42A2F94C5F5-0005E7D4D3C7D4D3",
        }


tenant_memory_throttling = TenantMemoryThrottlingScene()
