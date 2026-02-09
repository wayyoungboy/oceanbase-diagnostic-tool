#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: handler.py
@desc: Main GatherPlanMonitorHandler - orchestration logic.
       Report rendering, graph data, SQL building and stat processing
       are delegated to separate mixin modules.
"""

import os
import re
import sys
import shutil
import time

from src.common.base_handler import BaseHandler
from src.common.ob_connector import OBConnector
from src.common.tool import Util, DirectoryUtil, StringUtils, FileUtil, TimeUtils
from src.common.command import get_observer_commit_id
from src.common.result_type import ObdiagResult
from src.common.version import OBDIAG_VERSION

from src.handler.gather.plan_monitor.sql_builder import SQLBuilderMixin
from src.handler.gather.plan_monitor.graph_renderer import GraphRendererMixin
from src.handler.gather.plan_monitor.stat_processor import StatProcessorMixin
from src.handler.gather.plan_monitor.report_sections import ReportSectionsMixin


class GatherPlanMonitorHandler(SQLBuilderMixin, GraphRendererMixin, StatProcessorMixin, ReportSectionsMixin, BaseHandler):
    """
    Handler for gathering SQL Plan Monitor reports.

    Composed from mixins:
    - SQLBuilderMixin: SQL query generation
    - GraphRendererMixin: JavaScript timeline graph rendering
    - StatProcessorMixin: Statistics processing
    - ReportSectionsMixin: Report section rendering (HTML)
    """

    def _init(self, gather_pack_dir='./', is_scene=False, **kwargs):
        """Subclass initialization"""
        self.ob_cluster = None
        self.local_stored_path = gather_pack_dir
        self.tenant_mode = None
        self.sys_database = None
        self.database = None
        self.enable_dump_db = True
        self.trace_id = None
        self.env = {}
        self.STAT_NAME = {}
        self.report_file_path = ""
        self.enable_fast_dump = False
        self.ob_major_version = None
        self.sql_audit_name = "gv$sql_audit"
        self.plan_explain_name = "gv$plan_cache_plan_explain"
        self.is_scene = is_scene
        self.ob_version = "4.2.5.0"
        self.skip = None
        self.db_tables = []

        if self.context.get_variable("gather_timestamp", None):
            self.gather_timestamp = self.context.get_variable("gather_timestamp")
        else:
            self.gather_timestamp = TimeUtils.get_current_us_timestamp()

        # Initialize config
        ob_cluster = self.context.cluster_config
        self.ob_cluster = ob_cluster
        self.sys_connector = OBConnector(
            context=self.context,
            ip=ob_cluster.get("db_host"),
            port=ob_cluster.get("db_port"),
            username=ob_cluster.get("tenant_sys").get("user"),
            password=ob_cluster.get("tenant_sys").get("password"),
            timeout=100,
        )
        self.ob_cluster_name = ob_cluster.get("ob_cluster_name")

        # Initialize options
        trace_id_option = self._get_option('trace_id')
        if self.context.get_variable("gather_plan_monitor_trace_id", None):
            trace_id_option = self.context.get_variable("gather_plan_monitor_trace_id")

        if trace_id_option is not None:
            self.trace_id = trace_id_option
        else:
            raise ValueError("option --trace_id not found, please provide")

        store_dir_option = self._get_option('store_dir')
        if store_dir_option and store_dir_option != './':
            if not os.path.exists(os.path.abspath(store_dir_option)):
                self._log_warn(f'warn: option --store_dir [{os.path.abspath(store_dir_option)}] incorrect: No such directory, Now create it')
                os.makedirs(os.path.abspath(store_dir_option))
            self.local_stored_path = os.path.abspath(store_dir_option)

        env_option = self._get_option('env')
        if env_option is not None:
            self._log_verbose("use db_connector")
            if not self.__init_db_conn(env_option):
                raise ValueError("Failed to initialize db connection")
        else:
            self._log_verbose("use sys_connector")
            self.db_connector = self.sys_connector

        skip_option = self._get_option('skip')
        if skip_option:
            self.skip = skip_option

        if not self.tenant_mode_detected():
            raise ValueError("Failed to detect tenant mode")

    def __init_db_connector(self):
        self.db_connector = OBConnector(
            context=self.context,
            ip=self.db_conn.get("host"),
            port=self.db_conn.get("port"),
            username=self.db_conn.get("user"),
            password=self.db_conn.get("password") or "",
            database=self.db_conn.get("database"),
            timeout=100,
        )

    def handle(self) -> ObdiagResult:
        """Main handle logic"""
        self._validate_initialized()

        try:
            if self.is_scene:
                pack_dir_this_command = self.local_stored_path
            else:
                pack_dir_this_command = os.path.join(self.local_stored_path, f"obdiag_gather_{TimeUtils.timestamp_to_filename_time(self.gather_timestamp)}")
            self.report_file_path = os.path.join(pack_dir_this_command, "sql_plan_monitor_report.html")
            self._log_verbose(f"Use {pack_dir_this_command} as pack dir.")
            DirectoryUtil.mkdir(path=pack_dir_this_command, stdio=self.stdio)
            gather_tuples = []
            gather_pack_path_dict = {}

            def handle_plan_monitor_from_ob(cluster_name):
                st = time.time()
                resp = self.init_resp()
                result_sql_audit_by_trace_id_limit1 = self.select_sql_audit_by_trace_id_limit1()
                if len(result_sql_audit_by_trace_id_limit1) > 0:
                    trace = result_sql_audit_by_trace_id_limit1[0]
                    trace_id = trace[0]
                    user_sql = trace[1]
                    sql = trace[1]
                    tenant_name = trace[6]
                    db_name = trace[8]
                    plan_id = trace[9]
                    tenant_id = trace[10]
                    svr_ip = trace[12]
                    svr_port = trace[13]
                    params_value = None
                    try:
                        params_value = trace[14]
                    except IndexError:
                        self._log_verbose("OceanBase version is 3.x, params_value column is not available.")

                    if params_value:
                        sql = StringUtils.fill_sql_with_params(sql, params_value, self.stdio)
                        user_sql = sql

                    self._log_verbose(f"TraceID: {trace_id}, SQL: {sql}, SVR_IP: {svr_ip}, SVR_PORT: {svr_port}")
                    self._log_verbose(f"DB: {db_name}, PLAN_ID: {plan_id}, TENANT_NAME: {tenant_name}, TENANT_ID: {tenant_id}")

                    sql_plan_monitor_svr_agg_template = self.sql_plan_monitor_svr_agg_template_sql()
                    sql_plan_monitor_svr_agg_v1 = str(sql_plan_monitor_svr_agg_template).replace("##REPLACE_TRACE_ID##", trace_id).replace("##REPLACE_ORDER_BY##", "PLAN_LINE_ID ASC, MAX_CHANGE_TIME ASC, SVR_IP, SVR_PORT")
                    sql_plan_monitor_svr_agg_v2 = str(sql_plan_monitor_svr_agg_template).replace("##REPLACE_TRACE_ID##", trace_id).replace("##REPLACE_ORDER_BY##", "SVR_IP, SVR_PORT, PLAN_LINE_ID")

                    sql_plan_monitor_detail_template = self.sql_plan_monitor_detail_template_sql()
                    sql_plan_monitor_detail_v1 = str(sql_plan_monitor_detail_template).replace("##REPLACE_TRACE_ID##", trace_id).replace("##REPLACE_ORDER_BY##", "PLAN_LINE_ID ASC, SVR_IP, SVR_PORT, CHANGE_TS, PROCESS_NAME ASC")
                    sql_plan_monitor_detail_v2 = str(sql_plan_monitor_detail_template).replace("##REPLACE_TRACE_ID##", trace_id).replace("##REPLACE_ORDER_BY##", "PROCESS_NAME ASC, PLAN_LINE_ID ASC, FIRST_REFRESH_TIME ASC")

                    sql_plan_monitor_dfo_op = self.sql_plan_monitor_dfo_op_sql(tenant_id, plan_id, trace_id, svr_ip, svr_port)
                    sql_ash_top_event = self.sql_ash_top_event_sql(tenant_id, trace_id)
                    sql_plan_monitor_db_time = self.sql_plan_monitor_db_time_sql(tenant_id, trace_id)
                    full_audit_sql_by_trace_id_sql = self.full_audit_sql_by_trace_id_sql(trace_id)
                    plan_explain_sql = self.plan_explain_sql(tenant_id, plan_id, svr_ip, svr_port)

                    # Generate report sections
                    self.report_header()
                    if not self.report_sql_audit():
                        return
                    self.report_plan_explain(db_name, sql)
                    self.report_plan_cache(plan_explain_sql)

                    display_cursor_sql = "SELECT DBMS_XPLAN.DISPLAY_CURSOR({plan_id}, 'all', '{svr_ip}',  {svr_port}, {tenant_id}) FROM DUAL".format(
                        plan_id=plan_id, svr_ip=svr_ip, svr_port=svr_port, tenant_id=tenant_id)
                    self.report_display_cursor_obversion4(display_cursor_sql)
                    self.report_schema(user_sql, tenant_name)
                    self.report_table_collation_check(user_sql, db_name)
                    self.report_table_histograms(user_sql, db_name)
                    self.report_ash_obversion4(sql_ash_top_event)
                    self.init_monitor_stat()
                    self.report_sql_audit_details(full_audit_sql_by_trace_id_sql)
                    self.report_sql_plan_monitor_dfo_op(sql_plan_monitor_dfo_op)
                    self.report_db_time_display_op(sql_plan_monitor_db_time)
                    self.report_sql_plan_monitor_svr_agg(sql_plan_monitor_svr_agg_v1, sql_plan_monitor_svr_agg_v2)
                    self.report_fast_preview()
                    self.report_sql_plan_monitor_detail_operator_priority(sql_plan_monitor_detail_v1)
                    self.reportsql_plan_monitor_detail_svr_priority(sql_plan_monitor_detail_v2)

                    self._report("<h4>\u672c\u62a5\u544a\u5728\u79df\u6237\u4e0b\u4f7f\u7528\u7684 SQL</h4>")
                    self._report("<div class='help' style='font-size:11px'>DFO \u7ea7<hr /><pre>%s</pre></div><br/>" % (sql_plan_monitor_dfo_op))
                    self._report("<div class='help' style='font-size:11px'>\u673a\u5668\u7ea7<hr /><pre>%s</pre></div><br/>" % (sql_plan_monitor_svr_agg_v1))
                    self._report("<div class='help' style='font-size:11px'>\u7ebf\u7a0b\u7ea7<hr /><pre>%s</pre></div><br/>" % (sql_plan_monitor_detail_v1))

                    t = time.localtime(time.time())
                    self._report("Report generation time\uff1a %s <br>" % (time.strftime("%Y-%m-%d %H:%M:%S", t)))
                    self._report("obdiag version: {0} <br>".format(OBDIAG_VERSION))
                    self._report("observer version: {0} <br>".format(self.ob_version))
                    observer_version_commit_id = get_observer_commit_id(self.context)
                    if observer_version_commit_id:
                        self._report("observer commit id: {0} <br>".format(observer_version_commit_id))
                    self.report_footer()
                    self._log_verbose("report footer complete")
                else:
                    self._log_error(f"The data queried with the specified trace_id {self.trace_id} from {self.sql_audit_name} is empty.")

                if resp["skip"]:
                    return
                if resp["error"]:
                    gather_tuples.append((cluster_name, True, resp["error_msg"], 0, int(time.time() - st), "Error:{0}".format(resp["error_msg"]), ""))
                    return
                gather_pack_path_dict[cluster_name] = resp["gather_pack_path"]
                gather_tuples.append((cluster_name, False, "", int(time.time() - st), pack_dir_this_command))

            if getattr(sys, 'frozen', False):
                absPath = os.path.dirname(sys.executable)
            else:
                absPath = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            cs_resources_path = os.path.join(absPath, "resources")
            self._log_verbose(f"[cs resource path] : {cs_resources_path}")
            target_resources_path = os.path.join(pack_dir_this_command, "resources")
            self.copy_cs_resource(cs_resources_path, target_resources_path)
            self._log_verbose("[sql plan monitor report task] start")
            handle_plan_monitor_from_ob(self.ob_cluster_name)
            self._log_verbose("[sql plan monitor report task] end")
            summary_tuples = self.__get_overall_summary(gather_tuples)
            self._log_info(summary_tuples)
            FileUtil.write_append(os.path.join(pack_dir_this_command, "result_summary.txt"), summary_tuples)
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"store_dir": pack_dir_this_command})

        except Exception as e:
            return self._handle_error(e)

    # ====================================================================
    # Private helpers
    # ====================================================================

    def __init_db_conn(self, env):
        try:
            if not isinstance(env, list):
                self._log_error("Invalid env format. Please use --env key=value format")
                return False

            env_dict = StringUtils.parse_env_display(env)
            self.env = env_dict

            self.db_conn = StringUtils.build_db_info_from_env(env_dict, self.stdio)
            if not self.db_conn:
                self._log_error("Failed to build database connection information from env parameters")
                return False

            if StringUtils.validate_db_info(self.db_conn):
                self.__init_db_connector()
                return True
            else:
                self._log_error("db connection information required: --env host=... --env port=... --env user=... --env password=... --env database=...")
                return False
        except Exception as e:
            self.db_connector = self.sys_connector
            self._log_error(f"init db connector, error: {e}, please check --env option ")

    def __get_overall_summary(self, node_summary_tuple):
        summary_tab = []
        field_names = ["Cluster", "Status", "Time", "PackPath"]
        for tup in node_summary_tuple:
            cluster = tup[0]
            is_err = tup[2]
            consume_time = tup[3]
            pack_path = tup[4]
            summary_tab.append((cluster, "Error" if is_err else "Completed", "{0} s".format(int(consume_time)), pack_path))
        return self._generate_summary_table(field_names, summary_tab, "Gather Sql Plan Monitor Summary")

    def _report(self, s):
        """Write content to the report HTML file."""
        with open(self.report_file_path, 'a') as f:
            f.write(s)

    # Keep double-underscore version for backward compat with name mangling
    __report = _report

    def tenant_mode_detected(self):
        try:
            data = self.db_connector.execute_sql("show variables like 'version_comment'")
            for row in data:
                ob_version = row[1]

            version_pattern = r'(?:OceanBase(_CE)?\s+)?(\d+\.\d+\.\d+(?:\.\d+)?)'
            matched_version = re.search(version_pattern, ob_version)
            if matched_version:
                version = matched_version.group(2)
                self.ob_version = version
                major_version = int(version.split('.')[0])
                self.sql_audit_name = "gv$ob_sql_audit" if major_version >= 4 else "gv$sql_audit"
                self.plan_explain_name = "gv$ob_plan_cache_plan_explain" if major_version >= 4 else "gv$plan_cache_plan_explain"
                self.ob_major_version = major_version
                self.tenant_mode = "mysql"
                self.sys_database = "oceanbase"
                self._log_verbose(f"Detected MySQL mode, version: {ob_version}")
                return True
            else:
                raise ValueError("Failed to match MySQL version")
        except Exception:
            try:
                data = self.sys_connector.execute_sql("select SUBSTR(BANNER, 11, 100) from V$VERSION;")
                banner = data[0][0]
                version_pattern = r'(\d+\.\d+\.\d+\.\d+)'
                matched_version = re.search(version_pattern, banner)
                if matched_version:
                    version = matched_version.group(1)
                    major_version = int(version.split('.')[0])
                    self.sql_audit_name = "gv$ob_sql_audit" if major_version >= 4 else "gv$sql_audit"
                    self.ob_major_version = major_version
                    self.tenant_mode = "oracle"
                    self.sys_database = "SYS"
                    self._log_verbose(f"Detected Oracle mode, version: {version}")
                    return True
                else:
                    raise ValueError("Failed to match Oracle version")
            except Exception as oe:
                self._log_error(f"Error detecting database mode: {oe}")

    def init_resp(self):
        resp = {"skip": False, "error": False, "gather_pack_path": self.local_stored_path}
        return resp

    def copy_cs_resource(self, source_path, target_path):
        shutil.copytree(source_path, target_path)

    def select_sql_audit_by_trace_id_limit1(self):
        sql = self.sql_audit_by_trace_id_limit1_sql()
        return self.sys_connector.execute_sql(sql)

    def get_table_info(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self._log_warn(str(e))
            return None

    def get_stat_stale_yes_tables(self, sql):
        try:
            from src.common.tool import SQLTableExtractor
            parser = SQLTableExtractor()
            parse_tables = parser.parse(sql)
            for t in parse_tables:
                db_name, table_name = t
                if not db_name:
                    db_name = self.db_conn.get("database")
                self.db_tables.append((db_name, table_name))
        except Exception as e:
            self._log_warn(f"parse_tables failed, err: {str(e)}")
        stale_tables = []
        for db, table in self.db_tables:
            check_sql = """
                SELECT IS_STALE FROM oceanbase.DBA_OB_TABLE_STAT_STALE_INFO
                WHERE DATABASE_NAME = '{0}' AND TABLE_NAME = '{1}' limit 1
            """.format(db, table)
            try:
                result = self.db_connector.execute_sql(check_sql)
                is_stale = result[0][0] if result else 'NO'
                self._log_info(f"{db}.{table} -> IS_STALE={is_stale}")
                if is_stale == 'YES':
                    stale_tables.append(table)
            except Exception as e:
                self._log_warn(f"execute SQL: {check_sql} {str(e)}")
                continue
        return stale_tables
