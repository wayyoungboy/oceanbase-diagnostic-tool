#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: stat_processor.py
@desc: Statistics processing mixin for plan monitor handler
"""

import time


class StatProcessorMixin:
    """Mixin providing statistics processing methods."""

    def init_monitor_stat(self):
        sql = "select ID,NAME,TYPE from " + ("SYS." if self.tenant_mode == "oracle" else "oceanbase.") + "v$sql_monitor_statname order by ID"
        data = self.sys_connector.execute_sql(sql)
        for item in data:
            self.STAT_NAME[item[0]] = {"type": item[2], "name": item[1]}
        self._log_verbose("init sql plan monitor stat complete")

    def otherstat_detail_explain_item(self, item, n, v):
        try:
            if 0 == item[n]:
                val = ""
            elif self.STAT_NAME[item[n]]["type"] <= 1:
                val = str(item[v])
            elif self.STAT_NAME[item[n]]["type"] == 2:
                val = "%0.3fMB" % (item[n + 1] / 1024.0 / 1024)
            elif self.STAT_NAME[item[n]]["type"] == 3:
                val = "%s.%06d" % (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item[v] / 1000000)), item[v] - (item[v] / 1000000) * 1000000)
            else:
                val = str(item[v])
        except Exception as e:
            val = str(item[v])
        return "" if item[n] == 0 else self.STAT_NAME[item[n]]["name"] + "(" + val + ");<br/>"

    def otherstat_agg_explain_item(self, item, n, v):
        try:
            if 0 == item[n]:
                val = None
            elif self.STAT_NAME[item[n]]["type"] <= 1:
                val = str(item[v])
            elif self.STAT_NAME[item[n]]["type"] == 2:
                val = "%0.3fMB" % (float(item[v]) / 1024.0 / 1024)
            else:
                val = None
        except Exception as e:
            val = str(item[v])
        return "" if val is None else self.STAT_NAME[item[n]]["name"] + "(" + val + ");<br/>"

    def detail_otherstat_explain(self, item):
        otherstat = ""
        for i in range(1, 7):
            otherstat += self.otherstat_detail_explain_item(item, f"OTHERSTAT_{i}_ID", f"OTHERSTAT_{i}_VALUE")
        return otherstat

    def dfo_otherstat_explain(self, item):
        otherstat = ""
        for i in range(1, 7):
            otherstat += self.otherstat_agg_explain_item(item, f"OTHERSTAT_{i}_ID", f"SUM_STAT_{i}")
        return otherstat
