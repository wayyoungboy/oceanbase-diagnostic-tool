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
@time: 2024/2/1
@file: update.py
@desc: Handler for updating obdiag files (Migrated to BaseHandler)
"""
import os
import shutil
import time
from src.common.base_handler import BaseHandler
from src.common.constant import const
from src.common.tool import FileUtil
from src.common.tool import NetUtils
from src.common.tool import StringUtils
from src.common.tool import Util
from src.common.version import OBDIAG_VERSION
import oyaml as yaml

from src.common.result_type import ObdiagResult


# for update obdiag files without obdiag
class UpdateHandler(BaseHandler):
    def _init(self, **kwargs):
        """Subclass initialization"""
        self.local_update_file_sha = ""
        self.local_obdiag_version = OBDIAG_VERSION
        self.remote_obdiag_version = ""
        self.remote_tar_sha = ""
        self.file_path = ""
        self.force = False

        # on obdiag update command
        if self.context and self.context.namespace and self.context.namespace.spacename == "update":
            self.file_path = self._get_option('file', default="")
            self.force = self._get_option('force', default=False)

    def handle(self) -> ObdiagResult:
        """Handle update command"""
        self._validate_initialized()

        try:
            file_path = self.file_path
            force = self.force
            remote_server = const.UPDATE_REMOTE_SERVER
            remote_version_file_name = const.UPDATE_REMOTE_VERSION_FILE_NAME
            local_version_file_name = os.path.expanduser('~/.obdiag/remote_version.yaml')
            remote_update_file_name = const.UPDATE_REMOTE_UPDATE_FILE_NAME
            local_update_file_name = os.path.expanduser('~/.obdiag/data.tar')
            local_update_log_file_name = os.path.expanduser('~/.obdiag/data_version.yaml')

            if file_path and file_path != "":
                return self.handle_update_offline(file_path)

            if NetUtils.network_connectivity(remote_server) is False:
                self._log_warn("[update] network connectivity failed. Please check your network connection.")
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="network connectivity failed. Please check your network connection.")

            NetUtils.download_file(remote_version_file_name, os.path.expanduser(local_version_file_name))
            with open(local_version_file_name, 'r') as file:
                remote_data = yaml.safe_load(file)

            if remote_data.get("obdiag_version") is None:
                self._log_warn("obdiag_version is None. Do not perform the upgrade process.")
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="obdiag_version is None. Do not perform the upgrade process.")
            else:
                self.remote_obdiag_version = remote_data["obdiag_version"].strip()

            if StringUtils.compare_versions_greater(self.remote_obdiag_version, self.local_obdiag_version):
                self._log_warn(
                    f"remote_obdiag_version is {self.remote_obdiag_version}. local_obdiag_version is {self.local_obdiag_version}. "
                    "remote_obdiag_version>local_obdiag_version. Unable to update dependency files, please upgrade "
                    "obdiag. Do not perform the upgrade process."
                )
                return ObdiagResult(
                    ObdiagResult.SERVER_ERROR_CODE,
                    error_data=f"remote_obdiag_version is {self.remote_obdiag_version}. local_obdiag_version is {self.local_obdiag_version}. "
                    "remote_obdiag_version>local_obdiag_version. Unable to update dependency files, please upgrade "
                    "obdiag. Do not perform the upgrade process.",
                )

            if remote_data.get("remote_tar_sha") is None:
                self._log_warn("remote_tar_sha is None. Do not perform the upgrade process.")
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="remote_tar_sha is None. Do not perform the upgrade process.")
            else:
                self.remote_tar_sha = remote_data["remote_tar_sha"]

            # need update?
            # get local sha
            if force is False:
                if os.path.exists(os.path.expanduser(local_update_log_file_name)):
                    with open(os.path.expanduser(local_update_log_file_name), 'r') as file:
                        local_data = yaml.safe_load(file)
                    if local_data.get("remote_tar_sha") is not None and local_data.get("remote_tar_sha") == self.remote_tar_sha:
                        self._log_warn("[update] remote_tar_sha as local_tar_sha. No need to update.")
                        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"msg": "remote_tar_sha as local_tar_sha. No need to update."})
                    # get data_update_time
                    if local_data.get("data_update_time") is not None and time.time() - local_data["data_update_time"] < 3600 * 24 * 7:
                        self._log_warn("[update] data_update_time No need to update.")
                        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"msg": "No need to update"})

            # download_update_files
            NetUtils.download_file(remote_update_file_name, local_update_file_name)
            # check_sha
            self.local_update_file_sha = FileUtil.calculate_sha256(local_update_file_name)
            if self.remote_tar_sha != self.local_update_file_sha:
                self._log_warn(f"remote_tar_sha is {self.remote_tar_sha}, but local_tar_sha is {self.local_update_file_sha}. Unable to update dependency files. Do not perform the upgrade process.")
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data=f"SHA mismatch: remote={self.remote_tar_sha}, local={self.local_update_file_sha}")

            # move old files
            ## check_old_files
            if os.path.exists(os.path.expanduser("~/.obdiag/check.d")):
                shutil.rmtree(os.path.expanduser("~/.obdiag/check.d"))
            if os.path.exists(os.path.expanduser("~/.obdiag/check")):
                os.rename(os.path.expanduser("~/.obdiag/check"), os.path.expanduser("~/.obdiag/check.d"))
            ## gather
            if os.path.exists(os.path.expanduser("~/.obdiag/gather.d")):
                shutil.rmtree(os.path.expanduser("~/.obdiag/gather.d"))
            if os.path.exists(os.path.expanduser("~/.obdiag/gather")):
                os.rename(os.path.expanduser("~/.obdiag/gather"), os.path.expanduser("~/.obdiag/gather.d"))

            ## rca
            if os.path.exists(os.path.expanduser("~/.obdiag/rca.d")):
                shutil.rmtree(os.path.expanduser("~/.obdiag/rca.d"))
            if os.path.exists(os.path.expanduser("~/.obdiag/rca")):
                os.rename(os.path.expanduser("~/.obdiag/rca"), os.path.expanduser("~/.obdiag/rca.d"))

            # decompression remote files
            FileUtil.extract_tar(os.path.expanduser(local_update_file_name), os.path.expanduser("~/.obdiag"))
            # update data save
            with open(os.path.expanduser("~/.obdiag/data_version.yaml"), 'w') as f:
                yaml.dump({"data_update_time": int(time.time()), "remote_tar_sha": self.remote_tar_sha}, f)

            self._log_info("[update] Successfully updated. The original data is stored in the *. d folder.")
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"msg": "Successfully updated. The original data is stored in the *. d folder."})
        except Exception as e:
            return self._handle_error(e)

    def handle_update_offline(self, file):
        file = os.path.expanduser(file)

        self.local_update_file_sha = FileUtil.calculate_sha256(file)
        if os.path.exists(file) is False:
            self._log_error(f'{file} does not exist.')
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data=f"{file} does not exist.")
        if not file.endswith('.tar'):
            self._log_error(f'{file} is not a tar file.')
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data=f"{file} is not a tar file.")
        ## check_old_files
        if os.path.exists(os.path.expanduser("~/.obdiag/check.d")):
            shutil.rmtree(os.path.expanduser("~/.obdiag/check.d"))
        if os.path.exists(os.path.expanduser("~/.obdiag/check")):
            os.rename(os.path.expanduser("~/.obdiag/check"), os.path.expanduser("~/.obdiag/check.d"))
        ## gather
        if os.path.exists(os.path.expanduser("~/.obdiag/gather.d")):
            shutil.rmtree(os.path.expanduser("~/.obdiag/gather.d"))
        if os.path.exists(os.path.expanduser("~/.obdiag/gather")):
            os.rename(os.path.expanduser("~/.obdiag/gather"), os.path.expanduser("~/.obdiag/gather.d"))
        ## rca
        if os.path.exists(os.path.expanduser("~/.obdiag/rca.d")):
            shutil.rmtree(os.path.expanduser("~/.obdiag/rca.d"))
        if os.path.exists(os.path.expanduser("~/.obdiag/rca")):
            os.rename(os.path.expanduser("~/.obdiag/rca"), os.path.expanduser("~/.obdiag/rca.d"))
        # decompression remote files
        FileUtil.extract_tar(os.path.expanduser(file), os.path.expanduser("~/.obdiag"))
        # update data save
        with open(os.path.expanduser("~/.obdiag/data_version.yaml"), 'w') as f:
            yaml.dump({"data_update_time": int(time.time()), "remote_tar_sha": self.remote_tar_sha}, f)
        self._log_info("[update] Successfully updated. The original data is stored in the *. d folder.")
        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"msg": "Successfully updated. The original data is stored in the *. d folder."})
