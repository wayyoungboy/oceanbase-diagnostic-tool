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
@time: 2024/07/08
@file: gather_tabledump.py
@desc:
"""

import os
import time

from src.common.base_handler import BaseHandler
from src.common.result_type import ObdiagResult
from src.common.ob_connector import OBConnector
from src.common.tool import StringUtils
from src.common.command import get_observer_version
from src.common.tool import Util
from src.common.tool import TimeUtils
from tabulate import tabulate


class GatherTableDumpHandler(BaseHandler):
    def _init(self, store_dir="./obdiag_gather_report", is_inner=False, **kwargs):
        """Subclass initialization"""
        self.report = None
        self.report_path = None
        self.ob_cluster = {}
        self.ob_connector = None
        self.tenant_connector = None
        self.database = None
        self.table = None
        self.result_list = []
        self.store_dir = store_dir
        self.is_innner = is_inner

        if self.context.get_variable("gather_timestamp", None):
            self.gather_timestamp = self.context.get_variable("gather_timestamp")
        else:
            self.gather_timestamp = TimeUtils.get_current_us_timestamp()

        # Initialize config and options
        self.ob_cluster = self.context.cluster_config
        self.obproxy_nodes = self.context.obproxy_config['servers']
        self.ob_nodes = self.context.cluster_config['servers']
        new_nodes = Util.get_nodes_list(self.context, self.ob_nodes, self.stdio)
        if new_nodes:
            self.nodes = new_nodes

        # Get options
        self.database = self._get_option('database')
        self.table = self._get_option('table')
        user = self._get_option('user')
        password = self._get_option('password') or ""
        store_dir_option = self._get_option('store_dir')

        if store_dir_option is not None and store_dir_option != './':
            if not os.path.exists(os.path.abspath(store_dir_option)):
                self._log_warn(f'args --store_dir [{os.path.abspath(store_dir_option)}]: No such directory, Now create it')
                os.makedirs(os.path.abspath(store_dir_option))
                self.store_dir = os.path.abspath(store_dir_option)

        if self.context.get_variable("gather_database", None):
            self.database = self.context.get_variable("gather_database")
        if self.context.get_variable("gather_table", None):
            self.table = self.context.get_variable("gather_table")
        if self.context.get_variable("gather_user", None):
            user = self.context.get_variable("gather_user")
        if self.context.get_variable("gather_password", None):
            password = self.context.get_variable("gather_password")
        if self.context.get_variable("store_dir", None):
            self.store_dir = self.context.get_variable("store_dir")

        if not (self.database and self.table and user):
            raise ValueError("option --database/--table/--user not found, please provide")

        if self.context.get_variable("gather_tenant_name", None):
            self.tenant_name = self.context.get_variable("gather_tenant_name")
        else:
            self.tenant_name = self.__extract_string(user)

        self.database = self._clean_identifier(self.database)
        self.table = self._clean_identifier(self.table)

        self.ob_connector = OBConnector(
            context=self.context, ip=self.ob_cluster.get("db_host"), port=self.ob_cluster.get("db_port"), username=self.ob_cluster.get("tenant_sys").get("user"), password=self.ob_cluster.get("tenant_sys").get("password"), timeout=100
        )
        self.tenant_connector = OBConnector(context=self.context, ip=self.ob_cluster.get("db_host"), port=self.ob_cluster.get("db_port"), username=user, password=password, timeout=100)
        self.file_name = f"{self.store_dir}/obdiag_tabledump_result_{TimeUtils.timestamp_to_filename_time(self.gather_timestamp)}.txt"

    def _clean_identifier(self, identifier):
        if identifier:
            return identifier.replace('`', '')
        return identifier

    def handle(self) -> ObdiagResult:
        """Main handle logic"""
        self._validate_initialized()

        try:
            self.start_time = time.time()
            excute_status = self.execute()
            if not self.is_innner and excute_status:
                self.__print_result()
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"store_dir": self.store_dir})
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="execute failed")

        except Exception as e:
            return self._handle_error(e)

    def execute(self):
        try:
            self.version = get_observer_version(self.context)
            if self.__get_table_schema():
                if self.version == "4.0.0.0" or StringUtils.compare_versions_greater(self.version, "4.0.0.0"):
                    return self.__get_table_info()
                else:
                    return self.__get_table_info_v3()
        except Exception as e:
            self._log_error(f"report sql result failed, error: {e}")

    def __get_table_schema(self):
        try:
            self.table = self.__extract_table_name(self.table)
            sql = "show create table " + self.database + "." + self.table
            columns, result = self.tenant_connector.execute_sql_return_columns_and_data(sql)
            if result is None or len(result) == 0:
                self._log_verbose(f"excute sql: {sql},  result is None")
            else:
                self.__report_simple(sql, result[0][1])
            return True
        except Exception as e:
            self._log_verbose(f"show create table error: {e}")

    def __get_table_info(self):
        try:
            # Use parameterized query for tenant lookup
            tenant_data = self.ob_connector.execute_sql("select tenant_id from oceanbase.__all_tenant where tenant_name = %s", (self.tenant_name,))
            if len(tenant_data) == 0:
                self._log_error("tenant is None")
                return
            self.tenant_id = tenant_data[0][0]

            ## 查询行数 - Note: identifiers (table/db names) cannot be parameterized in MySQL,
            ## but the values come from user config, not external input
            query_count = (
                f"select /*+read_consistency(weak) */ table_name , ifnull(num_rows,0) as num_rows from oceanbase.cdb_tables where con_id = '{self.tenant_id}' and owner = '{self.database}' and table_name = '{self.table}' order by num_rows desc limit 1"
            )
            columns, result = self.ob_connector.execute_sql_return_columns_and_data(query_count)
            if result.count == 0:
                self._log_error("line count is None")
                return
            self._log_info(f"table count {result}")

            self.__report(query_count, columns, result)
            ## 查询数据量

            query_data = f'''select y.SVR_IP,y.DATABASE_NAME,
                case when y.TABLE_TYPE = 'INDEX' then '' else y.TABLE_NAME end as TABLE_NAME,
                y.TABLE_TYPE,
                sum(y.DATA_SIZE) AS "DATA_SIZE(MB)",sum(y.REQUIRED_SIZE) AS "REQUIRED_SIZE(MB)"
                from (
                    select a.TENANT_ID, a.SVR_IP, a.TABLET_ID, b.table_id, b.DATABASE_NAME, b.TABLE_NAME, b.TABLE_TYPE, ROUND(a.data_size/1024/1024,2) AS "DATA_SIZE", ROUND(a.required_size/1024/1024,2) AS "REQUIRED_SIZE" 
                        from oceanbase.CDB_OB_TABLET_REPLICAS a join oceanbase.cdb_ob_table_locations b on a.TABLET_ID=b.TABLET_ID and a.svr_ip=b.svr_ip and a.tenant_id=b.tenant_id 
                where a.TENANT_ID={self.tenant_id} 
                and b.DATABASE_NAME='{self.database}'
                and (
                b.TABLE_NAME='{self.table}'
                or b.DATA_TABLE_ID in(select table_id from oceanbase.cdb_ob_table_locations where TENANT_ID={self.tenant_id} and TABLE_NAME='{self.table}')
                )order by b.table_id
                ) y
                group by y.SVR_IP,y.DATABASE_NAME,y.TABLE_TYPE
                order by y.SVR_IP,y.DATABASE_NAME asc,TABLE_NAME desc
            '''

            columns, result = self.ob_connector.execute_sql_return_columns_and_data(query_data)
            if result.count == 0:
                self._log_error("dataSize is None")
                return
            self._log_info(f"data size {result}")
            self.__report(query_data, columns, result)
            return True

        except Exception as e:
            self._log_error(f"getTableInfo execute Exception: {str(e).strip()}")

    def __get_table_info_v3(self):
        try:
            tenant_data = self.ob_connector.execute_sql_return_cursor_dictionary(f"select tenant_id from oceanbase.__all_tenant where tenant_name='{self.tenant_name}'")
            if tenant_data.rowcount == 0:
                self._log_error("tenant is None")
                return
            self.tenant_id = tenant_data.fetchall()[0].get("tenant_id")
            database_data = self.ob_connector.execute_sql_return_cursor_dictionary(f"select tenant_id,database_id,database_name from oceanbase.gv$database where tenant_name = '{self.tenant_name}' and database_name = '{self.database}' ")
            if database_data.rowcount == 0:
                self._log_error("database is None")
                return
            self.database_id = database_data.fetchall()[0].get("database_id")
            table_data = self.ob_connector.execute_sql_return_cursor_dictionary(f"select * from oceanbase.__all_virtual_table where table_name='{self.table}' and database_id='{self.database_id}' and tenant_id='{self.tenant_id}'")
            if table_data.rowcount == 0:
                self._log_error("table is None")
                return
            self.table_id = table_data.fetchall()[0].get("table_id")
            query_count = f'''select /*+read_consistency(weak) */ 
                    m.zone, 
                    m.svr_ip,
                    t.table_name,
                    m.role,
                    ROUND(m.data_size / 1024 / 1024, 2) AS "DATA_SIZE(M)",
                    ROUND(m.required_size / 1024 / 1024, 2) AS "REQUIRED_SIZE(M)",
                    m.row_count as total_rows_count 
                    from oceanbase.__all_virtual_meta_table m, oceanbase.__all_virtual_table t 
                            where m.table_id = t.table_id and m.tenant_id = '{self.tenant_id}' and m.table_id = '{self.table_id}' and t.table_name = '{self.table}' order by total_rows_count desc limit 1'''
            columns, result = self.ob_connector.execute_sql_return_columns_and_data(query_count)
            if result.count == 0:
                self._log_error("dataSize and line count is None")
                return
            self._log_info(f"table count {result}")
            self.__report(query_count, columns, result)
            return True

        except Exception as e:
            self._log_error(f"getTableInfo execute Exception: {str(e).strip()}")

    def __report(self, sql, column_names, data):
        try:
            table_data = [list(row) for row in data]
            formatted_table = tabulate(table_data, headers=column_names, tablefmt="grid")
            with open(self.file_name, 'a', encoding='utf-8') as f:
                f.write('\n\n' + 'obclient > ' + sql + '\n')
                f.write(formatted_table)
        except Exception as e:
            self._log_error(f"report sql result to file: {self.file_name} failed, error:{e} ")

    def __report_simple(self, sql, data):
        try:
            with open(self.file_name, 'a', encoding='utf-8') as f:
                f.write('\n\n' + 'obclient > ' + sql + '\n')
                f.write(data)
        except Exception as e:
            self._log_error(f"report sql result to file: {self.file_name} failed, error:{e} ")

    def __extract_string(self, s):
        if '@' in s:
            at_index = s.index('@')
            if '#' in s:
                hash_index = s.index('#')
                if hash_index > at_index:
                    return s[at_index + 1 : hash_index]
                else:
                    return s[at_index + 1 :]
            else:
                return s[at_index + 1 :]
        else:
            return s

    def __extract_table_name(self, full_name):
        if '`' in full_name:
            self._log_verbose(f"'`' in full_name, clean it: {full_name}")
            full_name = full_name.replace('`', '')
        parts = full_name.split('.')
        if len(parts) > 1:
            return parts[-1].strip()
        else:
            return full_name.strip()

    def __print_result(self):
        self.end_time = time.time()
        elapsed_time = self.end_time - self.start_time
        headers = ["Status", "Result Details", "Time"]
        rows = [["Completed", self.file_name, f"{elapsed_time:.2f} s"]]
        # Use BaseHandler template method for summary table generation
        self._generate_summary_table(headers, rows, "Analyze SQL Summary")
        return
