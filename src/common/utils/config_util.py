#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: config_util.py
@desc: Configuration utility functions (extracted from tool.py)
"""

import string
import random


class ConfigUtil(object):

    @staticmethod
    def get_value_from_dict(conf, key, default=None, transform_func=None):
        try:
            # 不要使用 conf.get(key, default)来替换，这里还有类型转换的需求
            value = conf[key]
            return transform_func(value) if value is not None and transform_func else value
        except:
            return default

    @staticmethod
    def get_list_from_dict(conf, key, transform_func=None):
        try:
            return_list = conf[key]
            if transform_func:
                return [transform_func(value) for value in return_list]
            else:
                return return_list
        except:
            return []

    @staticmethod
    def get_random_pwd_by_total_length(pwd_length=10):
        char = string.ascii_letters + string.digits
        pwd = ""
        for i in range(pwd_length):
            pwd = pwd + random.choice(char)
        return pwd

    @staticmethod
    def get_random_pwd_by_rule(lowercase_length=2, uppercase_length=2, digits_length=2, punctuation_length=2):
        pwd = ""
        for i in range(lowercase_length):
            pwd += random.choice(string.ascii_lowercase)
        for i in range(uppercase_length):
            pwd += random.choice(string.ascii_uppercase)
        for i in range(digits_length):
            pwd += random.choice(string.digits)
        for i in range(punctuation_length):
            pwd += random.choice('(._+@#%)')
        pwd_list = list(pwd)
        random.shuffle(pwd_list)
        return ''.join(pwd_list)

    @staticmethod
    def passwd_format(passwd):
        return "'{}'".format(passwd.replace("'", "'\"'\"'"))
