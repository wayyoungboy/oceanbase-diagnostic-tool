#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: sql_builder.py
@desc: SQL query building mixin for plan monitor handler
"""

from src.handler.meta.sql_meta import GlobalSqlMeta


class SQLBuilderMixin:
    """Mixin providing SQL query generation methods."""

    def sql_audit_by_trace_id_limit1_sql(self):
        main_version = int(self.ob_version.split('.')[0])

        if main_version >= 4:
            params_value_replacement = "params_value"
        else:
            params_value_replacement = "null as params_value"

        if self.tenant_mode == 'mysql':
            sql = str(GlobalSqlMeta().get_value(key="sql_audit_by_trace_id_limit1_mysql"))
        else:
            sql = str(GlobalSqlMeta().get_value(key="sql_audit_by_trace_id_limit1_oracle"))

        sql = sql.replace("##REPLACE_TRACE_ID##", self.trace_id)
        sql = sql.replace("##REPLACE_SQL_AUDIT_TABLE_NAME##", self.sql_audit_name)
        sql = sql.replace("##OB_VERSION_PARAMS_VALUE##", params_value_replacement)

        return sql

    def plan_explain_sql(self, tenant_id, plan_id, svr_ip, svr_port):
        if self.tenant_mode == 'mysql':
            if self.ob_major_version >= 4:
                sql = "select * from oceanbase.gv$ob_plan_cache_plan_explain where tenant_id = %s and plan_id = %s  and svr_ip = '%s' and svr_port = %s" % (tenant_id, plan_id, svr_ip, svr_port)
            else:
                sql = "select * from oceanbase.gv$plan_cache_plan_explain where tenant_id = %s and plan_id = %s  and ip = '%s' and port = %s" % (tenant_id, plan_id, svr_ip, svr_port)
        else:
            if self.ob_major_version >= 4:
                sql = "select * from sys.gv$ob_plan_cache_plan_explain where tenant_id = %s and plan_id = %s  and svr_ip = '%s' and svr_port = %s" % (tenant_id, plan_id, svr_ip, svr_port)
            else:
                sql = "select * from sys.gv$plan_cache_plan_explain where tenant_id = %s and plan_id = %s  and svr_ip = '%s' and svr_port = %s" % (tenant_id, plan_id, svr_ip, svr_port)
        return sql

    def full_audit_sql_by_trace_id_sql(self, trace_id):
        if self.tenant_mode == 'mysql':
            sql = "select /*+ sql_audit */ * from oceanbase.%s where trace_id = '%s' AND client_ip IS NOT NULL ORDER BY QUERY_SQL ASC, REQUEST_ID limit 1000" % (self.sql_audit_name, trace_id)
        else:
            sql = "select /*+ sql_audit */ * from sys.%s where trace_id = '%s' AND  length(client_ip) > 4 ORDER BY  REQUEST_ID limit 1000" % (self.sql_audit_name, trace_id)
        return sql

    def sql_plan_monitor_dfo_op_sql(self, tenant_id, plan_id, trace_id, svr_ip, svr_port):
        if self.tenant_mode == 'mysql':
            key = "sql_plan_monitor_dfo_op_mysql_obversion4" if self.ob_major_version >= 4 else "sql_plan_monitor_dfo_op_mysql"
        else:
            key = "sql_plan_monitor_dfo_op_oracle_obversion4" if self.ob_major_version >= 4 else "sql_plan_monitor_dfo_op_oracle"

        sql = (
            str(GlobalSqlMeta().get_value(key=key))
            .replace("##REPLACE_TRACE_ID##", trace_id)
            .replace("##REPLACE_PLAN_ID##", str(plan_id))
            .replace("##REPLACE_TENANT_ID##", str(tenant_id))
            .replace("##REPLACE_PLAN_EXPLAIN_TABLE_NAME##", self.plan_explain_name)
            .replace("##REPLACE_SVR_IP##", svr_ip)
            .replace("##REPLACE_SVR_PORT##", str(svr_port))
        )
        return sql

    def sql_plan_monitor_svr_agg_template_sql(self):
        if self.tenant_mode == 'mysql':
            key = "sql_plan_monitor_svr_agg_template_mysql_obversion4" if self.ob_major_version >= 4 else "sql_plan_monitor_svr_agg_template_mysql"
        else:
            key = "sql_plan_monitor_svr_agg_template_oracle_obversion4" if self.ob_major_version >= 4 else "sql_plan_monitor_svr_agg_template_oracle"
        return GlobalSqlMeta().get_value(key=key)

    def sql_plan_monitor_detail_template_sql(self):
        if self.tenant_mode == 'mysql':
            key = "sql_plan_monitor_detail_template_mysql_obversion4" if self.ob_major_version >= 4 else "sql_plan_monitor_detail_template_mysql"
        else:
            key = "sql_plan_monitor_detail_template_oracle_obversion4" if self.ob_major_version >= 4 else "sql_plan_monitor_detail_template_oracle"
        return GlobalSqlMeta().get_value(key=key)

    def sql_ash_top_event_sql(self, tenant_id, trace_id):
        sql = str(GlobalSqlMeta().get_value(key="ash_top_event_mysql")).replace("##REPLACE_TENANT_ID##", str(tenant_id)).replace("##REPLACE_TRACE_ID##", trace_id)
        return sql

    def sql_plan_monitor_db_time_sql(self, tenant_id, trace_id):
        sql = str(GlobalSqlMeta().get_value(key="sql_plan_monitor_db_time_mysql_template_obversion4")).replace("##REPLACE_TENANT_ID##", str(tenant_id)).replace("##REPLACE_TRACE_ID##", trace_id)
        return sql

    def sql_plan_monitor_histogram_sql(self, db_name, table_name):
        """Get histogram query SQL for table-level statistics (Issue #626)."""
        db_escaped = db_name.replace("'", "''") if db_name else ""
        table_escaped = table_name.replace("'", "''") if table_name else ""
        if self.tenant_mode == 'mysql':
            sql = GlobalSqlMeta().get_value(key="sql_plan_monitor_histogram_mysql")
        else:
            sql = GlobalSqlMeta().get_value(key="sql_plan_monitor_histogram_oracle")
        return str(sql).replace("##REPLACE_DATABASE_NAME##", db_escaped).replace("##REPLACE_TABLE_NAME##", table_escaped)

    def sql_plan_monitor_part_histogram_sql(self, db_name, table_name):
        """Get partition-level histogram query SQL (Issue #626)."""
        db_escaped = db_name.replace("'", "''") if db_name else ""
        table_escaped = table_name.replace("'", "''") if table_name else ""
        if self.tenant_mode == 'mysql':
            sql = GlobalSqlMeta().get_value(key="sql_plan_monitor_part_histogram_mysql")
        else:
            sql = GlobalSqlMeta().get_value(key="sql_plan_monitor_part_histogram_oracle")
        return str(sql).replace("##REPLACE_DATABASE_NAME##", db_escaped).replace("##REPLACE_TABLE_NAME##", table_escaped)
