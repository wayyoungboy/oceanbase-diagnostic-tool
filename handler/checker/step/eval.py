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
@time: 2024/9/30
@file: eval.py
@desc:
"""
from decimal import Decimal

from handler.checker.check_exception import StepExecuteFailException
from common.tool import StringUtils
from common.tool import Util
import math


class StepEvalHandler:
    def __init__(self, context, step, task_variable_dict):
        try:
            self.context = context
            self.stdio = context.stdio
            self.step = step
            self.task_variable_dict = task_variable_dict
            self.ob_cluster = self.context.cluster_config
        except Exception as e:
            self.stdio.error("StepEvalHandler init fail. Please check the OBCLUSTER conf. Exception : {0} .".format(e))
            raise Exception("StepEvalHandler init fail. Please check the OBCLUSTER conf. Exception : {0} .".format(e))

    def execute(self):
        try:
            if "eval" not in self.step:
                raise StepExecuteFailException("eval execute is not set")
            expression = StringUtils.build_str_on_expr_by_dict(self.step["eval"], self.task_variable_dict)
            self.stdio.verbose("eval execute: {0}".format(expression))
            result = Decimal(eval(expression, {"__builtins__": None}, {"math": math}))
            self.stdio.verbose("execute eval result:{0}".format(result))
            self.stdio.verbose("eval result:{0}".format(Util.convert_to_number(str(result))))
            if "result" in self.step and "set_value" in self.step["result"]:
                self.stdio.verbose("StepEvalHandler execute update task_variable_dict: {0} = {1}".format(self.step["result"]["set_value"], Util.convert_to_number(result)))
                self.task_variable_dict[self.step["result"]["set_value"]] = Util.convert_to_number(result)
        except Exception as e:
            self.stdio.error("StepEvalHandler execute Exception: {0}".format(e))
            raise StepExecuteFailException("StepEvalHandler execute Exception: {0}".format(e))

    def update_step_variable_dict(self):
        return self.task_variable_dict
