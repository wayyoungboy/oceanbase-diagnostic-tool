#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# You may obtain a software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/03
@file: check_list_refactored.py
@desc: Refactored CheckListHandler using new BaseHandler architecture
"""

import os
import oyaml as yaml
from src.common.base_handler import BaseHandler
from src.common.result_type import ObdiagResult
from src.common.tool import Util, DynamicLoading


class CheckListHandlerRefactored(BaseHandler):
    """
    Refactored handler for listing available check tasks and packages.

    This is an example of migrating an existing handler to the new architecture.
    """

    def _init(self, **kwargs):
        """Subclass initialization"""
        # Use ConfigAccessor for configuration access
        if self.config:
            self.work_path = self.config.check_work_path
        else:
            self.work_path = os.path.expanduser("~/.obdiag/check")

        self._log_verbose(f"CheckListHandler initialized: work_path={self.work_path}")

    def handle(self) -> ObdiagResult:
        """
        List all available check cases and tasks.

        Returns:
            ObdiagResult: List of check cases and tasks
        """
        self._validate_initialized()

        try:
            self._log_verbose("Listing check cases")

            entries = os.listdir(self.work_path)
            files = [f for f in entries if os.path.isfile(os.path.join(self.work_path, f))]
            result_map = {}

            # Process package files
            for file in files:
                if "check_package" in file:
                    cases_map = {"all": {"name": "all", "command": "obdiag check run", "info_en": "default check all task without filter", "info_cn": "默认执行除filter组里的所有巡检项"}}

                    # Parse package file name
                    parts = file.split('_')
                    if len(parts) < 1:
                        self._log_warn(f"Invalid check package name: {file}, " "Please don't add file which 'check_package' in the name")
                        continue

                    target = parts[0]
                    file_path = os.path.join(self.work_path, file)

                    # Read yaml file
                    try:
                        with open(file_path, 'r') as f:
                            package_file_data = yaml.safe_load(f)
                            result_map[target] = {}
                            result_map[target]["commands"] = []

                            if not package_file_data or len(package_file_data) == 0:
                                self._log_warn(f"No data in check package: {file_path}")
                                continue

                            for package_data in package_file_data:
                                if package_data == "filter":
                                    continue

                                package_target = "cases" if target == "observer" else f"{target}_cases"

                                case_info = {
                                    "name": package_data,
                                    "command": f"obdiag check run --{package_target}={package_data}",
                                    "info_en": package_file_data[package_data].get("info_en") or "",
                                    "info_cn": package_file_data[package_data].get("info_cn") or "",
                                }

                                cases_map[package_data] = case_info
                                result_map[target]["commands"].append(case_info)

                        Util.print_title(f"check cases about {target}", stdio=self.stdio)
                        Util.print_scene(cases_map, stdio=self.stdio)

                    except Exception as e:
                        self._log_error(f"Failed to process package file {file_path}: {e}")
                        continue

            # Check if --all option is provided
            show_all_tasks = self._get_option('all', False)

            if show_all_tasks:
                task_list = self._get_task_list()
                for target in task_list:
                    if task_list[target] is None:
                        continue

                    self._log_info(f"\n\ntasks of {target}:")
                    result_map[target]["tasks"] = task_list[target]

                    for task_name in task_list[target]:
                        task_data = task_list[target][task_name]
                        task_info = task_data.get("info", "") if isinstance(task_data, dict) else task_data
                        task_issue_link = task_data.get("issue_link", "") if isinstance(task_data, dict) else ""

                        if task_issue_link:
                            self._log_info(f"name: {task_name}\ninfo: {task_info}\nissue_link: {task_issue_link}\n")
                        else:
                            self._log_info(f"name: {task_name}\ninfo: {task_info}\n")

            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data=result_map)

        except Exception as e:
            return self._handle_error(e)

    def _get_task_list(self):
        """
        Get list of all tasks for each target.

        Returns:
            Dictionary mapping target to task list
        """
        self._log_verbose("Getting task list")
        tasks_list = {"obproxy": self._get_task_list_by_target("obproxy"), "observer": self._get_task_list_by_target("observer")}
        return tasks_list

    def _get_task_list_by_target(self, target: str):
        """
        Get all Python tasks for a specific target.

        Args:
            target: Either "obproxy" or "observer"

        Returns:
            dict: Task name -> task info mapping (includes 'info' and optional 'issue_link')
        """
        self._log_verbose(f"Getting all tasks by target: {target}")
        current_path = os.path.join(self.work_path, "tasks", target)
        tasks_info = {}

        if not os.path.exists(current_path):
            self._log_warn(f"Task directory does not exist: {current_path}")
            return tasks_info

        for root, dirs, files in os.walk(current_path):
            for file in files:
                # Only load Python files
                if file.endswith('.py') and not file.startswith('__'):
                    lib_path = root
                    module_name = os.path.basename(file)[:-3]
                    task_name = f"{os.path.basename(root)}.{module_name}"

                    try:
                        DynamicLoading.add_lib_path(lib_path)
                        module = DynamicLoading.import_module(module_name, None)

                        if not hasattr(module, module_name):
                            self._log_error(f"{task_name} import_module failed: " f"missing {module_name} attribute")
                            continue

                        # Get task info including issue_link
                        task_instance = getattr(module, module_name)
                        task_info = task_instance.get_task_info()

                        tasks_info[task_name] = {"info": task_info.get("info", ""), "issue_link": task_info.get("issue_link", "")}

                    except Exception as e:
                        self._log_error(f"Load task {task_name} failed: {e}")

        return tasks_info
