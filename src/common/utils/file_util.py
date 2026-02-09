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
@file: file_util.py
@desc: File utility functions (extracted from tool.py)
"""

import os
import sys
import stat
import shutil
import hashlib
import io
import fcntl
import bz2
import gzip
import lzma
import tarfile
import uuid
import tabulate

# Cross-platform zip compression support
_USE_PYZIPPER = False
try:
    import pyminizip
except ImportError:
    try:
        import pyzipper
        _USE_PYZIPPER = True
    except ImportError:
        raise ImportError("Neither pyminizip nor pyzipper is available. Please install one of them.")

_WINDOWS = os.name == 'nt'
encoding_open = open


class FileUtil(object):
    COPY_BUFSIZE = 1024 * 1024 if _WINDOWS else 64 * 1024

    @staticmethod
    def checksum(target_path, stdio=None):
        from src.common.ssh import LocalClient

        if not os.path.isfile(target_path):
            info = 'No such file: ' + target_path
            if stdio:
                getattr(stdio, 'error', print)(info)
                return False
            else:
                raise IOError(info)
        ret = LocalClient.execute_command('md5sum {}'.format(target_path), stdio=stdio)
        if ret:
            return ret.stdout.strip().split(' ')[0].encode('utf-8')
        else:
            m = hashlib.md5()
            with open(target_path, 'rb') as f:
                m.update(f.read())
            return m.hexdigest().encode(sys.getdefaultencoding())

    @staticmethod
    def copy_fileobj(fsrc, fdst):
        fsrc_read = fsrc.read
        fdst_write = fdst.write
        while True:
            buf = fsrc_read(FileUtil.COPY_BUFSIZE)
            if not buf:
                break
            fdst_write(buf)

    @staticmethod
    def copy(src, dst, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('copy %s %s' % (src, dst))
        if os.path.exists(src) and os.path.exists(dst) and os.path.samefile(src, dst):
            info = "`%s` and `%s` are the same file" % (src, dst)
            if stdio:
                getattr(stdio, 'error', print)(info)
                return False
            else:
                raise IOError(info)

        for fn in [src, dst]:
            try:
                st = os.stat(fn)
            except OSError:
                pass
            else:
                if stat.S_ISFIFO(st.st_mode):
                    info = "`%s` is a named pipe" % fn
                    if stdio:
                        getattr(stdio, 'error', print)(info)
                        return False
                    else:
                        raise IOError(info)

        try:
            if os.path.islink(src):
                FileUtil.symlink(os.readlink(src), dst)
                return True
            with FileUtil.open(src, 'rb') as fsrc, FileUtil.open(dst, 'wb') as fdst:
                FileUtil.copy_fileobj(fsrc, fdst)
                os.chmod(dst, os.stat(src).st_mode)
                return True
        except Exception as e:
            if int(getattr(e, 'errno', -1)) == 26:
                from src.common.ssh import LocalClient

                if LocalClient.execute_command('/usr/bin/cp -f %s %s' % (src, dst), stdio=stdio):
                    return True
            elif stdio:
                getattr(stdio, 'exception', print)('copy error: %s' % e)
            else:
                raise e
        return False

    @staticmethod
    def symlink(src, dst, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('link %s %s' % (src, dst))
        try:
            # Deferred import to avoid circular dependency
            from src.common.utils.directory_util import DirectoryUtil
            if DirectoryUtil.rm(dst, stdio):
                os.symlink(src, dst)
                return True
        except Exception as e:
            if stdio:
                getattr(stdio, 'exception', print)('link error: %s' % e)
            else:
                raise e
        return False

    @staticmethod
    def open(path, _type='r', encoding=None, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('open %s for %s' % (path, _type))
        if os.path.exists(path):
            if os.path.isfile(path):
                return encoding_open(path, _type, encoding=encoding)
            info = '%s is not file' % path
            if stdio:
                getattr(stdio, 'error', print)(info)
                return None
            else:
                raise IOError(info)
        dir_path, file_name = os.path.split(path)
        if dir_path:
            # Deferred import to avoid circular dependency
            from src.common.utils.directory_util import DirectoryUtil
            if DirectoryUtil.mkdir(dir_path, stdio=stdio):
                return encoding_open(path, _type, encoding=encoding)
        else:
            return encoding_open(path, _type, encoding=encoding)
        info = '%s is not file' % path
        if stdio:
            getattr(stdio, 'error', print)(info)
            return None
        else:
            raise IOError(info)

    @staticmethod
    def unzip(source, ztype=None, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('unzip %s' % source)
        if not ztype:
            ztype = source.split('.')[-1]
        try:
            if ztype == 'bz2':
                s_fn = bz2.BZ2File(source, 'r')
            elif ztype == 'xz':
                s_fn = lzma.LZMAFile(source, 'r')
            elif ztype == 'gz':
                s_fn = gzip.GzipFile(source, 'r')
            else:
                s_fn = open(source, 'r')
            return s_fn
        except:
            stdio and getattr(stdio, 'exception', print)('failed to unzip %s' % source)
        return None

    @staticmethod
    def extract_tar(tar_path, output_path, stdio=None):
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        try:
            with tarfile.open(tar_path, 'r') as tar:
                tar.extractall(path=output_path)
        except:
            stdio and getattr(stdio, 'exception', print)('failed to extract tar file %s' % tar_path)
        return None

    @staticmethod
    def rm(path, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('rm %s' % path)
        if not os.path.exists(path):
            return True
        try:
            os.remove(path)
            return True
        except:
            stdio.warn('failed to remove %s' % path)
        return False

    @staticmethod
    def move(src, dst, stdio=None):
        return shutil.move(src, dst)

    @staticmethod
    def share_lock_obj(obj, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('try to get share lock %s' % obj.name)
        fcntl.flock(obj, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return obj

    @classmethod
    def share_lock(cls, path, _type='w', stdio=None):
        return cls.share_lock_obj(cls.open(path, _type=_type, stdio=stdio))

    @staticmethod
    def exclusive_lock_obj(obj, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('try to get exclusive lock %s' % obj.name)
        fcntl.flock(obj, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return obj

    @classmethod
    def exclusive_lock(cls, path, _type='w', stdio=None):
        return cls.exclusive_lock_obj(cls.open(path, _type=_type, stdio=stdio))

    @staticmethod
    def unlock(obj, stdio=None):
        stdio and getattr(stdio, 'verbose', print)('unlock %s' % obj.name)
        fcntl.flock(obj, fcntl.LOCK_UN)
        return obj

    @staticmethod
    def size_format(num, unit="B", output_str=False, stdio=None):
        if num < 0:
            raise ValueError("num cannot be negative!")
        units = ["B", "K", "M", "G", "T"]
        try:
            unit_idx = units.index(unit)
        except KeyError:
            raise ValueError("unit {0} is illegal!".format(unit))
        new_num = float(num) * (1024**unit_idx)
        unit_idx = 0
        while new_num > 1024:
            new_num = float(new_num) / 1024
            unit_idx += 1
        if unit_idx >= len(units):
            raise ValueError("size exceed 1023TB!")
        if output_str:
            return "".join(["%.3f" % new_num, units[unit_idx]])
        return new_num, units[unit_idx]

    @staticmethod
    def show_file_size_tabulate(ssh_client, file_size, stdio=None):
        format_file_size = FileUtil.size_format(int(file_size), output_str=True, stdio=stdio)
        summary_tab = []
        field_names = ["Node", "LogSize"]
        summary_tab.append((ssh_client.get_name(), format_file_size))
        return "\nZipFileInfo:\n" + tabulate.tabulate(summary_tab, headers=field_names, tablefmt="grid", showindex=False)

    @staticmethod
    def show_file_list_tabulate(ip, file_list, stdio=None):
        summary_tab = []
        field_names = ["Node", "LogList"]
        summary_tab.append((ip, file_list))
        return "\nFileListInfo:\n" + tabulate.tabulate(summary_tab, headers=field_names, tablefmt="grid", showindex=False)

    @staticmethod
    def find_all_file(base, stdio=None):
        file_list = []
        for root, ds, fs in os.walk(base):
            for f in fs:
                fullname = os.path.join(root, f)
                file_list.append(fullname)
        return file_list

    @staticmethod
    def calculate_sha256(filepath, stdio=None):
        sha256 = hashlib.sha256()
        try:
            filepath = os.path.expanduser(filepath)
            with open(filepath, 'rb') as file:
                while True:
                    data = file.read(8192)
                    if not data:
                        break
                    sha256.update(data)
            return sha256.hexdigest()
        except Exception as e:
            return ""

    @staticmethod
    def size(size_str, unit='B', stdio=None):
        unit_size_dict = {
            "b": 1,
            "B": 1,
            "k": 1024,
            "K": 1024,
            "m": 1024 * 1024,
            "M": 1024 * 1024,
            "g": 1024 * 1024 * 1024,
            "G": 1024 * 1024 * 1024,
            "t": 1024 * 1024 * 1024 * 1024,
            "T": 1024 * 1024 * 1024 * 1024,
        }
        unit_str = size_str.strip()[-1]
        if unit_str not in unit_size_dict:
            raise ValueError('unit {0} not in {1}'.format(unit_str, unit_size_dict.keys()))
        real_size = float(size_str.strip()[:-1]) * unit_size_dict[unit_str]
        if real_size < 0:
            raise ValueError('size cannot be negative!')
        return real_size / unit_size_dict[unit]

    @staticmethod
    def write_append(filename, result, stdio=None):
        with io.open(filename, 'a', encoding='utf-8') as fileobj:
            fileobj.write(u'{}'.format(result))

    @staticmethod
    def tar_gz_to_zip(temp_dir, tar_gz_file, output_zip, password, stdio):
        extract_dir = os.path.join(temp_dir, 'extracted_files_{0}'.format(str(uuid.uuid4())[:6]))

        try:
            # 1. Extract the tar.gz file
            with tarfile.open(tar_gz_file, 'r:gz') as tar:
                tar.extractall(path=extract_dir)
            stdio.verbose("tar.gz file extracted to {0}".format(extract_dir))

            # 2. Gather all extracted files and their relative paths
            files_to_compress = []
            base_paths = []
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    base_path = os.path.basename(root)
                    files_to_compress.append(file_path)
                    base_paths.append(base_path)
            stdio.verbose("start compress_multiple using {0}".format("pyzipper" if _USE_PYZIPPER else "pyminizip"))
            # 3. Compress the extracted files into a (possibly) encrypted zip file
            if _USE_PYZIPPER:
                # Use pyzipper for macOS compatibility
                if password:
                    with pyzipper.AESZipFile(output_zip, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                        zf.setpassword(password.encode('utf-8'))
                        for file_path, base_path in zip(files_to_compress, base_paths):
                            arcname = os.path.join(base_path, os.path.basename(file_path))
                            zf.write(file_path, arcname)
                    stdio.verbose("extracted files compressed into encrypted {0}".format(output_zip))
                else:
                    with pyzipper.ZipFile(output_zip, 'w', compression=pyzipper.ZIP_DEFLATED) as zf:
                        for file_path, base_path in zip(files_to_compress, base_paths):
                            arcname = os.path.join(base_path, os.path.basename(file_path))
                            zf.write(file_path, arcname)
                    stdio.verbose("extracted files compressed into unencrypted {0}".format(output_zip))
            else:
                # Use pyminizip for Linux
                if password:
                    pyminizip.compress_multiple(files_to_compress, base_paths, output_zip, password, 5)  # 5 is the compression level
                    stdio.verbose("extracted files compressed into encrypted {0}".format(output_zip))
                else:
                    pyminizip.compress_multiple(files_to_compress, base_paths, output_zip, None, 5)
                    stdio.verbose("extracted files compressed into unencrypted {0}".format(output_zip))

            # 4. Remove the extracted directory
            shutil.rmtree(extract_dir)
            stdio.verbose("extracted directory {0} removed".format(extract_dir))

            # 5. Optionally remove the original tar.gz file
            os.remove(tar_gz_file)
            stdio.verbose("original tar.gz file {0} removed".format(tar_gz_file))

        except tarfile.TarError as te:
            stdio.exception("tar file error: {0}".format(te))
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            return False
        except Exception as e:
            stdio.exception("an error occurred: {0}".format(e))
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            return False

        return True
