#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: graph_renderer.py
@desc: Graph data rendering mixin for plan monitor handler (JavaScript timeline graphs)
"""

from decimal import Decimal


class GraphRendererMixin:
    """Mixin providing graph data rendering methods (JavaScript timeline charts)."""

    def report_detail_graph_data(self, ident, cursor, title=''):
        data = "<script> var %s = [" % ident
        for item in cursor:
            start = 0 if None == item['FIRST_CHANGE_TS'] else item['FIRST_CHANGE_TS']
            end = 0 if None == item['LAST_CHANGE_TS'] else item['LAST_CHANGE_TS']
            rows = 0 if None == item['OUTPUT_ROWS'] else item['OUTPUT_ROWS']
            otherstat = self.detail_otherstat_explain(item)
            data = data + "{start:%f, end:%f, diff:%f, opid:%s, op:'%s',tid:'%s',rows:%d, tag:'op', depth:%d, rescan:%d, svr_ip:'%s', otherstat:'%s'}," % (
                start, end, end - start, item['PLAN_LINE_ID'], item['PLAN_OPERATION'],
                item['PROCESS_NAME'], rows, item['PLAN_DEPTH'], item['RESCAN_TIMES'],
                item['SVR_IP'], otherstat,
            )
        data = data + "{start:0}];</script>"
        data = data + "<p>%s</p><div class='bar' id='%s'></div>" % (title, ident)
        self._report(data)

    def report_detail_graph_data_obversion4(self, ident, cursor, title=''):
        data = "<script> var %s = [" % ident
        for item in cursor:
            start = 0 if None == item['FIRST_CHANGE_TS'] else item['FIRST_CHANGE_TS']
            end = 0 if None == item['LAST_CHANGE_TS'] else item['LAST_CHANGE_TS']
            rows = 0 if None == item['OUTPUT_ROWS'] else item['OUTPUT_ROWS']
            otherstat = self.detail_otherstat_explain(item)
            data = data + "{cpu:%f, io:%f, start:%f, end:%f, diff:%f, opid:%s, op:'%s',tid:'%s',rows:%d, tag:'op', depth:%d, rescan:%d, svr_ip:'%s', otherstat:'%s'}," % (
                item['MY_CPU_TIME'], item['MY_IO_TIME'], start, end, end - start,
                item['PLAN_LINE_ID'], item['PLAN_OPERATION'], item['PROCESS_NAME'],
                rows, item['PLAN_DEPTH'], item['RESCAN_TIMES'], item['SVR_IP'], otherstat,
            )
        data = data + "{start:0}];</script>"
        data = data + "<p>%s</p><div class='bar' id='%s'></div>" % (title, ident)
        self._report(data)

    def report_dfo_agg_db_time_graph_data_obversion4(self, cursor, title=''):
        data = "<script> var db_time_serial = ["
        for item in cursor:
            start = Decimal('0.00001')
            end = item['MY_DB_TIME'] + start
            diff = end - start
            rows = item['TOTAL_OUTPUT_ROWS']
            op_id = item['PLAN_LINE_ID']
            op = item['PLAN_OPERATION']
            depth = item['PLAN_DEPTH']
            threads = item['THREAD_NUM']
            my_cpu_time = item['MY_CPU_TIME']
            my_io_time = item['MY_IO_TIME']
            otherstat = "my_db_time:%f, my_cpu_time:%f, my_io_time:%f" % (item['MY_DB_TIME'], item['MY_CPU_TIME'], item['MY_IO_TIME'])
            data = data + "{cpu:%f,io:%f,start:%f, end:%f, diff:%f, my_io_time:%f, my_cpu_time:%f, opid:%s, op:'%s', est_rows:0, rows:%d, tag:'db_time', tid: %d, depth:%d, otherstat:'%s'}," % (
                item['MY_CPU_TIME'], item['MY_IO_TIME'], start, end, diff,
                my_io_time, my_cpu_time, op_id, op, rows, threads, depth, otherstat,
            )
        data = data + "{start:0}];"
        data = data + "</script><p>%s</p><div class='bar' id='db_time_serial'></div>" % (title)
        self._report(data)

    def report_dfo_agg_graph_data(self, cursor, title=''):
        data = "<script> var agg_serial = ["
        for item in cursor:
            start = 0 if None == item['MIN_FIRST_CHANGE_TS'] else item['MIN_FIRST_CHANGE_TS']
            end = 0 if None == item['MAX_LAST_CHANGE_TS'] else item['MAX_LAST_CHANGE_TS']
            rows = 0 if None == item['TOTAL_OUTPUT_ROWS'] else item['TOTAL_OUTPUT_ROWS']
            est_rows = 0 if None == item['EST_ROWS'] else item['EST_ROWS']
            otherstat = self.dfo_otherstat_explain(item)
            data = data + "{start:%f, end:%f, diff:%f, opid:%s, op:'%s',tid:'%s',rows:%d,est_rows:%d, tag:'dfo', depth:%d, otherstat:'%s'}," % (
                start, end, end - start, item['PLAN_LINE_ID'], item['PLAN_OPERATION'],
                item['PARALLEL'], rows, est_rows, item['PLAN_DEPTH'], otherstat,
            )
        data = data + "{start:0}];"
        data = data + "</script><p>%s</p><div class='bar' id='agg_serial'></div>" % (title)
        self._report(data)

    def report_dfo_agg_graph_data_obversion4(self, cursor, title=''):
        data = "<script> var agg_serial = ["
        for item in cursor:
            start = 0 if None == item['MIN_FIRST_CHANGE_TS'] else item['MIN_FIRST_CHANGE_TS']
            end = 0 if None == item['MAX_LAST_CHANGE_TS'] else item['MAX_LAST_CHANGE_TS']
            rows = 0 if None == item['TOTAL_OUTPUT_ROWS'] else item['TOTAL_OUTPUT_ROWS']
            skewness = 0 if None == item['SKEWNESS'] else item['SKEWNESS']
            est_rows = 0 if None == item['EST_ROWS'] else item['EST_ROWS']
            otherstat = self.dfo_otherstat_explain(item)
            data = data + "{cpu:%f,io:%f,start:%f, end:%f, diff:%f, opid:%s, op:'%s',tid:'%s',rows:%d,est_rows:%d, tag:'dfo', depth:%d, otherstat:'%s', skewness:%.2f}," % (
                item['MY_CPU_TIME'], item['MY_IO_TIME'], start, end, end - start,
                item['PLAN_LINE_ID'], item['PLAN_OPERATION'], item['PARALLEL'],
                rows, est_rows, item['PLAN_DEPTH'], otherstat, skewness,
            )
        data = data + "{start:0}];"
        data = data + "</script><p>%s</p><div class='bar' id='agg_serial'></div>" % (title)
        self._report(data)

    def report_dfo_sched_agg_graph_data(self, cursor, title=''):
        data = "<script> var agg_sched_serial = ["
        for item in cursor:
            start = 0 if None == item['MIN_FIRST_REFRESH_TS'] else item['MIN_FIRST_REFRESH_TS']
            end = 0 if None == item['MAX_LAST_REFRESH_TS'] else item['MAX_LAST_REFRESH_TS']
            rows = 0 if None == item['TOTAL_OUTPUT_ROWS'] else item['TOTAL_OUTPUT_ROWS']
            est_rows = 0 if None == item['EST_ROWS'] else item['EST_ROWS']
            otherstat = self.dfo_otherstat_explain(item)
            data = data + "{start:%f, end:%f, diff:%f, opid:%s, op:'%s',tid:'%s',rows:%d,est_rows:%d, tag:'dfo', depth:%d, otherstat:'%s'}," % (
                start, end, end - start, item['PLAN_LINE_ID'], item['PLAN_OPERATION'],
                item['PARALLEL'], rows, est_rows, item['PLAN_DEPTH'], otherstat,
            )
        data = data + "{start:0}];"
        data = data + "</script><p>%s</p><div class='bar' id='agg_sched_serial'></div>" % (title)
        self._report(data)

    def report_dfo_sched_agg_graph_data_obversion4(self, cursor, title=''):
        data = "<script> var agg_sched_serial = ["
        for item in cursor:
            start = 0 if None == item['MIN_FIRST_REFRESH_TS'] else item['MIN_FIRST_REFRESH_TS']
            end = 0 if None == item['MAX_LAST_REFRESH_TS'] else item['MAX_LAST_REFRESH_TS']
            rows = 0 if None == item['TOTAL_OUTPUT_ROWS'] else item['TOTAL_OUTPUT_ROWS']
            skewness = 0 if None == item['SKEWNESS'] else item['SKEWNESS']
            est_rows = 0 if None == item['EST_ROWS'] else item['EST_ROWS']
            otherstat = self.dfo_otherstat_explain(item)
            data = data + "{cpu:%f,io:%f,start:%f, end:%f, diff:%f, opid:%s, op:'%s',tid:'%s',rows:%d,est_rows:%d, tag:'dfo', depth:%d, otherstat:'%s', skewness:%.2f}," % (
                item['MY_CPU_TIME'], item['MY_IO_TIME'], start, end, end - start,
                item['PLAN_LINE_ID'], item['PLAN_OPERATION'], item['PARALLEL'],
                rows, est_rows, item['PLAN_DEPTH'], otherstat, skewness,
            )
        data = data + "{start:0}];"
        data = data + "</script><p>%s</p><div class='bar' id='agg_sched_serial'></div>" % (title)
        self._report(data)

    def report_svr_agg_graph_data(self, ident, cursor, title=''):
        data = "<script> var %s = [" % ident
        for item in cursor:
            start = 0 if None == item['MIN_FIRST_CHANGE_TS'] else item['MIN_FIRST_CHANGE_TS']
            end = 0 if None == item['MAX_LAST_CHANGE_TS'] else item['MAX_LAST_CHANGE_TS']
            rows = 0 if None == item['TOTAL_OUTPUT_ROWS'] else item['TOTAL_OUTPUT_ROWS']
            data = data + "{start:%f, end:%f, diff:%f, opid:%s, op:'%s',tid:'%s',svr:'%s',rows:%d, tag:'sqc', depth:%d}," % (
                start, end, end - start, item['PLAN_LINE_ID'], item['PLAN_OPERATION'],
                item['PARALLEL'], item['SVR_IP'] + ':' + str(item['SVR_PORT']),
                rows, item['PLAN_DEPTH'],
            )
        data = data + "{start:0}];</script>"
        data = data + "<p>%s</p><div class='bar' id='%s'></div>" % (title, ident)
        self._log_verbose(f"report SQL_PLAN_MONITOR SQC operator priority start, DATA: {data}")
        self._report(data)

    def report_svr_agg_graph_data_obversion4(self, ident, cursor, title=''):
        data = "<script> var %s = [" % ident
        for item in cursor:
            start = 0 if None == item['MIN_FIRST_CHANGE_TS'] else item['MIN_FIRST_CHANGE_TS']
            end = 0 if None == item['MAX_LAST_CHANGE_TS'] else item['MAX_LAST_CHANGE_TS']
            rows = 0 if None == item['TOTAL_OUTPUT_ROWS'] else item['TOTAL_OUTPUT_ROWS']
            skewness = 0 if None == item['SKEWNESS'] else item['SKEWNESS']
            data = data + "{cpu:%f,io:%f,start:%f, end:%f, diff:%f, opid:%s, op:'%s',tid:'%s',svr:'%s',rows:%d, tag:'sqc', depth:%d, skewness:%.2f}," % (
                item['MY_CPU_TIME'], item['MY_IO_TIME'], start, end, end - start,
                item['PLAN_LINE_ID'], item['PLAN_OPERATION'], item['PARALLEL'],
                item['SVR_IP'] + ':' + str(item['SVR_PORT']), rows,
                item['PLAN_DEPTH'], skewness,
            )
        data = data + "{start:0}];</script>"
        data = data + "<p>%s</p><div class='bar' id='%s'></div>" % (title, ident)
        self._log_verbose(f"report SQL_PLAN_MONITOR SQC operator priority start, DATA: {data}")
        self._report(data)
