#!/usr/bin/env python
# -*- coding: UTF-8 -*
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
@time: 2023/9/26
@file: check_report.py
@desc:
"""

# report module is used to comprehensive system report generated by a single inspection and summarize it through the
# replies of task execution. When report summarizes information, it will be based on the content of the task. The
# first level is task_name. If all tasks are passed, it will be marked as 'pass'. If any task is not passed,
# it will generate separate reports for each step at the second level. The dimension of the second level is step,
# and generally, only the steps with exceptions will be summarized, but it can also handle them as needed.
from prettytable import PrettyTable
import datetime
import os
import yaml
import xmltodict
import json
from io import open

from handler.checker.check_exception import CheckException
from telemetry.telemetry import telemetry


class CheckReport:
    def __init__(self, context, report_target="observer", export_report_path="./check_report/", export_report_type="table"):
        self.context = context
        self.stdio = context.stdio
        self.tasks = []
        self.export_report_path = export_report_path
        try:
            if not os.path.exists(export_report_path):
                os.makedirs(export_report_path)
        except Exception as e:
            self.stdio.error("init check_report {0}".format(e))
            raise CheckrReportException("int check_report {0}".format(e))
        self.export_report_type = export_report_type

        now = datetime.datetime.now()
        date_format = now.strftime("%Y-%m-%d-%H-%M-%S")

        file_name = "/obdiag_check_report_{0}_".format(report_target) + date_format
        self.report_target = report_target

        report_path = self.export_report_path + file_name
        self.report_path = report_path
        self.stdio.verbose("export report to {0}".format(report_path))

    def add_task_report(self, task_report):
        self.tasks.append(task_report)

    def export_report(self):
        self.stdio.verbose("export report to {0}.{1}, export type is {1}".format(self.report_path, self.export_report_type))
        try:
            if self.export_report_type == "table":
                self.export_report_table()
            elif self.export_report_type == "json":
                self.export_report_json()
            elif self.export_report_type == "xml":
                self.export_report_xml()
            elif self.export_report_type == "yaml":
                self.export_report_yaml()
            else:
                raise CheckrReportException("export_report_type: {0} is not support".format(self.export_report_type))
            self.export_report_path = self.export_report_path + "." + self.export_report_type
        except Exception as e:
            self.stdio.error("export_report Exception : {0}".format(e))
            raise CheckrReportException(e)

    def get_report_path(self):
        return self.report_path + "." + self.export_report_type

    def export_report_xml(self):
        allMap = self.report_tobeMap()
        with open(self.report_path + ".xml", 'w', encoding="utf8") as f:
            allreport = {}
            allreport["report"] = allMap
            json_str = json.dumps(allreport)
            xml_str = xmltodict.unparse(json.loads(json_str))
            f.write(xml_str)
            f.close()

    def export_report_yaml(self):
        allMap = self.report_tobeMap()
        with open(self.report_path + ".yaml", 'w', encoding="utf8") as f:
            yaml.dump(allMap, f)

    def export_report_json(self):
        allMap = self.report_tobeMap()
        self.stdio.verbose("export_report_json allMap: {0}".format(allMap))
        with open(self.report_path + ".json", 'w', encoding="utf8") as f:
            # for python2 and python3
            try:
                json.dump(allMap, f, ensure_ascii=False)
            except:
                f.write(unicode(json.dumps(allMap, ensure_ascii=False)))

    def report_tobeMap(self):
        failMap = {}
        criticalMap = {}
        warningMap = {}
        allInfoMap = {}
        allMap = {}
        for task in self.tasks:
            if len(task.all_fail()) != 0:
                failMap[task.name] = task.all_fail()
            if len(task.all_critical()) != 0:
                criticalMap[task.name] = task.all_critical()
            if len(task.all_warning()) != 0:
                warningMap[task.name] = task.all_warning()
            if len(task.all()) != 0:
                allInfoMap[task.name] = task.all()

        allMap["fail"] = failMap
        allMap["critical"] = criticalMap
        allMap["warning"] = warningMap
        allMap["all"] = allInfoMap
        telemetry.push_check_info(self.report_target, {"fail_cases": list(failMap), "critical_cases": list(criticalMap), "warning_cases": list(warningMap)})
        return allMap

    def export_report_table(self):
        try:
            report_fail_tb = PrettyTable(["task", "task_report"])
            report_fail_tb.align["task_report"] = "l"
            report_fail_tb.title = "fail-tasks-report"

            report_critical_tb = PrettyTable(["task", "task_report"])
            report_critical_tb.align["task_report"] = "l"
            report_critical_tb.title = "critical-tasks-report"

            report_warning_tb = PrettyTable(["task", "task_report"])
            report_warning_tb.align["task_report"] = "l"
            report_warning_tb.title = "warning-tasks-report"

            report_all_tb = PrettyTable(["task", "task_report"])
            report_all_tb.align["task_report"] = "l"
            report_all_tb.title = "all-tasks-report"
            self.stdio.verbose("export report start")
            failMap = []
            criticalMap = []
            warningMap = []

            for task in self.tasks:
                if len(task.all_fail()) != 0:
                    report_fail_tb.add_row([task.name, '\n'.join(task.all_fail())])
                    failMap.append(task.name)
                if len(task.all_critical()) != 0:
                    report_critical_tb.add_row([task.name, '\n'.join(task.all_critical())])
                    criticalMap.append(task.name)
                if len(task.all_warning()) != 0:
                    report_warning_tb.add_row([task.name, '\n'.join(task.all_warning())])
                    warningMap.append(task.name)
                if len(task.all()) != 0:
                    report_all_tb.add_row([task.name, '\n'.join(task.all())])
                if len(task.all_fail()) == 0 and len(task.all_critical()) == 0 and len(task.all_warning()) == 0:
                    report_all_tb.add_row([task.name, "all pass"])
            telemetry.push_check_info(self.report_target, {"fail_cases": list(set(failMap)), "critical_cases": list(set(criticalMap)), "warning_cases": list(set(warningMap))})

            fp = open(self.report_path + ".table", 'a+', encoding="utf8")

            if len(report_fail_tb._rows) != 0:
                self.stdio.verbose(report_fail_tb)
                fp.write(report_fail_tb.get_string() + "\n")
            if len(report_critical_tb._rows) != 0:
                self.stdio.verbose(report_critical_tb)
                fp.write(report_critical_tb.get_string() + "\n")
            if len(report_warning_tb._rows) != 0:
                self.stdio.verbose(report_warning_tb)
                fp.write(report_warning_tb.get_string() + "\n")
            if len(report_all_tb._rows) != 0:
                self.stdio.verbose(report_all_tb)
                fp.write(report_all_tb.get_string() + "\n")
            fp.close()
            self.stdio.verbose("export report end")
        except Exception as e:
            raise CheckrReportException("export report {0}".format(e))


class TaskReport:
    def __init__(self, context, task_name, level="normal"):
        self.context = context
        self.stdio = context.stdio
        self.steps = []
        self.name = task_name
        self.level = level
        self.normal = []
        # "warning" usually indicates a non-critical issue;
        # "critical" indicates a serious error that is triggered;
        # "fail" is triggered only when an execution fails.
        self.warning = []

        self.critical = []

        self.fail = []

    def add(self, info, level="normal"):
        self.stdio.verbose("add task_report {0} ,{1}".format(info, level))
        if level == "normal":
            self.add_normal(info)
        elif level == "warning":
            self.add_warning(info)
        elif level == "critical":
            self.add_critical(info)
        elif level == "fail":
            self.add_fail(info)
        else:
            self.stdio.warn("report level is not support: " + str(level))
            self.add_normal(info)

    def add_normal(self, normal):
        self.normal.append("[normal] " + str(normal))
        self.normal = list(set(self.normal))

    def add_warning(self, tip):
        self.warning.append("[warning] " + str(tip))
        self.warning = list(set(self.warning))

    def add_critical(self, critical):
        self.critical.append("[critical] " + str(critical))
        self.critical = list(set(self.critical))

    def add_fail(self, fail):
        self.fail.append("[fail] " + str(fail))
        self.fail = list(set(self.fail))

    def all(self):
        list = self.fail + self.critical + self.warning + self.normal
        return list

    def all_fail(self):
        return self.fail

    def all_critical(self):
        return self.critical

    def all_warning(self):
        return self.warning

    def all_normal(self):
        return self.normal


class CheckrReportException(CheckException):
    def __init__(self, msg=None, obj=None):
        super(CheckrReportException, self).__init__(msg, obj)
