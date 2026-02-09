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
@file: main.py
@desc:
"""

import sys
import os

# Setup sys.path for packaged environment
# Dynamic plugins use "from src.xxx import yyy", need to find src module
if getattr(sys, 'frozen', False):
    # PyInstaller packaged environment
    _base_path = os.path.dirname(sys.executable)
    _site_packages = os.path.join(_base_path, 'lib', 'site-packages')
    if os.path.exists(_site_packages) and _site_packages not in sys.path:
        sys.path.insert(0, _site_packages)

from src.common.diag_cmd import MainCommand
from src.common.stdio import IO

ROOT_IO = IO(1)


def main(args=None):
    """
    Main entry point for obdiag command.

    Args:
        args: Command line arguments (default: sys.argv[1:])

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    if args is None:
        args = sys.argv[1:]

    # Set default encoding (Python 2 compatibility)
    defaultencoding = 'utf-8'
    if sys.version_info[0] < 3:
        # Python 2: setdefaultencoding is available
        if sys.getdefaultencoding() != defaultencoding:
            try:
                from imp import reload

                reload(sys)
                sys.setdefaultencoding(defaultencoding)
            except (ImportError, AttributeError):
                pass
    # Python 3: default encoding is always UTF-8

    ROOT_IO.track_limit += 2

    if MainCommand().init(sys.argv[0], args).do_command():
        return 0
    else:
        return 1


if __name__ == '__main__':
    exit_code = main()
    ROOT_IO.exit(exit_code)
