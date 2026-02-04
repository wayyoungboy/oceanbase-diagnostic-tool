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
@time: 2025/07/10
@file: crypto_config_handler.py
@desc: Handler for encrypting/decrypting config files (Migrated to BaseHandler)
"""
import os
import getpass
from src.common.base_handler import BaseHandler
from src.common.result_type import ObdiagResult
from src.common.file_crypto.file_crypto import FileEncryptor
from src.common.tool import Util


class CryptoConfigHandler(BaseHandler):
    def _init(self, **kwargs):
        """Subclass initialization"""
        pass

    def handle(self) -> ObdiagResult:
        """Execute crypto config handler"""
        self._validate_initialized()

        try:
            self._log_verbose("CryptoConfigHandler execute")
            file_path = self._get_option("file")
            encrypted_file_path = self._get_option("encrypted_file") or ""
            pd = self._get_option("key") or ""

            if file_path:
                file_path = os.path.abspath(os.path.expanduser(file_path))

            if file_path and not pd and not encrypted_file_path:
                self._log_warn("file path is empty or key is empty. need input key")
                key_first = getpass.getpass("please input key: ")
                key_second = getpass.getpass("please input key again: ")
                if key_first != key_second:
                    self._log_error("key is not same")
                    return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data="key is not same")
                pd = key_first

            if file_path and pd and not encrypted_file_path:
                self._log_verbose(f"encrypt file {file_path}")
                self.encrypt_file(file_path, pd)
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"message": "File encrypted successfully"})
            elif file_path and pd and encrypted_file_path:
                self._log_verbose(f"check encrypt file {file_path} and {encrypted_file_path}")
                self.check_encrypt_file(file_path, pd, encrypted_file_path)
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"message": "Encryption check completed"})
            elif file_path and encrypted_file_path and not pd:
                self._log_warn("file path is empty or key is empty. need input key")
                key_first = getpass.getpass("please input key: ")
                pd = key_first
                self.check_encrypt_file(file_path, pd, encrypted_file_path)
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"message": "Encryption check completed"})
            elif encrypted_file_path and pd and not file_path:
                self._log_verbose(f"decrypt file {encrypted_file_path}")
                self.decrypt_file(encrypted_file_path, pd)
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"message": "File decrypted successfully"})
            elif not file_path and not encrypted_file_path:
                self._log_error("file path is empty or encrypted_file_path is empty")
                return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data="file path is empty or encrypted_file_path is empty")
            else:
                return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data="Invalid parameters")

        except Exception as e:
            return self._handle_error(e)

    def encrypt_file(self, file_path, password):
        try:
            fileEncryptor = FileEncryptor(context=self.context)
            fileEncryptor.encrypt_file(file_path, password=password)
        except Exception as e:
            self._log_error(f"encrypt file failed, error: {e}")
            raise

    def decrypt_file(self, encrypted_file_path, password):
        try:
            fileEncryptor = FileEncryptor(context=self.context)
            self._log_info(str(fileEncryptor.decrypt_file(encrypted_file_path, password=password, save=False).decode('utf-8', errors='ignore')))
        except Exception as e:
            self._log_error(f"decrypt file failed, error: {e}")
            raise

    def check_encrypt_file(self, file_path, password, encrypted_file_path):
        try:
            fileEncryptor = FileEncryptor(context=self.context)
            fileEncryptor.check_encrypt_file(file_path, password=password, encrypted_file_path=encrypted_file_path)
        except Exception as e:
            self._log_error(f"check encrypt file failed, error: {e}")
            raise
