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
@time: 2022/6/20
@file: ob_connector.py
@desc:
"""
import re

# Note: Replaced PrettyTable with tabulate for consistency
from tabulate import tabulate
import pymysql as mysql


class TableResult:
    """
    Wrapper class to replace PrettyTable, providing compatible interface.
    Uses tabulate internally for table generation.
    """
    def __init__(self, field_names, rows):
        self.field_names = field_names
        self.rows = rows
        self._align = 'l'  # Default alignment
    
    @property
    def align(self):
        """Get alignment setting"""
        return self._align
    
    @align.setter
    def align(self, value):
        """Set alignment (for compatibility, stored but not used in HTML output)"""
        if isinstance(value, dict):
            self._align = value
        else:
            # Set all fields to the same alignment
            self._align = value
    
    def get_html_string(self):
        """Generate HTML table string using tabulate"""
        # Convert to HTML table format
        html_table = tabulate(self.rows, headers=self.field_names, tablefmt="html", showindex=False)
        return html_table
    
    def __str__(self):
        """Generate plain text table string"""
        return tabulate(self.rows, headers=self.field_names, tablefmt="grid", showindex=False)


class OBConnector(object):
    # sql be upper
    filter_sql_list = []
    filter_sql_re_list = [r'\bDELETE\b', r'CREATE\s+(TABLE|INDEX|SEQUENCE|VIEW|TRIGGER)']

    def __init__(
        self,
        context,
        ip,
        port,
        username,
        password=None,
        database=None,
        timeout=30,
    ):
        self.context = context
        self.ip = str(ip)
        self.port = int(port)
        self.username = str(username)
        self.password = str(password)
        self.timeout = timeout
        self.conn = None
        self.stdio = context.stdio
        self.database = database
        self.init()

    def init(self):
        try:
            self._connect_db()
        except Exception as e:
            self.stdio.verbose(e)

    def __enter__(self):
        """Ensures the database connection is open upon entering the 'with' block."""
        self._connect_db()
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        """Automatically closes the database connection when exiting the 'with' block."""
        if self.conn:
            self.conn.close()

    def _connect_db(self):
        try:
            self.conn = mysql.connect(
                host=self.ip,
                port=self.port,
                user=self.username,
                passwd=self.password,
                db=self.database,
                connect_timeout=30,
            )
            self.stdio.verbose("connect databse ...")
        except mysql.Error as e:
            self.stdio.error("connect OB: {0}:{1} with user {2} failed, error:{3}".format(self.ip, self.port, self.username, e))
            return
        try:
            ob_trx_timeout = 3216672000000000
            self.execute_sql("SET SESSION ob_trx_timeout={0};".format(ob_trx_timeout))
        except Exception as e:
            self.stdio.warn("set ob_trx_timeout failed, error:{0}".format(e))
        try:
            ob_query_timeout = 3216672000000000
            self.execute_sql("SET SESSION ob_query_timeout={0};".format(ob_query_timeout))
        except Exception as e:
            self.stdio.warn("set ob_query_timeout failed, error:{0}".format(e))

    def execute_sql(self, sql, params=None):
        """
        Execute SQL query and return results.

        Args:
            sql: SQL query string. Use %s placeholders for parameterized queries.
            params: Optional tuple/list of parameters for parameterized queries.

        Returns:
            List of result tuples.
        """
        if self.conn is None:
            self._connect_db()
        else:
            self.conn.ping(reconnect=True)
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        ret = cursor.fetchall()
        cursor.close()
        return ret

    def execute_sql_return_columns_and_data(self, sql, params=None):
        """
        Executes an SQL query and returns column names and data.

        :param sql: The SQL statement to execute, using %s as a placeholder for parameters.
        :param parameters: A tuple or list of parameters to substitute into the SQL statement.
        :return: A tuple containing a list of column names and a list of rows (each a tuple).
        """
        if self.conn is None:
            self._connect_db()
        else:
            self.conn.ping(reconnect=True)

        with self.conn.cursor() as cursor:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)

            column_names = [col[0] for col in cursor.description]
            data = cursor.fetchall()
        return column_names, data

    def execute_sql_return_cursor_dictionary(self, sql, params=None):
        if self.conn is None:
            self._connect_db()
        else:
            self.conn.ping(reconnect=True)
        cursor = self.conn.cursor(mysql.cursors.DictCursor)
        cursor.execute(sql, params)
        return cursor

    def execute_sql_return_cursor(self, sql, params=None):
        if self.conn is None:
            self._connect_db()
        else:
            self.conn.ping(reconnect=True)
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        return cursor

    def execute_sql_pretty(self, sql, params=None):
        if self.conn is None:
            self._connect_db()
        else:
            self.conn.ping(reconnect=True)
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        # Replace from_db_cursor with manual fetching and TableResult wrapper
        field_names = [col[0] for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        cursor.close()
        return TableResult(field_names, rows)

    def execute_display_cursor(self, business_sql):
        if self.conn is None:
            self._connect_db()
        else:
            self.conn.ping(reconnect=True)
        cursor = self.conn.cursor()
        try:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            cursor.execute(business_sql)

            cursor.execute("select dbms_xplan.display_cursor(0, 'all')")
            # Replace from_db_cursor with manual fetching and TableResult wrapper
            field_names = [col[0] for col in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            plan_result = TableResult(field_names, rows)
            plan_result.align = 'l'
            cursor.close()
            return plan_result
        except Exception as e:
            pass
        finally:
            cursor.close()

    def execute_enable_opt_trace(self, suffix, business_sql):
        """
        Enables optimizer tracing using DBMS_XPLAN, executes EXPLAIN on the provided SQL,
        and then disables the optimizer trace.

        :param suffix: A string used to identify the current trace session.
        :param business_sql: The actual SQL statement to be explained.
        """
        if self.conn is None:
            self._connect_db()
        else:
            self.conn.ping(reconnect=True)
        cursor = self.conn.cursor()
        try:
            self.stdio.print("execute dbms_xplan.enable_opt_trace start ...")
            set_transaction = "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
            self.stdio.print(set_transaction)
            cursor.execute(set_transaction)

            enable_opt_trace = "call dbms_xplan.enable_opt_trace();"
            self.stdio.print(enable_opt_trace)
            cursor.execute(enable_opt_trace)

            set_opt_trace_parameter = "call dbms_xplan.set_opt_trace_parameter(identifier=>'{0}', `level`=>3);".format(suffix)
            self.stdio.print(set_opt_trace_parameter)
            cursor.execute(set_opt_trace_parameter)

            explain = "explain {0}".format(business_sql)
            self.stdio.print(explain)
            cursor.execute(explain)

            disable_opt_trace = "call dbms_xplan.disable_opt_trace();"
            self.stdio.print(disable_opt_trace)
            cursor.execute(disable_opt_trace)

            cursor.close()
            self.stdio.print("execute dbms_xplan.enable_opt_trace end")
        except Exception as e:
            error_code = e.args[0] if hasattr(e, 'args') and len(e.args) > 0 else None
            if error_code == 1049:
                self.stdio.exception(f"execution failed: call dbms_xplan.enable_opt_trace() not supported")
            else:
                self.stdio.exception(f"error occurred during execution: {e}")
        finally:
            # Safely close cursor if it was created
            if cursor:
                cursor.close()

    def callproc(self, procname, args=()):
        if self.conn is None:
            self._connect_db()
        else:
            self.conn.ping(reconnect=True)
        cursor = self.conn.cursor()
        cursor.callproc(procname, args)
        ret = cursor.fetchall()
        return ret

    def filter_sql(self, sql):
        sql = sql.strip().upper()
        for sql in self.filter_sql_list:
            raise Exception('sql is not safe ,not support. sql: {0}'.format(sql))
        for filter_sql in self.filter_sql_re_list:
            if re.match(filter_sql, sql):
                raise Exception('sql is not safe ,not support. sql: {0}'.format(sql))
