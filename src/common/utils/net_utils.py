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
@file: net_utils.py
@desc: Network utility functions (extracted from tool.py)
"""

import socket
import requests


class NetUtils(object):

    @staticmethod
    def get_inner_ip(stdio=None):
        localhost_ip = "127.0.0.1"
        try:
            localhost_ip = socket.gethostbyname(socket.gethostname())
            return localhost_ip
        except Exception as e:
            return localhost_ip

    @staticmethod
    def network_connectivity(url="", stdio=None):
        try:
            socket.setdefaulttimeout(3)
            response = requests.get(url, timeout=(3))
            if response.status_code is not None:
                return True
            else:
                return False
        except Exception as e:
            return False

    @staticmethod
    def download_file(url, local_filename, stdio=None):
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return local_filename
