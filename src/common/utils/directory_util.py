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
@file: directory_util.py
@desc: Directory utility functions (extracted from tool.py)
"""

import os
import stat
import shutil

# Note: FileUtil import is deferred to avoid circular dependency


class DirectoryUtil(object):

    @staticmethod
    def get_owner(path):
        return os.stat(path)[stat.ST_UID]

    @staticmethod
    def list_dir(path, stdio=None):
        files = []
        if os.path.isdir(path):
            for fn in os.listdir(path):
                fp = os.path.join(path, fn)
                if os.path.isdir(fp):
                    files += DirectoryUtil.list_dir(fp)
                else:
                    files.append(fp)
        return files

    @staticmethod
    def copy(src, dst, stdio=None):
        if not os.path.isdir(src):
            stdio and getattr(stdio, 'error', print)("cannot copy tree '%s': not a directory" % src)
            return False
        try:
            names = os.listdir(src)
        except:
            stdio and getattr(stdio, 'exception', print)("error listing files in '%s':" % (src))
            return False

        if DirectoryUtil.mkdir(dst, stdio):
            return False

        ret = True
        links = []
        for n in names:
            src_name = os.path.join(src, n)
            dst_name = os.path.join(dst, n)
            if os.path.islink(src_name):
                link_dest = os.readlink(src_name)
                links.append((link_dest, dst_name))

            elif os.path.isdir(src_name):
                ret = DirectoryUtil.copy(src_name, dst_name, stdio) and ret
            else:
                # Deferred import to avoid circular dependency
                from src.common.utils.file_util import FileUtil

                FileUtil.copy(src_name, dst_name, stdio)
        for link_dest, dst_name in links:
            # Deferred import to avoid circular dependency
            from src.common.utils.file_util import FileUtil

            FileUtil.symlink(link_dest, dst_name, stdio)
        return ret

    @staticmethod
    def mkdir(path, mode=0o755, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('mkdir %s' % path)
        try:
            os.makedirs(path, mode=mode)
            return True
        except OSError as e:
            if e.errno == 17:
                return True
            elif e.errno == 20:
                stdio and getattr(stdio, 'error', print)('%s is not a directory', path)
            else:
                stdio and getattr(stdio, 'error', print)('failed to create directory %s', path)
            stdio and getattr(stdio, 'exception', print)('')
        except:
            stdio and getattr(stdio, 'exception', print)('')
            stdio and getattr(stdio, 'error', print)('failed to create directory %s', path)
        return False

    @staticmethod
    def rm(path, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('rm %s' % path)
        try:
            if os.path.exists(path):
                if os.path.islink(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)
            return True
        except Exception as e:
            stdio and getattr(stdio, 'exception', print)('')
            stdio and getattr(stdio, 'error', print)('failed to remove %s', path)
        return False
