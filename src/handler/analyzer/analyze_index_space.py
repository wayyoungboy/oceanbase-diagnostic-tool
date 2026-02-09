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
@time: 2024/8/19
@file: analyze_index_space.py
@desc:
"""


from src.common.base_handler import BaseHandler

# Removed PrettyTable import - now using BaseHandler._generate_summary_table
from src.common.tool import StringUtils, Util
from src.common.ob_connector import OBConnector
from src.common.command import get_observer_version
from src.common.result_type import ObdiagResult


def translate_byte(B):
    if B < 0:
        B = -B
        return '-' + translate_byte(B)
    if B == 0:
        return '0B'
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    k = 1024
    i = 0
    while B >= k and i < len(units) - 1:
        B /= k
        i += 1
    return f"{B:.2f} {units[i]}"


class AnalyzeIndexSpaceHandler(BaseHandler):
    def _init(self, **kwargs):
        """Subclass initialization"""
        self.ob_version = get_observer_version(self.context)
        self.sys_connector = None
        self.tenant_id = None
        self.database_id = None
        self.table_id = None
        self.index_id = None
        self.column_names = []
        self.estimated_table_data = None
        self.result_map_list = []

    def init_option(self):
        ob_cluster = self.context.cluster_config
        self._log_verbose(f'cluster config: {StringUtils.mask_passwords(ob_cluster)}')
        self.ob_cluster = ob_cluster
        self.sys_connector = OBConnector(context=self.context, ip=ob_cluster.get("db_host"), port=ob_cluster.get("db_port"), username=ob_cluster.get("tenant_sys").get("user"), password=ob_cluster.get("tenant_sys").get("password"), timeout=100)
        tenant_name = self._get_option('tenant_name')
        database_name = self._get_option('database')
        table_name = self._get_option('table_name')
        index_name = self._get_option('index_name')
        column_names = self._get_option('column_names')
        # get tenant id (parameterized)
        tenant_data = self.sys_connector.execute_sql("select tenant_id from oceanbase.__all_tenant where tenant_name = %s", (tenant_name,))
        if len(tenant_data) == 0:
            raise Exception(f"can not find tenant id by tenant name: {tenant_name}. Please check the tenant name.")
        self.tenant_id = tenant_data[0][0]
        if self.tenant_id is None:
            raise Exception(f"can not find tenant id by tenant name: {tenant_name}. Please check the tenant name.")
        # get database id if database_name is provided (parameterized)
        if database_name is not None:
            database_id_data = self.sys_connector.execute_sql("select database_id from oceanbase.__all_virtual_database where database_name = %s and tenant_id = %s", (database_name, self.tenant_id))
            if len(database_id_data) == 0:
                raise Exception(f"can not find database id by database name: {database_name}. Please check the database name.")
            self.database_id = database_id_data[0][0]
            if self.database_id is None:
                raise Exception(f"can not find database id by database name: {database_name}. Please check the database name.")
            self._log_verbose(f"database_id is {self.database_id}")
        # get table id (parameterized)
        if database_name is not None:
            table_id_data = self.sys_connector.execute_sql("select table_id from oceanbase.__all_virtual_table where table_name = %s and tenant_id = %s and database_id = %s", (table_name, self.tenant_id, self.database_id))
        else:
            table_id_data = self.sys_connector.execute_sql("select table_id from oceanbase.__all_virtual_table where table_name = %s and tenant_id = %s", (table_name, self.tenant_id))
        if len(table_id_data) == 0:
            if database_name is not None:
                raise Exception(f"can not find table id by table name: {table_name} and database name: {database_name}. Please check the table name and database name.")
            else:
                raise Exception(f"can not find table id by table name: {table_name}. Please check the table name.")
        elif len(table_id_data) > 1:
            if database_name is not None:
                raise Exception(f"table name is {table_name}, tenant is {tenant_name}, database is {database_name}. but find more than one table id. Please check the table name and database name.")
            else:
                raise Exception(f"table name is {table_name}, tenant is {tenant_name}. but find more than one table id. Please add --database parameter to specify the database name.")
        self.table_id = table_id_data[0][0]
        if self.table_id is None:
            if database_name is not None:
                raise Exception(f"can not find table id by table name: {table_name} and database name: {database_name}. Please check the table name and database name.")
            else:
                raise Exception(f"can not find table id by table name: {table_name}. Please check the table name.")
        # get index id (parameterized)
        if index_name is not None:
            like_pattern = f"%{index_name}%"
            index_id_data = self.sys_connector.execute_sql("select table_id from oceanbase.__all_virtual_table where table_name like %s and data_table_id = %s and tenant_id = %s", (like_pattern, self.table_id, self.tenant_id))
            if len(index_id_data) == 0:
                raise Exception(f"can not find index id by index name: {index_name}. Please check the index name.")
            self.index_id = index_id_data[0][0]
            if self.index_id is None:
                raise Exception(f"can not find index id by index name: {index_name}. Please check the index name.")
        # get column names
        if column_names is not None:
            self.column_names = column_names.split(',')
            if len(self.column_names) == 0:
                raise Exception(f"--column_names parameter format is incorrect: {column_names}.")
        return True

    def handle(self) -> ObdiagResult:
        """Main handle logic"""
        self._validate_initialized()

        try:
            self.init_option()
        except Exception as e:
            self._log_error(f"init option failed: {str(e)}")
            return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data=f"init option failed: {str(e)}")
        # check ob version, this feature only supports OceanBase 4.x
        if not StringUtils.compare_versions_greater(self.ob_version, "4.0.0.0"):
            self._log_error(f"analyze index_space only supports OceanBase 4.x and above. Current version: {self.ob_version}")
            return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data=f"analyze index_space only supports OceanBase 4.x and above. Current version: {self.ob_version}")
        try:
            # evaluate the space size of the table where the index is located
            self.stdio.start_loading('start query estimated_table_data_size, please wait some minutes...')
            sql = f"select svr_ip, svr_port, sum(original_size) as estimated_table_size from oceanbase.__all_virtual_tablet_sstable_macro_info where tablet_id in (select tablet_id from oceanbase.__all_virtual_tablet_to_table_history where table_id = {self.table_id}) and (svr_ip, svr_port) in (select svr_ip, svr_port from oceanbase.__all_virtual_ls_meta_table where role = 1) group by svr_ip, svr_port;"
            self._log_verbose(f"execute_sql is {sql}")
            self.estimated_table_data = self.sys_connector.execute_sql_return_cursor_dictionary(sql).fetchall()
            self.stdio.stop_loading('succeed')
            if len(self.estimated_table_data) == 0:
                raise Exception(f"can not find estimated_table_data on __all_virtual_tablet_sstable_macro_info by table id: {self.table_id}. Please wait major or manually major'")
            # get the sum of all column lengths
            sql = f"select table_id, sum(data_length) as all_columns_length from oceanbase.__all_virtual_column_history where tenant_id = '{self.tenant_id}' and table_id = '{self.table_id}';"
            self._log_verbose(f"execute_sql is {sql}")
            self.main_table_sum_of_data_length = int(self.sys_connector.execute_sql_return_cursor_dictionary(sql).fetchall()[0]["all_columns_length"])
            # get the sum of column lengths included in the index
            if self.index_id is not None:
                sql = f"select table_id, sum(data_length) as index_columns_length from oceanbase.__all_virtual_column_history where tenant_id = '{self.tenant_id}' and table_id = '{self.index_id}';"
                self._log_verbose(f"execute_sql is {sql}")
                self.index_table_sum_of_data_length = int(self.sys_connector.execute_sql_return_cursor_dictionary(sql).fetchall()[0]["index_columns_length"])
            elif len(self.column_names) != 0:
                # Use parameterized query for column names
                placeholders = ','.join(['%s'] * len(self.column_names))
                sql = f"select table_id, sum(data_length) as columns_length from oceanbase.__all_virtual_column_history where tenant_id = %s and table_id = %s and column_name in ({placeholders})"
                params = tuple([self.tenant_id, self.table_id] + self.column_names)
                self._log_verbose(f"execute_sql is {sql} with params {params}")
                self.index_table_sum_of_data_length = int(self.sys_connector.execute_sql_return_cursor_dictionary(sql, params).fetchall()[0]["columns_length"])
            else:
                raise Exception("please specify an index or column.")

            # estimate the final space size
            estimated_index_data = []
            for node_table_estimated_size in self.estimated_table_data:
                node_estimated_index_data = {"svr_ip": node_table_estimated_size["svr_ip"], "svr_port": node_table_estimated_size["svr_port"]}
                estimiated_index_size = int(self.index_table_sum_of_data_length / self.main_table_sum_of_data_length * int(node_table_estimated_size["estimated_table_size"]))
                if self.ob_version == "4.2.3.0" or StringUtils.compare_versions_greater(self.ob_version, "4.2.3.0"):
                    self._log_verbose("magnification is 1.5")
                    target_server_estimated_size = int(estimiated_index_size * 15 / 10)
                else:
                    self._log_verbose("magnification is 5.5")
                    target_server_estimated_size = int(estimiated_index_size * 55 / 10)
                node_estimated_index_data["estimiated_index_size"] = target_server_estimated_size
                estimated_index_data.append(node_estimated_index_data)
            for node_estimated_index_data in estimated_index_data:
                target_server_ip = node_estimated_index_data["svr_ip"]
                target_server_port = node_estimated_index_data["svr_port"]
                target_server_estimated_index_size = int(node_estimated_index_data["estimiated_index_size"])
                # get target_server_total_size and target_server_used_size
                target_server_data = self.sys_connector.execute_sql_return_cursor_dictionary(f"select total_size, used_size from oceanbase.__all_virtual_disk_stat where svr_ip = '{target_server_ip}' and svr_port = {target_server_port};").fetchall()
                target_server_total_size = int(target_server_data[0]["total_size"])
                target_server_used_size = int(target_server_data[0]["used_size"])
                # get data_disk_usage_limit_percentage
                sql = f"SELECT VALUE FROM oceanbase.GV$OB_PARAMETERS WHERE SVR_IP='{target_server_ip}' and SVR_PORT='{target_server_port}' and NAME LIKE  \"data_disk_usage_limit_percentage\""
                self._log_verbose(f"execute_sql is {sql}")
                data_disk_usage_limit_percentage = int(self.sys_connector.execute_sql_return_cursor_dictionary(sql).fetchall()[0]["VALUE"])
                # data_disk_usage_limit_percentage is a Cluster level configuration items
                available_disk_space = int(target_server_total_size / 100 * data_disk_usage_limit_percentage - target_server_used_size)
                node_result_map = {}
                node_result_map["ip"] = target_server_ip
                node_result_map["port"] = target_server_port
                node_result_map["estimated_index_space"] = translate_byte(target_server_estimated_index_size)
                node_result_map["available_disk_space"] = translate_byte(available_disk_space)
                self.result_map_list.append(node_result_map)
            self.export_report_table()
            self._log_verbose("end analyze index space")
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data=self.execute())
        except Exception as e:
            self._log_error(f"analyze index space error: {e}")
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data=f"analyze index space error: {e}")

    def execute(self):
        result_map = {}
        result_map["result"] = self.result_map_list
        return result_map

    def export_report_table(self):
        try:
            headers = ["ip", "port", "estimated_index_space", "available_disk_space"]
            rows = []
            for result in self.result_map_list:
                rows.append([result["ip"], result["port"], result["estimated_index_space"], result["available_disk_space"]])
            # Use BaseHandler template method for summary table generation
            self._generate_summary_table(headers, rows, "estimated-index-space-report")
        except Exception as e:
            raise Exception(f"export report {e}")
