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
@file: time_utils.py
@desc: Time utility functions (extracted from tool.py)
"""

import datetime
import time
import re
from datetime import timedelta


class TimeUtils(object):

    @staticmethod
    def parse_time_sec(time_str):
        unit = time_str[-1]
        value = int(time_str[:-1])
        if unit == "s":
            value *= 1
        elif unit == "m":
            value *= 60
        elif unit == "h":
            value *= 3600
        elif unit == "d":
            value *= 3600 * 24
        else:
            raise Exception('%s parse time to second fialed:' % (time_str))
        return value

    @staticmethod
    def get_format_time(time_str, stdio=None):
        try:
            return datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            if stdio:
                stdio.exception('%s parse time fialed, error:\n%s, time format need to be %s' % (time_str, e, '%Y-%m-%d %H:%M:%S'))
            return None

    @staticmethod
    def sub_minutes(t, delta, stdio=None):
        try:
            return (t - datetime.timedelta(minutes=delta)).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            if stdio:
                stdio.exception('%s get time fialed, error:\n%s' % (t, e))
            return None

    @staticmethod
    def add_minutes(t, delta, stdio=None):
        try:
            return (t + datetime.timedelta(minutes=delta)).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            if stdio:
                stdio.exception('%s get time fialed, error:\n%s' % (t, e))
            return None

    @staticmethod
    def parse_time_from_to(from_time=None, to_time=None, stdio=None):
        format_from_time = None
        format_to_time = None
        sucess = False
        if from_time:
            format_from_time = TimeUtils.get_format_time(from_time, stdio)
            format_to_time = TimeUtils.get_format_time(to_time, stdio) if to_time else TimeUtils.add_minutes(format_from_time, 30)
        else:
            if to_time:
                format_to_time = TimeUtils.get_format_time(to_time, stdio)
                format_from_time = TimeUtils.sub_minutes(format_to_time, 30)
        if format_from_time and format_to_time:
            sucess = True
        return format_from_time, format_to_time, sucess

    @staticmethod
    def parse_time_since(since=None, stdio=None):
        now_time = datetime.datetime.now()
        format_to_time = (now_time + datetime.timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
        try:
            format_from_time = (now_time - datetime.timedelta(seconds=TimeUtils.parse_time_sec(since))).strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            if stdio:
                stdio.exception('%s parse time fialed, error:\n%s' % (since, e))
            format_from_time = TimeUtils.sub_minutes(format_to_time, 30)
        return format_from_time, format_to_time

    @staticmethod
    def get_current_us_timestamp(stdio=None):
        time_second = time.time()
        return int(time_second * 1000000)

    @staticmethod
    def parse_time_length_to_sec(time_length_str, stdio=None):
        unit = time_length_str[-1]
        if unit != "m" and unit != "h" and unit != "d":
            raise Exception("time length must be format 'n'<m|h|d>")
        value = int(time_length_str[:-1])
        if unit == "m":
            value *= 60
        elif unit == "h":
            value *= 3600
        elif unit == "d":
            value *= 3600 * 24
        else:
            raise Exception("time length must be format 'n'<m|h|d>")
        return int(value)

    @staticmethod
    def datetime_to_timestamp(datetime_str, stdio=None):
        # yyyy-mm-dd hh:mm:ss.uuuuus or yyyy-mm-dd hh:mm:ss
        try:
            if len(datetime_str) > 19:
                dt = datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S.%f')
            else:
                dt = datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            return int(dt.timestamp() * 1000000)
        except Exception as e:
            return 0

    @staticmethod
    def trans_datetime_utc_to_local(datetime_str, stdio=None):
        utct_date = datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")  # 2020-12-01 03:21:57
        local_date = utct_date + datetime.timedelta(hours=8)  # 加上时区
        local_date_srt = datetime.datetime.strftime(local_date, "%Y-%m-%d %H:%M:%S")  # 2020-12-01 11:21:57
        trans_res = datetime.datetime.strptime(local_date_srt, "%Y-%m-%d %H:%M:%S")
        return str(trans_res)

    @staticmethod
    def timestamp_to_filename_time(timestamp, stdio=None):
        second_timestamp = timestamp / 1000000
        time_obj = time.localtime(int(second_timestamp))
        filename_time_str = time.strftime('%Y%m%d%H%M%S', time_obj)
        return filename_time_str

    @staticmethod
    def parse_time_str(arg_time, stdio=None):
        format_time = ''
        try:
            format_time = datetime.datetime.strptime(arg_time, "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            raise ValueError("time option {0} must be formatted as {1}".format(arg_time, '"%Y-%m-%d %H:%M:%S"'))
        return format_time

    @staticmethod
    def filename_time_to_datetime(filename_time, stdio=None):
        """transform yyyymmddhhmmss to yyyy-mm-dd hh:mm:ss"""
        if filename_time != "":
            return "{0}-{1}-{2} {3}:{4}:{5}".format(filename_time[0:4], filename_time[4:6], filename_time[6:8], filename_time[8:10], filename_time[10:12], filename_time[12:14])
        else:
            return ""

    @staticmethod
    def extract_filename_time_from_log_name(log_name, stdio=None):
        """eg: xxx.20221226231617"""
        log_name_fields = log_name.split(".")
        if bytes.isdigit(log_name_fields[-1].encode("utf-8")) and len(log_name_fields[-1]) >= 14:
            return log_name_fields[-1]
        return ""

    @staticmethod
    def extract_time_from_log_file_text(log_text, stdio=None):
        # 因为 yyyy-mm-dd hh:mm:ss.000000 的格式已经占了27个字符，所以如果传进来的字符串包含时间信息，那长度一定大于27
        if len(log_text) > 27:
            if log_text.startswith("["):
                time_str = log_text[1 : log_text.find(']')]
            else:
                time_str = log_text[0 : log_text.find(',')]
            time_without_us = time_str[0 : time_str.find('.')]
            try:
                format_time = datetime.datetime.strptime(time_without_us, "%Y-%m-%d %H:%M:%S")
                format_time_str = time.strftime("%Y-%m-%d %H:%M:%S", format_time.timetuple())
            except Exception as e:
                format_time_str = ""
        else:
            format_time_str = ""
        if format_time_str == "":
            time_pattern = r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}'
            match = re.search(time_pattern, log_text)
            if match:
                format_time_str = match.group(0)
        return format_time_str

    @staticmethod
    def get_time_rounding(dt, step=0, rounding_level="s", stdio=None):
        """
        计算整分钟，整小时，整天的时间
        :param step: 往前或往后跳跃取整值，默认为0，即当前所在的时间，正数为往后，负数往前。
                    例如：
                    step = 0 时 2022-07-26 17:38:21.869993 取整秒后为 2022-07-26 17:38:21
                    step = 1 时 2022-07-26 17:38:21.869993 取整秒后为 2022-07-26 17:38:22
                    step = -1 时 2022-07-26 17:38:21.869993 取整秒后为 2022-07-26 17:38:20
        :param rounding_level: 字符串格式。
                    "s": 按秒取整；"min": 按分钟取整；"hour": 按小时取整；"days": 按天取整
        :return: 处理后的时间
        """
        if rounding_level == "days":
            td = timedelta(days=-step, seconds=dt.second, microseconds=dt.microsecond, milliseconds=0, minutes=dt.minute, hours=dt.hour, weeks=0)
            new_dt = dt - td
        elif rounding_level == "hour":
            td = timedelta(days=0, seconds=dt.second, microseconds=dt.microsecond, milliseconds=0, minutes=dt.minute, hours=-step, weeks=0)
            new_dt = dt - td
        elif rounding_level == "min":
            td = timedelta(days=0, seconds=dt.second, microseconds=dt.microsecond, milliseconds=0, minutes=-step, hours=0, weeks=0)
            new_dt = dt - td
        elif rounding_level == "s":
            td = timedelta(days=0, seconds=-step, microseconds=dt.microsecond, milliseconds=0, minutes=0, hours=0, weeks=0)
            new_dt = dt - td
        else:
            new_dt = dt
        return str(new_dt)

    @staticmethod
    def trans_time(size: int):
        """
        将时间单位转化为字符串
        :param size: 时间单位，单位为微秒
        :return: 转化后的字符串
        """
        if size < 0:
            return 'NO_END'
        mapping = [
            (86400000000, 'd'),
            (3600000000, 'h'),
            (60000000, 'm'),
            (1000000, 's'),
            (1000, 'ms'),
            (1, 'μs'),
        ]
        for unit, unit_str in mapping:
            if size >= unit:
                if unit == 1:
                    return '{} {}'.format(size, unit_str)
                else:
                    return '{:.3f} {}'.format(size / unit, unit_str)
        return '0'

    @staticmethod
    def str_2_timestamp(t, stdio=None):
        if isinstance(t, int):
            return t
        temp = datetime.datetime.strptime(t, '%Y-%m-%d %H:%M:%S.%f')
        return int(datetime.datetime.timestamp(temp) * 10**6)

    @staticmethod
    def parse_since(since_str, to_timestamp, stdio=None):
        """Parse 'since' time string relative to to_timestamp."""
        try:
            seconds = TimeUtils.parse_time_sec(since_str)
            return to_timestamp - (seconds * 1000000)  # Convert to microseconds
        except Exception as e:
            if stdio:
                stdio.warn(f"Failed to parse since time '{since_str}': {e}")
            return to_timestamp - (30 * 60 * 1000000)  # Default: 30 minutes

    @staticmethod
    def timestamp_to_str(timestamp, stdio=None):
        """Convert timestamp (microseconds) to datetime string."""
        try:
            second_timestamp = timestamp / 1000000
            dt = datetime.datetime.fromtimestamp(second_timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            if stdio:
                stdio.warn(f"Failed to convert timestamp {timestamp}: {e}")
            return ""
