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
@time: 2024/01/23
@file: rca_list.py
@desc: Handler for listing RCA scenes (Migrated to BaseHandler)
"""
import os.path
from src.common.base_handler import BaseHandler
from src.common.constant import const
from src.common.tool import DynamicLoading
from src.common.tool import Util
from src.common.result_type import ObdiagResult


class RcaScenesListHandler(BaseHandler):
    def _init(self, work_path=None, **kwargs):
        """Subclass initialization"""
        # Use config value if available, otherwise use parameter or default
        if not work_path:
            if hasattr(self, 'config') and hasattr(self.config, 'rca_work_path'):
                work_path = self.config.rca_work_path
            else:
                work_path = const.RCA_WORK_PATH

        if os.path.exists(os.path.expanduser(work_path)):
            self.work_path = os.path.expanduser(work_path)
        else:
            # Fallback to default if specified path doesn't exist
            default_path = const.RCA_WORK_PATH
            if hasattr(self, 'config') and hasattr(self.config, 'rca_work_path'):
                default_path = self.config.rca_work_path
            self._log_warn(f"input rca work_path not exists: {work_path}, use default path {default_path}")
            self.work_path = os.path.expanduser(default_path)

    def get_all_scenes(self):
        # find all rca file
        scenes_files = self.__find_rca_files()
        # get all info
        scene_list = {}
        scene_info_list = {}
        if not scenes_files or len(scenes_files) == 0:
            self._log_error(f"no rca scene found! Please check RCA_WORK_PATH: {self.work_path}")
            return {}, {}

        for scene_file in scenes_files:
            lib_path = self.work_path
            module_name = os.path.basename(scene_file)[:-3]
            DynamicLoading.add_lib_path(lib_path)
            module = DynamicLoading.import_module(os.path.basename(scene_file)[:-3], None)
            if not hasattr(module, module_name):
                self._log_error(f"{module_name} import_module failed")
                continue
            scene_list[module_name] = getattr(module, module_name)

        for scene_name, scene in scene_list.items():
            scene_info = scene.get_scene_info()
            if "example" in scene_info:
                scene_info_list[scene_name] = {"name": scene_name, "command": "{0}".format(scene_info.get("example") or "obdiag rca run --scene={0}".format(scene_name)), "info_en": scene_info["info_en"], "info_cn": scene_info["info_cn"]}
                continue
            scene_info_list[scene_name] = {"name": scene_name, "command": "obdiag rca run --scene={0}".format(scene_name), "info_en": scene_info["info_en"], "info_cn": scene_info["info_cn"]}
        return scene_info_list, scene_list

    def handle(self) -> ObdiagResult:
        """List all RCA scenes"""
        self._validate_initialized()

        try:
            self._log_verbose("Listing RCA scenes")
            scene_info_list, scene_item_list = self.get_all_scenes()
            Util.print_scene(scene_info_list, stdio=self.stdio)
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data=scene_info_list)
        except Exception as e:
            return self._handle_error(e)

    def __find_rca_files(self):
        files = []
        for file_or_folder in os.listdir(self.work_path):
            full_path = os.path.join(self.work_path, file_or_folder)
            if os.path.isfile(full_path):
                if full_path.endswith('.py') and len(os.path.basename(full_path)) > 7:
                    files.append(full_path)
        return files
