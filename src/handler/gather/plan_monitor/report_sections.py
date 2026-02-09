#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: report_sections.py
@desc: Report section rendering mixin for plan monitor handler
"""

import os
import re

from src.common.ob_connector import TableResult
from src.common.tool import StringUtils, FileUtil, SQLTableExtractor
from src.handler.gather.gather_tabledump import GatherTableDumpHandler
from src.handler.meta.html_meta import GlobalHtmlMeta


class ReportSectionsMixin:
    """Mixin providing report section rendering methods."""

    def report_pre(self, s):
        pre = f'''<pre style='margin:20px;border:1px solid gray;'>{s}</pre>'''
        self._report(pre)

    def report_header(self):
        if self.ob_major_version >= 4:
            header = GlobalHtmlMeta().get_value(key="sql_plan_monitor_report_header_obversion4")
        else:
            header = GlobalHtmlMeta().get_value(key="sql_plan_monitor_report_header")
        with open(self.report_file_path, 'w') as f:
            f.write(header)
        self._log_verbose("report header complete")

    def report_footer(self):
        footer = GlobalHtmlMeta().get_value(key="sql_plan_monitor_report_footer")
        self._report(footer)

    def report_fast_preview(self):
        if self.ob_major_version >= 4:
            content = '''
            <script>
            generate_db_time_graph("dfo", db_time_serial, $('#db_time_serial'));
            generate_graph("dfo", agg_serial, $('#agg_serial'));
            generate_graph("dfo", agg_sched_serial, $('#agg_sched_serial'));
            generate_graph("sqc", svr_agg_serial_v1, $('#svr_agg_serial_v1'));
            generate_graph("sqc", svr_agg_serial_v2, $('#svr_agg_serial_v2'));
            </script>
            '''
        else:
            content = '''
            <script>
            generate_graph("dfo", agg_serial, $('#agg_serial'));
            generate_graph("dfo", agg_sched_serial, $('#agg_sched_serial'));
            generate_graph("sqc", svr_agg_serial_v1, $('#svr_agg_serial_v1'));
            generate_graph("sqc", svr_agg_serial_v2, $('#svr_agg_serial_v2'));
            </script>
            '''
        self._report(content)
        self._log_verbose("report SQL_PLAN_MONITOR fast preview complete")

    def report_optimization_info_warn(self, text):
        if text:
            content = '<div class="statsWarning">' + text + '</div>'
            self._report(content)
        else:
            self._log_verbose("the result of optimization_info_warn is None")

    # ====================================================================
    # SQL Audit sections
    # ====================================================================

    def report_sql_audit(self):
        sql = self.sql_audit_by_trace_id_limit1_sql()
        self._log_verbose(f"select sql_audit from ob with SQL: {sql}")
        try:
            sql_audit_result = self.sys_connector.execute_sql_pretty(sql)
            if not sql_audit_result:
                self._log_error(f"failed to find the related sql_audit for the given trace_id:{self.trace_id}")
                return False
            self._log_verbose(f"sql_audit_result: {sql_audit_result}")
            self._log_verbose("report sql_audit_result to file start ...")
            self._report(sql_audit_result.get_html_string())
            self._log_verbose("report sql_audit_result end")
            return True
        except Exception as e:
            self._log_error(f"sql_audit> {sql}")
            self._log_error(repr(e))

    def report_sql_audit_details(self, sql):
        if self.enable_dump_db:
            full_audit_sql_result = self.sys_connector.execute_sql_pretty(sql)
            table_html = full_audit_sql_result.get_html_string()

            vertical_html = ""
            vertical_html += '''
            <script>
            function toggleRecord(recordId) {
                const content = document.getElementById('record-content-' + recordId);
                const toggleButton = document.getElementById('toggle-btn-' + recordId);
                const copyButton = document.getElementById('copy-btn-' + recordId);
                if (content.style.display === 'none') {
                    content.style.display = 'block';
                    toggleButton.innerHTML = '\\u25bc \\u6536\\u8d77';
                    copyButton.style.display = 'inline-block';
                } else {
                    content.style.display = 'none';
                    toggleButton.innerHTML = '\\u25ba \\u5c55\\u5f00';
                    copyButton.style.display = 'none';
                }
            }
            function copyRecord(recordId) {
                const content = document.getElementById('record-content-' + recordId).innerText;
                navigator.clipboard.writeText(content).then(() => {
                    const button = document.getElementById('copy-btn-' + recordId);
                    const originalText = button.innerHTML;
                    button.innerHTML = '\\u2713 \\u5df2\\u590d\\u5236';
                    setTimeout(() => button.innerHTML = originalText, 2000);
                });
            }
            </script>
            '''

            vertical_html += '<div class="vertical-display mt-4">'
            vertical_html += '<h4 class="mb-3">SQL Audit Information (Vertical View - Record with Maximum ELAPSED_TIME)</h4>'

            field_names = full_audit_sql_result.field_names
            records = full_audit_sql_result.rows

            filtered_records = []
            elapsed_time_index = query_sql_index = tenant_name_index = None

            for idx, field in enumerate(field_names):
                upper_field = field.upper()
                if upper_field == 'ELAPSED_TIME':
                    elapsed_time_index = idx
                elif upper_field == 'QUERY_SQL':
                    query_sql_index = idx
                elif upper_field == 'TENANT_NAME':
                    tenant_name_index = idx

            if elapsed_time_index is not None and query_sql_index is not None and tenant_name_index is not None:
                for row in records:
                    query_sql = row[query_sql_index] if query_sql_index < len(row) else ''
                    tenant_name = row[tenant_name_index] if tenant_name_index < len(row) else ''
                    if query_sql and tenant_name:
                        filtered_records.append(row)

                max_elapsed_record = None
                max_elapsed_value = -1
                for row in filtered_records:
                    try:
                        elapsed_value = int(str(row[elapsed_time_index]).strip())
                        if elapsed_value > max_elapsed_value:
                            max_elapsed_value = elapsed_value
                            max_elapsed_record = row
                    except (ValueError, TypeError):
                        continue

            sql_audit_records = []
            if max_elapsed_record:
                record_html = '<div class="card mb-3">'
                record_html += '<div class="card-header d-flex justify-content-between align-items-center">'
                record_html += '<span><strong>sql_audit (\\G)</strong></span>'
                record_html += '<div>'
                record_html += '<button id="toggle-btn-0" class="btn btn-sm btn-outline-secondary me-2" onclick="toggleRecord(0)"><span>\\u25ba \\u5c55\\u5f00</span></button>'
                record_html += '<button id="copy-btn-0" class="btn btn-sm btn-outline-primary" onclick="copyRecord(0)" style="display: none;"><span>\\u590d\\u5236</span></button>'
                record_html += '</div></div>'
                record_html += '<div id="record-content-0" class="card-body" style="display: none;">'
                record_html += '<table class="table table-sm table-borderless">'
                for field, value in zip(field_names, max_elapsed_record):
                    record_html += f'<tr><th style="width: 30%; text-align: right">{field}:</th><td>{value}</td></tr>'
                record_html += '</table></div></div>'
                sql_audit_records.append(record_html)

            vertical_html += ''.join(sql_audit_records)
            vertical_html += '</div>'

            combined_html = f'<div class="sql-audit-container"><div class="table-display">{table_html}</div><div class="vertical-display">{vertical_html}</div></div>'
            self._report(f"<div><h2 id='sql_audit_table_anchor'>SQL_AUDIT \\u4fe1\\u606f</h2><div class='v' id='sql_audit_table' style='display: none'>{combined_html}</div></div>")
        self._log_verbose("report full sql audit complete")

    # ====================================================================
    # Plan explain / cache
    # ====================================================================

    def report_plan_explain(self, db_name, raw_sql):
        explain_sql = "explain extended %s" % raw_sql
        try:
            sql_explain_cursor = self.db_connector.execute_sql_return_cursor(explain_sql)
            self._log_verbose(f"execute SQL: {explain_sql}")
            sql_explain_result_sql = f"{explain_sql}"
            field_names = [col[0] for col in sql_explain_cursor.description] if sql_explain_cursor.description else []
            rows = sql_explain_cursor.fetchall()
            sql_explain_result = TableResult(field_names, rows)

            if self.ob_major_version >= 4:
                filter_tables = self.get_stat_stale_yes_tables(raw_sql)
                optimization_warn = StringUtils.parse_optimization_info(str(sql_explain_result), self.stdio, filter_tables)
                self.report_optimization_info_warn(optimization_warn)

            self._log_verbose("report sql_explain_result_sql complete")
            self.report_pre(sql_explain_result_sql)
            sql_explain_result.align = 'l'
            self.report_pre(str(sql_explain_result))
            self._log_verbose("report sql_explain_result complete")
        except Exception as e:
            self._log_error(f"plan explain> {explain_sql}")
            self._log_error(repr(e))

    def report_plan_cache(self, sql):
        try:
            cursor_plan_explain = self.sys_connector.execute_sql_return_cursor(sql)
            self._log_verbose("select plan_explain from ob complete")
            self.report_pre(sql)
            field_names = [col[0] for col in cursor_plan_explain.description] if cursor_plan_explain.description else []
            rows = cursor_plan_explain.fetchall()
            data_plan_explain = TableResult(field_names, rows)
            data_plan_explain.align = 'l'
            self.report_pre(str(data_plan_explain))
            self._log_verbose("report plan_explain complete")
        except Exception as e:
            self._log_error(f"plan cache> {sql}")
            self._log_error(repr(e))

    # ====================================================================
    # Schema / Collation / Histogram
    # ====================================================================

    def report_schema(self, sql, tenant_name):
        try:
            schemas = ""
            parse_tables = []
            if self.enable_dump_db:
                parser = SQLTableExtractor()
                parse_tables = parser.parse(sql)
                for t in parse_tables:
                    db_name, table_name = t
                    try:
                        self.context.set_variable('gather_tenant_name', tenant_name)
                        if db_name:
                            self.context.set_variable('gather_database', db_name)
                        else:
                            self.context.set_variable('gather_database', self.db_conn.get("database"))
                        self.context.set_variable('gather_table', table_name)
                        self.context.set_variable('gather_user', self.db_conn.get("user"))
                        self.context.set_variable('gather_password', self.db_conn.get("password"))
                        self.context.set_variable('store_dir', self.local_stored_path)
                        self.context.set_variable('gather_timestamp', self.gather_timestamp)
                        handler = GatherTableDumpHandler()
                        handler.init(self.context, store_dir=self.local_stored_path, is_inner=True)
                        handler.init(self.context, store_dir=self.local_stored_path, is_inner=True)
                        handler.handle()
                    except Exception:
                        pass
            from src.common.tool import TimeUtils
            table_info_file = os.path.join(self.local_stored_path, "obdiag_tabledump_result_{0}.txt".format(TimeUtils.timestamp_to_filename_time(self.gather_timestamp)))
            self._log_verbose(f"table info file path:{table_info_file}")
            table_info = self.get_table_info(table_info_file)
            if table_info:
                schemas = schemas + "<pre style='margin:20px;border:1px solid gray;'>%s</pre>" % table_info
            if len(table_info_file) > 25:
                FileUtil.rm(table_info_file)
            cursor = self.sys_connector.execute_sql_return_cursor("show variables like '%parallel%'")
            field_names = [col[0] for col in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            s = TableResult(field_names, rows)
            s.align = 'l'
            schemas = schemas + "<pre style='margin:20px;border:1px solid gray;'>%s</pre>" % str(s)

            cursor.execute("show variables")
            field_names = [col[0] for col in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            s = TableResult(field_names, rows)
            s.align = 'l'
            schemas = schemas + "<pre style='margin:20px;border:1px solid gray;'>%s</pre>" % str(s)

            cursor.execute("show parameters")
            field_names = [col[0] for col in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            s = TableResult(field_names, rows)
            s.align = 'l'
            schemas = schemas + "<pre style='margin:20px;border:1px solid gray;'>%s</pre>" % str(s)
            self._report("<div><h2 id='schema_anchor'>SCHEMA \\u4fe1\\u606f</h2><div id='schema' style='display: none'>" + schemas + "</div></div>")
            cursor.close()
        except Exception as e:
            self._log_error(f"report table schema failed {sql}")
            self._log_error(repr(e))

    def report_table_collation_check(self, sql, default_db_name):
        """Check collation consistency for all tables and columns used in the SQL."""
        try:
            parser = SQLTableExtractor()
            parse_tables = parser.parse(sql)
            if not parse_tables:
                self._log_verbose("No tables found in SQL, skip collation check")
                return

            collation_info = []
            all_collations = set()

            for db_name, table_name in parse_tables:
                if not db_name:
                    db_name = default_db_name or (self.db_conn.get("database") if self.db_conn else None)
                if not db_name:
                    self._log_warn(f"Database name is empty for table {table_name}, skip collation check")
                    continue

                try:
                    if self.tenant_mode == 'mysql':
                        collation_sql = """
                            SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLLATION_NAME, CHARACTER_SET_NAME
                            FROM information_schema.columns
                            WHERE TABLE_SCHEMA = '{0}' AND TABLE_NAME = '{1}' AND COLLATION_NAME IS NOT NULL
                            ORDER BY COLUMN_NAME
                        """.format(db_name.replace("'", "''"), table_name.replace("'", "''"))
                        connector = self.db_connector
                    else:
                        collation_sql = """
                            SELECT d.database_name as TABLE_SCHEMA, t.table_name as TABLE_NAME, c.column_name as COLUMN_NAME,
                                   c.data_type as DATA_TYPE, c.collation_type as COLLATION_NAME, c.charset_type as CHARACTER_SET_NAME
                            FROM oceanbase.__all_virtual_column c
                            INNER JOIN oceanbase.__all_virtual_table t ON c.tenant_id = t.tenant_id AND c.table_id = t.table_id
                            INNER JOIN oceanbase.__all_virtual_database d ON t.tenant_id = d.tenant_id AND t.database_id = d.database_id
                            WHERE UPPER(d.database_name) = UPPER('{0}') AND UPPER(t.table_name) = UPPER('{1}')
                            AND c.collation_type IS NOT NULL ORDER BY c.column_name
                        """.format(db_name.replace("'", "''"), table_name.replace("'", "''"))
                        connector = self.sys_connector

                    result = connector.execute_sql(collation_sql)
                    if result:
                        for row in result:
                            table_schema, table_name_col, column_name, data_type, collation_name, charset_name = row
                            if collation_name:
                                collation_info.append({
                                    'database': table_schema, 'table': table_name_col,
                                    'column': column_name, 'data_type': data_type,
                                    'collation': collation_name, 'charset': charset_name,
                                })
                                all_collations.add(collation_name)
                except Exception as e:
                    self._log_warn(f"Failed to check collation for table {db_name}.{table_name}: {str(e)}")
                    continue

            if not collation_info:
                self._log_verbose("No collation information found, skip collation check report")
                return

            if len(all_collations) > 1:
                warning_content = "<div class='statsWarning'>"
                warning_content += "<h4>\\u26a0\\ufe0f Collation Inconsistency Warning</h4>"
                warning_content += "<p><strong>Issue:</strong> The SQL uses tables/columns with different collations. "
                warning_content += "When executing SQL, all tables and columns should have the same collation for better performance. "
                warning_content += "If collation can't keep consistent, columns will be casted, which may impact performance.</p>"
                warning_content += "<p><strong>Found {0} different collation(s):</strong> {1}</p>".format(len(all_collations), ", ".join(sorted(all_collations)))
                warning_content += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; margin: 10px 0;'>"
                warning_content += "<thead><tr style='background-color: #f0f0f0;'><th>Database</th><th>Table</th><th>Column</th><th>Data Type</th><th>Collation</th><th>Charset</th></tr></thead><tbody>"
                for info in collation_info:
                    warning_content += "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td><strong>{4}</strong></td><td>{5}</td></tr>".format(
                        info['database'], info['table'], info['column'], info['data_type'], info['collation'], info['charset'] or 'N/A')
                warning_content += "</tbody></table>"
                warning_content += "<p><strong>Recommendation:</strong> Consider modifying table/column collations to be consistent for better SQL execution performance.</p></div>"
                self._report(warning_content)
                self._log_warn(f"Collation inconsistency detected: {len(all_collations)} different collation(s) found")
            else:
                info_content = "<div style='background-color: #e8f5e9; padding: 10px; margin: 10px 0; border-left: 4px solid #4caf50;'>"
                info_content += "<h4>\\u2713 Collation Consistency Check</h4>"
                info_content += "<p>All tables and columns use the same collation: <strong>{0}</strong></p>".format(list(all_collations)[0])
                info_content += "<p>This is good for SQL execution performance.</p></div>"
                self._report(info_content)
                self._log_verbose(f"Collation check passed: all columns use collation {list(all_collations)[0]}")

        except Exception as e:
            self._log_error(f"report table collation check failed: {str(e)}")

    def report_table_histograms(self, sql, default_db_name):
        """Report histogram statistics for tables used in the SQL (Issue #626)."""
        try:
            parser = SQLTableExtractor()
            parse_tables = parser.parse(sql)
            if not parse_tables:
                self._log_verbose("No tables found in SQL, skip histogram report")
                return
            if self.ob_major_version < 4:
                self._log_verbose("Histogram views (DBA_TAB_HISTOGRAMS) are supported from OB 4.x, skip")
                return

            section_added = False
            for db_name, table_name in parse_tables:
                if not db_name:
                    db_name = default_db_name or (self.db_conn.get("database") if self.db_conn else None)
                if not db_name:
                    self._log_warn(f"Database name is empty for table {table_name}, skip histogram")
                    continue
                try:
                    hist_sql = self.sql_plan_monitor_histogram_sql(db_name, table_name)
                    self._log_verbose(f"execute histogram SQL for {db_name}.{table_name}")
                    cursor = self.db_connector.execute_sql_return_cursor(hist_sql)
                    rows = cursor.fetchall()
                    cursor.close()
                    if rows:
                        if not section_added:
                            self._report("<div><h2 id='histogram_anchor'>\\u7edf\\u8ba1\\u4fe1\\u606f\\u76f4\\u65b9\\u56fe (Histogram)</h2>")
                            section_added = True
                        cursor_tbl = self.db_connector.execute_sql_return_cursor(hist_sql)
                        field_names = [col[0] for col in cursor_tbl.description] if cursor_tbl.description else []
                        rows = cursor_tbl.fetchall()
                        tbl = TableResult(field_names, rows)
                        tbl.align = 'l'
                        self._report("<h3>{0}.{1}</h3>".format(db_name, table_name))
                        self._report("<div class='v' style='display: none'>" + tbl.get_html_string() + "</div>")
                        cursor_tbl.close()

                    part_sql = self.sql_plan_monitor_part_histogram_sql(db_name, table_name)
                    cursor_part = self.db_connector.execute_sql_return_cursor(part_sql)
                    part_rows = cursor_part.fetchall()
                    cursor_part.close()
                    if part_rows:
                        if not section_added:
                            self._report("<div><h2 id='histogram_anchor'>\\u7edf\\u8ba1\\u4fe1\\u606f\\u76f4\\u65b9\\u56fe (Histogram)</h2>")
                            section_added = True
                        cursor_part_tbl = self.db_connector.execute_sql_return_cursor(part_sql)
                        field_names = [col[0] for col in cursor_part_tbl.description] if cursor_part_tbl.description else []
                        rows = cursor_part_tbl.fetchall()
                        tbl_part = TableResult(field_names, rows)
                        tbl_part.align = 'l'
                        self._report("<h3>{0}.{1} (\\u5206\\u533a\\u76f4\\u65b9\\u56fe DBA_PART_HISTOGRAMS)</h3>".format(db_name, table_name))
                        self._report("<div class='v' style='display: none'>" + tbl_part.get_html_string() + "</div>")
                        cursor_part_tbl.close()
                except Exception as e:
                    self._log_warn(f"Failed to get histogram for {db_name or ''}.{table_name}: {str(e)}")
                    continue

            if section_added:
                self._report("</div>")
        except Exception as e:
            self._log_error(f"report table histograms failed: {str(e)}")

    # ====================================================================
    # DFO / SVR / Detail report sections
    # ====================================================================

    def report_sql_plan_monitor_dfo_op(self, sql):
        data_sql_plan_monitor_dfo_op = self.sys_connector.execute_sql_pretty(sql)
        if len(data_sql_plan_monitor_dfo_op.rows) == 0:
            self._log_warn("failed to find sql_plan_monitor data, please add hint /*+ monitor*/ to your SQL before executing it.")
        self._report("<div><h2 id='agg_table_anchor'>SQL_PLAN_MONITOR DFO \\u7ea7\\u8c03\\u5ea6\\u65f6\\u5e8f\\u6c47\\u603b</h2><div class='v' id='agg_table' style='display: none'>" + data_sql_plan_monitor_dfo_op.get_html_string() + "</div></div>")
        self._log_verbose("report SQL_PLAN_MONITOR DFO complete")
        cursor_sql_plan_monitor_dfo_op = self.sys_connector.execute_sql_return_cursor_dictionary(sql)
        if self.ob_major_version >= 4:
            self.report_dfo_sched_agg_graph_data_obversion4(cursor_sql_plan_monitor_dfo_op, '\\u8c03\\u5ea6\\u65f6\\u5e8f\\u56fe')
        else:
            self.report_dfo_sched_agg_graph_data(cursor_sql_plan_monitor_dfo_op, '\\u8c03\\u5ea6\\u65f6\\u5e8f\\u56fe')
        self._log_verbose("report SQL_PLAN_MONITOR DFO SCHED complete")
        cursor_sql_plan_monitor_dfo_op = self.sys_connector.execute_sql_return_cursor_dictionary(sql)
        if self.ob_major_version >= 4:
            self.report_dfo_agg_graph_data_obversion4(cursor_sql_plan_monitor_dfo_op, '\\u6570\\u636e\\u65f6\\u5e8f\\u56fe')
        else:
            self.report_dfo_agg_graph_data(cursor_sql_plan_monitor_dfo_op, '\\u6570\\u636e\\u65f6\\u5e8f\\u56fe')
        self._log_verbose("report SQL_PLAN_MONITOR DFO graph data complete")

    def report_db_time_display_op(self, sql):
        if self.ob_major_version >= 4:
            self.report_db_time_display_obversion4(sql)
            self._log_verbose("report db time display complete")

    def report_sql_plan_monitor_svr_agg(self, sql_plan_monitor_svr_agg_v1, sql_plan_monitor_svr_agg_v2):
        cursor = self.sys_connector.execute_sql_return_cursor(sql_plan_monitor_svr_agg_v1)
        field_names = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        table_result = TableResult(field_names, rows)
        self._report(
            "<div><h2 id='svr_agg_table_anchor'>SQL_PLAN_MONITOR SQC \\u7ea7\\u6c47\\u603b</h2><div class='v' id='svr_agg_table' style='display: none'>"
            + table_result.get_html_string()
            + "</div><div class='shortcut'><a href='#svr_agg_serial_v1'>Goto \\u7b97\\u5b50\\u4f18\\u5148</a> <a href='#svr_agg_serial_v2'>Goto \\u673a\\u5668\\u4f18\\u5148</a></div></div>"
        )
        self._log_verbose("report SQL_PLAN_MONITOR SQC complete")
        cursor_v1 = self.sys_connector.execute_sql_return_cursor_dictionary(sql_plan_monitor_svr_agg_v2)
        if self.ob_major_version >= 4:
            self.report_svr_agg_graph_data_obversion4('svr_agg_serial_v1', cursor_v1, '\\u7b97\\u5b50\\u4f18\\u5148\\u89c6\\u56fe')
        else:
            self.report_svr_agg_graph_data('svr_agg_serial_v1', cursor_v1, '\\u7b97\\u5b50\\u4f18\\u5148\\u89c6\\u56fe')
        cursor_v2 = self.sys_connector.execute_sql_return_cursor_dictionary(sql_plan_monitor_svr_agg_v2)
        if self.ob_major_version >= 4:
            self.report_svr_agg_graph_data('svr_agg_serial_v2', cursor_v2, '\\u673a\\u5668\\u4f18\\u5148\\u89c6\\u56fe')
        else:
            self.report_svr_agg_graph_data('svr_agg_serial_v2', cursor_v2, '\\u673a\\u5668\\u4f18\\u5148\\u89c6\\u56fe')
        self._log_verbose("report SQL_PLAN_MONITOR SQC server priority complete")

    def report_sql_plan_monitor_detail_operator_priority(self, sql):
        cursor = self.sys_connector.execute_sql_return_cursor(sql)
        if self.enable_fast_dump:
            table_html = "no result in --fast mode"
        else:
            field_names = [col[0] for col in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            table_result = TableResult(field_names, rows)
            table_html = table_result.get_html_string()
        self._report(
            "<div><h2 id='detail_table_anchor'>SQL_PLAN_MONITOR \\u8be6\\u60c5</h2><div class='v' id='detail_table' style='display: none'>"
            + table_html
            + "</div><div class='shortcut'><a href='#detail_serial_v1'>Goto \\u7b97\\u5b50\\u4f18\\u5148</a> <a href='#detail_serial_v2'>Goto \\u7ebf\\u7a0b\\u4f18\\u5148</a></div></div>"
        )
        self._log_verbose("report SQL_PLAN_MONITOR details complete")
        cursor_v1 = self.sys_connector.execute_sql_return_cursor_dictionary(sql)
        if self.ob_major_version >= 4:
            self.report_detail_graph_data_obversion4("detail_serial_v1", cursor_v1, '\\u7b97\\u5b50\\u4f18\\u5148\\u89c6\\u56fe')
        else:
            self.report_detail_graph_data("detail_serial_v1", cursor_v1, '\\u7b97\\u5b50\\u4f18\\u5148\\u89c6\\u56fe')

    def reportsql_plan_monitor_detail_svr_priority(self, sql):
        cursor_v2 = self.sys_connector.execute_sql_return_cursor_dictionary(sql)
        if self.ob_major_version >= 4:
            self.report_detail_graph_data_obversion4("detail_serial_v2", cursor_v2, '\\u7ebf\\u7a0b\\u4f18\\u5148\\u89c6\\u56fe')
        else:
            self.report_detail_graph_data("detail_serial_v2", cursor_v2, '\\u7ebf\\u7a0b\\u4f18\\u5148\\u89c6\\u56fe')

    # ====================================================================
    # ASH / DB Time / Display Cursor
    # ====================================================================

    def report_ash_obversion4(self, ash_top_event_sql):
        ash_report = ""
        try:
            if self.ob_major_version >= 4:
                cursor = self.db_connector.execute_sql_return_cursor(ash_top_event_sql)
                field_names = [col[0] for col in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                s = TableResult(field_names, rows)
                s.align = 'l'
                ash_report = ash_report + "<pre style='margin:20px;border:1px solid gray;'>%s\n%s</pre>" % (ash_top_event_sql, str(s))
                self._report("<div><h2 id='ash_anchor'>ASH \\u4fe1\\u606f</h2><div id='ash' style='display: none'>" + ash_report + "</div></div>")
                self._log_verbose("ash report complete")
            else:
                self._log_verbose(f"ash report requires OB version >= 4.0. Your version: {self.ob_major_version}")
        except Exception as e:
            self._log_error(f"ash report> {ash_top_event_sql}")
            self._log_error(repr(e))

    def report_db_time_display_obversion4(self, sql_plan_monitor_db_time):
        try:
            if self.ob_major_version >= 4:
                cursor = self.db_connector.execute_sql_return_cursor_dictionary(sql_plan_monitor_db_time)
                self._log_verbose(f"execute SQL: {sql_plan_monitor_db_time}")
                self.report_dfo_agg_db_time_graph_data_obversion4(cursor, 'DB Time \\u7b97\\u5b50\\u771f\\u5b9e\\u8017\\u65f6\\u5206\\u6790\\u56fe')
                self._log_verbose("DB Time display complete")
            else:
                self._log_verbose(f"DB Time display requires OB version >= 4.0. Your version: {self.ob_major_version}")
        except Exception as e:
            self._log_error(f"DB Time display> {sql_plan_monitor_db_time}")
            self._log_error(repr(e))

    def report_display_cursor_obversion4(self, display_cursor_sql):
        if self.skip and self.skip == "dbms_xplan":
            self._log_warn("you have set the option --skip to skip gather dbms_xplan")
            return
        try:
            if not StringUtils.compare_versions_lower(self.ob_version, "4.2.5.0"):
                self._log_info(f"execute SQL: {display_cursor_sql}")
                plan_result = self.db_connector.execute_sql_pretty(display_cursor_sql)
                if plan_result:
                    plan_result.align = 'l'
                    self.report_pre("obclient> " + display_cursor_sql)
                    self.report_pre(plan_result)
                    self._log_verbose("display_cursor report complete")
                else:
                    self._log_warn("the result of display_cursor is None")
            else:
                self._log_verbose(f"display_cursor requires OB version >= 4.2.5.0. Your version: {self.ob_major_version}")
        except Exception as e:
            self._log_error(f"display_cursor report> {display_cursor_sql}")
            self._log_error(repr(e))
