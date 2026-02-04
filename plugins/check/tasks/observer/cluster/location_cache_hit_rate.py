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
@time: 2025/01/01
@file: location_cache_hit_rate.py
@desc: Check OceanBase location cache hit rate and analyze potential issues
       when hit rate is low. Analyzes plan_type distribution to identify
       routing efficiency issues. issue #100
"""

from src.handler.check.check_task import TaskBase
from src.common.tool import StringUtils


class LocationCacheHitRate(TaskBase):

    def init(self, context, report):
        super().init(context, report)

    def execute(self):
        try:
            if self.ob_connector is None:
                return self.report.add_critical("can't build obcluster connection")

            # Determine OceanBase version for SQL compatibility
            if self.observer_version is None or len(self.observer_version.strip()) == 0:
                self.stdio.warn("observer version is empty, skip location cache check")
                return

            is_ob4 = self.observer_version == "4.0.0.0" or StringUtils.compare_versions_greater(self.observer_version, "4.0.0.0")

            # Use different view names based on version
            if is_ob4:
                sql_audit_view = "oceanbase.GV$OB_SQL_AUDIT"
            else:
                sql_audit_view = "oceanbase.GV$SQL_AUDIT"

            self.stdio.verbose("checking location cache hit rate using view: {0}".format(sql_audit_view))

            # Analyze plan_type distribution to assess location cache efficiency
            # plan_type: 1=LOCAL, 2=REMOTE, 3=DISTRIBUTED
            # High REMOTE/DISTRIBUTED ratio may indicate low location cache hit rate
            sql_plan_type_distribution = """
            SELECT 
                plan_type,
                COUNT(*) as exec_count,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
            FROM {0}
            WHERE IS_EXECUTOR_RPC = 0
            AND request_time > (UNIX_TIMESTAMP(NOW()) - 3600) * 1000000
            GROUP BY plan_type
            ORDER BY exec_count DESC
            """.format(
                sql_audit_view
            )

            self.stdio.verbose("executing plan type distribution query")
            plan_type_data = self.ob_connector.execute_sql_return_cursor_dictionary(sql_plan_type_distribution).fetchall()

            if plan_type_data is None or len(plan_type_data) == 0:
                self.stdio.verbose("no plan type data found in recent 1 hour")
                return

            total_count = 0
            local_count = 0
            remote_count = 0
            distributed_count = 0

            for row in plan_type_data:
                plan_type = row.get("plan_type") or row.get("PLAN_TYPE")
                exec_count = row.get("exec_count") or row.get("EXEC_COUNT") or 0
                total_count += int(exec_count)

                if plan_type == 1:
                    local_count = int(exec_count)
                elif plan_type == 2:
                    remote_count = int(exec_count)
                elif plan_type == 3:
                    distributed_count = int(exec_count)

            if total_count == 0:
                self.stdio.verbose("total execution count is 0, skip analysis")
                return

            # Calculate percentages
            local_pct = round(local_count * 100.0 / total_count, 2)
            remote_pct = round(remote_count * 100.0 / total_count, 2)
            distributed_pct = round(distributed_count * 100.0 / total_count, 2)

            self.stdio.verbose("plan type distribution - LOCAL: {0}%, REMOTE: {1}%, DISTRIBUTED: {2}%".format(local_pct, remote_pct, distributed_pct))

            # Check for potential location cache issues
            # If REMOTE ratio > 30%, it may indicate location cache hit rate issues
            if remote_pct > 30:
                self.report.add_warning(
                    "High REMOTE plan ratio detected: {0}% (threshold: 30%). "
                    "This may indicate low location cache hit rate. "
                    "Suggestions: 1) Check if there are frequent partition migrations; "
                    "2) Check if location_cache_refresh_min_interval is properly configured; "
                    "3) Consider using table group to optimize data locality.".format(remote_pct)
                )

            # If DISTRIBUTED ratio > 50%, check for potential optimization
            if distributed_pct > 50:
                self.report.add_warning(
                    "High DISTRIBUTED plan ratio detected: {0}% (threshold: 50%). "
                    "This may cause high cross-node communication overhead. "
                    "Suggestions: 1) Review SQL to reduce cross-partition queries; "
                    "2) Consider optimizing partition strategy; "
                    "3) Check if primary zone configuration is appropriate.".format(distributed_pct)
                )

            # Analyze per-server plan type distribution for load balancing check
            self.__check_server_plan_distribution(sql_audit_view, is_ob4)

            # Check location cache refresh related parameters (OB 4.x only)
            if is_ob4:
                self.__check_location_cache_parameters()

        except Exception as e:
            self.stdio.error("execute error {0}".format(e))
            return self.report.add_fail("execute error {0}".format(e))

    def __check_server_plan_distribution(self, sql_audit_view, is_ob4):
        """Check plan type distribution per server to identify imbalanced routing"""
        try:
            sql_server_distribution = """
            SELECT 
                svr_ip,
                plan_type,
                COUNT(*) as exec_count
            FROM {0}
            WHERE IS_EXECUTOR_RPC = 0
            AND request_time > (UNIX_TIMESTAMP(NOW()) - 3600) * 1000000
            GROUP BY svr_ip, plan_type
            ORDER BY svr_ip, plan_type
            """.format(
                sql_audit_view
            )

            self.stdio.verbose("checking server plan distribution")
            server_data = self.ob_connector.execute_sql_return_cursor_dictionary(sql_server_distribution).fetchall()

            if server_data is None or len(server_data) == 0:
                return

            # Aggregate data by server
            server_stats = {}
            for row in server_data:
                svr_ip = row.get("svr_ip") or row.get("SVR_IP")
                plan_type = row.get("plan_type") or row.get("PLAN_TYPE")
                exec_count = int(row.get("exec_count") or row.get("EXEC_COUNT") or 0)

                if svr_ip not in server_stats:
                    server_stats[svr_ip] = {"local": 0, "remote": 0, "distributed": 0, "total": 0}

                server_stats[svr_ip]["total"] += exec_count
                if plan_type == 1:
                    server_stats[svr_ip]["local"] = exec_count
                elif plan_type == 2:
                    server_stats[svr_ip]["remote"] = exec_count
                elif plan_type == 3:
                    server_stats[svr_ip]["distributed"] = exec_count

            # Check for servers with high remote ratio
            for svr_ip, stats in server_stats.items():
                if stats["total"] == 0:
                    continue
                remote_ratio = stats["remote"] * 100.0 / stats["total"]
                if remote_ratio > 50:
                    self.report.add_warning(
                        "Server {0} has high REMOTE plan ratio: {1}%. " "This server may be receiving requests that should be routed elsewhere. " "Check OBProxy routing configuration and location cache status.".format(svr_ip, round(remote_ratio, 2))
                    )

        except Exception as e:
            self.stdio.warn("check server plan distribution failed: {0}".format(e))

    def __check_location_cache_parameters(self):
        """Check location cache related parameters (OB 4.x only)"""
        try:
            # Check location_cache_refresh_min_interval parameter
            sql_check_param = """
            SELECT NAME, VALUE, SVR_IP 
            FROM oceanbase.GV$OB_PARAMETERS 
            WHERE NAME IN ('location_cache_refresh_min_interval', 'location_fetch_concurrency')
            """

            self.stdio.verbose("checking location cache parameters")
            param_data = self.ob_connector.execute_sql_return_cursor_dictionary(sql_check_param).fetchall()

            if param_data is None or len(param_data) == 0:
                return

            for row in param_data:
                name = row.get("NAME") or row.get("name")
                value = row.get("VALUE") or row.get("value")
                svr_ip = row.get("SVR_IP") or row.get("svr_ip")

                if name == "location_cache_refresh_min_interval":
                    # Default is 1s, if too low may cause frequent refresh
                    try:
                        # Value format may be like "1s" or "1000ms"
                        if value and ("ms" in str(value).lower() or int(str(value).replace("s", "").replace("ms", "")) < 1000):
                            self.stdio.verbose("location_cache_refresh_min_interval on {0}: {1}".format(svr_ip, value))
                    except Exception:
                        pass

        except Exception as e:
            self.stdio.warn("check location cache parameters failed: {0}".format(e))

    def get_task_info(self):
        return {"name": "location_cache_hit_rate", "info": "Check OceanBase location cache hit rate by analyzing plan_type distribution. " "High REMOTE/DISTRIBUTED plan ratio may indicate low location cache hit rate. issue #100"}


location_cache_hit_rate = LocationCacheHitRate()
