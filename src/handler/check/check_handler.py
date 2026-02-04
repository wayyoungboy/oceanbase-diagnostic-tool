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
@time: 2024/12/29
@file: check_handler.py
@desc: Handler for executing Python check tasks (Migrated to BaseHandler)
"""

import os
import queue
import traceback
import re
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from src.common.base_handler import BaseHandler
from src.common.result_type import ObdiagResult
from src.common.ob_connector import OBConnector
from src.common.scene import get_version_by_type
from src.handler.check.check_exception import CheckException
from src.handler.check.check_report import TaskReport, CheckReport, CheckReportException
from src.common.tool import Util, DynamicLoading
from src.common.tool import StringUtils, TimeUtils


class CheckHandler(BaseHandler):
    """
    Handler for executing Python check tasks.

    This handler:
    1. Loads Python check tasks from the tasks directory
    2. Executes tasks based on specified cases or filters
    3. Generates check reports in various formats
    """

    def _init(self, check_target_type="observer", **kwargs):
        """Subclass initialization"""
        self.version = None
        self.report = None
        self.tasks = None

        # Use ConfigAccessor for configuration access
        self.max_workers = self.config.check_max_workers
        self.work_path = self.config.check_work_path
        self.export_report_type = self.config.check_report_type
        self.ignore_version = self.config.check_ignore_version

        self.cluster = self.context.cluster_config
        self.check_target_type = check_target_type

        # Get nodes based on target type
        if check_target_type == "observer":
            self.nodes = self.context.cluster_config.get("servers")
        elif check_target_type == "obproxy":
            self.nodes = self.context.obproxy_config.get("servers")
        else:
            self.nodes = []

        self.tasks_base_path = os.path.join(self.work_path, "tasks")

        # Get environment option
        env_option = self._get_option('env')
        self.input_env = StringUtils.parse_env_display(env_option) if env_option else {}

        # Log initialization info
        self._log_verbose(
            f"CheckHandler input. ignore_version={self.ignore_version}, "
            f"cluster={self.cluster.get('ob_cluster_name') or self.cluster.get('obproxy_cluster_name')}, "
            f"nodes={StringUtils.node_cut_passwd_for_log(self.nodes)}, "
            f"export_report_path={self.export_report_path}, "
            f"export_report_type={self.export_report_type}, "
            f"check_target_type={self.check_target_type}, "
            f"tasks_base_path={self.tasks_base_path}, "
            f"input_env={self.input_env}"
        )

        # Validate check_target_type
        if not self.check_target_type:
            raise CheckException("check_target_type is null. Please check the conf")

        # case_package_file
        case_package_file = os.path.join(self.work_path, f"{self.check_target_type}_check_package.yaml")
        case_package_file = os.path.expanduser(case_package_file)
        if os.path.exists(case_package_file):
            self.package_file_name = case_package_file
        else:
            raise CheckException(f"case_package_file {case_package_file} is not exist")
        self._log_verbose(f"case_package_file is {self.package_file_name}")

        # checker tasks_base_path
        tasks_base_path = os.path.join(self.tasks_base_path, self.check_target_type)
        tasks_base_path = os.path.expanduser(tasks_base_path)
        if os.path.exists(tasks_base_path):
            self.tasks_base_path = tasks_base_path
        else:
            raise CheckException(f"tasks_base_path {tasks_base_path} is not exist")
        self._log_verbose(f"tasks_base_path is {self.tasks_base_path}")

        # Setup SSH connections using connection manager if available
        # Note: SSH connections can be created per-task in __execute_one for thread safety,
        # but we also support pre-creating them here if ssh_manager is available
        if hasattr(self, 'ssh_manager') and self.ssh_manager and self.nodes:
            self.nodes = self.ssh_manager.setup_nodes_with_connections(self.context, self.nodes, self.check_target_type)
        else:
            # Fallback: SSH connections will be created per-task in __execute_one
            # This avoids connection contention and ensures thread safety
            pass

        # Get version and setup connection pool
        if self._get_option('cases') != "build_before":
            self.version = get_version_by_type(self.context, self.check_target_type, self.stdio)
            obConnectorPool = None
            try:
                # Connection pool size matches max_workers for optimal concurrency
                pool_size = min(self.max_workers, 12)  # max 12 connections to avoid overloading DB
                obConnectorPool = CheckOBConnectorPool(self.context, pool_size, self.cluster)
            except Exception as e:
                self._log_warn(f"obConnector init error. Error info is {e}")
            finally:
                self.context.set_variable('check_obConnector_pool', obConnectorPool)
        else:
            self._log_warn("check cases is build_before, so don't get version")

    def handle(self) -> ObdiagResult:
        """Main entry point for check execution."""
        self._validate_initialized()

        try:
            package_name = None
            input_tasks = None

            # Get input tasks or package name
            if self.check_target_type == "obproxy":
                input_tasks = self._get_option('obproxy_tasks')
                package_name = self._get_option('obproxy_cases')
            elif self.check_target_type == "observer":
                input_tasks = self._get_option('observer_tasks')
                package_name = self._get_option('cases')

            if self._get_option('cases') == "build_before" and self.check_target_type == "obproxy":
                self._log_info("when cases is build_before, not check obproxy")
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"message": "obproxy check skipped"})

            # Update export_report_path from options
            store_dir = self._get_option('store_dir')
            if store_dir:
                self.export_report_path = os.path.expanduser(store_dir)
                self._log_verbose(f"export_report_path change to {self.export_report_path}")
            else:
                # Default to current directory if not specified
                self.export_report_path = "./"

            if not os.path.exists(self.export_report_path):
                self._log_warn(f"{self.export_report_path} not exists. mkdir it!")
                os.makedirs(self.export_report_path, exist_ok=True)

            # Create timestamped subdirectory similar to gather
            target_dir = "obdiag_check_{0}".format(TimeUtils.timestamp_to_filename_time(TimeUtils.get_current_us_timestamp()))
            self.export_report_path = os.path.join(self.export_report_path, target_dir)
            if not os.path.exists(self.export_report_path):
                os.makedirs(self.export_report_path, exist_ok=True)

            # Change self.export_report_type
            report_type = self._get_option('report_type')
            if report_type:
                self.export_report_type = report_type
                if self.export_report_type not in ["table", "json", "xml", "yaml", "html"]:
                    raise CheckException("report_type must be table, json, xml, yaml, html")
            self._log_verbose(f"export_report_path is {self.export_report_path}")

            # get tasks
            self.tasks = {}
            if input_tasks:
                input_tasks = input_tasks.replace(" ", "")
                input_tasks = input_tasks.split(";")
                self.get_all_tasks()
                end_tasks = {}
                for package_task in input_tasks:
                    if package_task in self.tasks:
                        end_tasks[package_task] = self.tasks[package_task]
                    for task_name, value in self.tasks.items():
                        if re.match(package_task, task_name):
                            end_tasks[task_name] = self.tasks[task_name]
                if len(end_tasks) == 0:
                    raise CheckException("no cases is check by *_tasks: {0}".format(input_tasks))
                self.tasks = end_tasks
                self.stdio.verbose("input_tasks is {0}".format(input_tasks))
            elif package_name:
                self.stdio.verbose("package_name is {0}".format(package_name))
                package_tasks_by_name = self.get_package_tasks(package_name)
                self.get_all_tasks()
                end_tasks = {}
                for package_task in package_tasks_by_name:
                    if package_task in self.tasks:
                        end_tasks[package_task] = self.tasks[package_task]
                    for task_name, value in self.tasks.items():
                        if re.match(package_task, task_name):
                            end_tasks[task_name] = self.tasks[task_name]
                self.tasks = end_tasks
            else:
                self.stdio.verbose("tasks_package is all")
                self.get_all_tasks()
                filter_tasks = self.get_package_tasks("filter")
                if len(filter_tasks) > 0:
                    self.tasks = {key: value for key, value in self.tasks.items() if key not in filter_tasks}
                    new_tasks = {}
                    for task_name, task_value in self.tasks.items():
                        filter_tag = False
                        for filter_task in filter_tasks:
                            if re.match(filter_task.strip(), task_name.strip()):
                                filter_tag = True
                        if not filter_tag:
                            new_tasks[task_name] = task_value
                    self.tasks = new_tasks

            self._log_verbose(f"tasks is {list(self.tasks.keys())}")
            result = self.__execute()
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data=result)
        except CheckException as e:
            return self._handle_error(e, error_code=ObdiagResult.INPUT_ERROR_CODE)
        except Exception as e:
            self._log_error(f"Get package tasks failed. Error info is {e}")
            self._log_verbose(traceback.format_exc())
            return self._handle_error(e)

    def get_all_tasks(self):
        """Load all Python check tasks from the tasks directory."""
        self._log_verbose("Getting all tasks")
        current_path = self.tasks_base_path
        tasks = {}

        for root, dirs, files in os.walk(current_path):
            for file in files:
                # Only load Python files
                if file.endswith('.py') and not file.startswith('__'):
                    folder_name = os.path.basename(root)
                    task_name = f"{folder_name}.{file.split('.')[0]}"
                    try:
                        DynamicLoading.add_lib_path(root)
                        task_module = DynamicLoading.import_module(file[:-3], self.stdio)
                        attr_name = task_name.split('.')[-1]
                        if task_module is None:
                            self._log_error(f"{task_name} import_module failed: module is None")
                            continue
                        if not hasattr(task_module, attr_name):
                            self._log_error(f"{task_name} import_module failed: missing {attr_name} attribute. " f"Module attrs: {[x for x in dir(task_module) if not x.startswith('_')]}")
                            continue
                        tasks[task_name] = getattr(task_module, attr_name)
                    except Exception as e:
                        self._log_error(f"import_module {task_name} failed: {e}")
                        raise CheckException(f"import_module {task_name} failed: {e}")

        if len(tasks) == 0:
            raise CheckException(f"No tasks found in {current_path}")
        self.tasks = tasks

    def get_package_tasks(self, package_name):
        """Get task list from package configuration file."""
        with open(self.package_file_name, 'r', encoding='utf-8') as file:
            package_file_data = yaml.safe_load(file)
            packege_tasks = package_file_data

        if package_name not in packege_tasks:
            if package_name == "filter":
                return []
            else:
                raise CheckException(f"no cases name is {package_name}")

        self._log_verbose(f"by cases name: {package_name}, get cases: {packege_tasks[package_name]}")
        if packege_tasks[package_name].get("tasks") is None:
            return []
        return packege_tasks[package_name].get("tasks")

    def __execute_one(self, task_name):
        """Execute a single check task."""
        task_instance = None
        try:
            self._log_verbose(f"execute task: {task_name}")
            report = TaskReport(self.context, task_name)

            # Pre-check: verify OS compatibility
            task_instance = self.tasks[task_name]
            task_info = task_instance.get_task_info()
            supported_os = task_info.get("supported_os")

            if supported_os:
                # Check if current OS is supported
                current_os = self.__get_current_os()
                if current_os not in supported_os:
                    self._log_verbose(f"Task {task_name} skipped: requires {supported_os}, current OS is {current_os}")
                    report.add_warning(f"Task skipped: requires OS {supported_os}, current is {current_os}")
                    return report

            if not self.ignore_version:
                version = self.version
                if version or self._get_option('cases') == "build_before":
                    self.cluster["version"] = version
                    self._log_verbose(f"cluster.version is {self.cluster['version']}")

                    # Execute Python task
                    # SSH connections are created in TaskBase.init() for thread safety
                    task_instance = self.tasks[task_name]
                    task_instance.init(self.context, report)
                    task_instance.execute()

                    self._log_verbose(f"execute task end: {task_name}")
                    return report
                else:
                    self._log_error("can't get version")
            else:
                self._log_verbose("ignore version")
                # Execute Python task without version check
                # SSH connections are created in TaskBase.init() for thread safety
                task_instance = self.tasks[task_name]
                task_instance.init(self.context, report)
                task_instance.execute()
                return report
        except Exception as e:
            self._log_error(f"execute_one Exception: {e}")
            raise CheckException(f"execute_one Exception: {e}")
        finally:
            # Cleanup task resources (release connection back to pool and close SSH connections)
            if task_instance and hasattr(task_instance, 'cleanup'):
                try:
                    task_instance.cleanup()
                except Exception as cleanup_error:
                    self._log_warn(f"task cleanup error: {cleanup_error}")

    def __execute(self):
        """Execute all check tasks concurrently and generate report."""
        try:
            task_count = len(self.tasks.keys())
            self._log_verbose(f"execute_all_tasks. the number of tasks is {task_count}, tasks is {list(self.tasks.keys())}")
            self.report = CheckReport(self.context, export_report_path=self.export_report_path, export_report_type=self.export_report_type, report_target=self.check_target_type)

            # Determine actual worker count (don't use more workers than tasks)
            actual_workers = min(self.max_workers, task_count) if task_count > 0 else 1
            self._log_verbose(f"Starting concurrent execution with {actual_workers} workers")

            # Execute tasks concurrently using ThreadPoolExecutor
            task_names = list(self.tasks.keys())
            failed_tasks = []
            completed_count = 0

            # Start progress bar
            if self.stdio and task_count > 0:
                progress_text = f"Running {self.check_target_type} checks"
                self.stdio.start_progressbar(progress_text, maxval=task_count, widget_type='simple_progress')

            with ThreadPoolExecutor(max_workers=actual_workers) as executor:
                # Submit all tasks
                future_to_task = {executor.submit(self.__execute_one_safe, task_name): task_name for task_name in task_names}

                # Collect results as they complete
                for future in as_completed(future_to_task):
                    task_name = future_to_task[future]
                    try:
                        t_report = future.result()
                        if t_report:
                            self.report.add_task_report(t_report)
                    except Exception as e:
                        failed_tasks.append(task_name)
                        self._log_error(f"Task {task_name} failed with exception: {e}")

                    # Update progress bar
                    completed_count += 1
                    if self.stdio:
                        self.stdio.update_progressbar(completed_count)

            # Finish progress bar
            if self.stdio:
                self.stdio.finish_progressbar()

            if failed_tasks:
                self._log_warn(f"The following tasks failed: {failed_tasks}")

            self.report.export_report()
            return self.report.report_tobeMap()
        except CheckReportException as e:
            self._log_error(f"Report error: {e}")
            # Ensure progress bar is finished even on error
            if self.stdio:
                self.stdio.finish_progressbar()
            raise CheckException(f"Report error: {e}")
        except Exception as e:
            # Ensure progress bar is finished even on error
            if self.stdio:
                self.stdio.finish_progressbar()
            raise CheckException(f"Internal error: {e}")
        finally:
            # Ensure progress bar is finished
            if self.stdio:
                self.stdio.finish_progressbar()
            # Cleanup: close SSH connections
            self.__cleanup()

    def __execute_one_safe(self, task_name):
        """Thread-safe wrapper for __execute_one that catches exceptions."""
        try:
            return self.__execute_one(task_name)
        except Exception as e:
            self._log_error(f"execute_one_safe Exception for task {task_name}: {e}")
            # Return a failed report instead of raising
            report = TaskReport(self.context, task_name)
            report.add_fail(f"Task execution failed: {str(e)}")
            return report

    def __get_current_os(self):
        """
        Get the current operating system type.
        Returns: 'linux', 'darwin' (macOS), or 'unknown'
        """
        import platform

        system = platform.system().lower()
        if system == "linux":
            return "linux"
        elif system == "darwin":
            return "darwin"
        else:
            return "unknown"

    def __cleanup(self):
        """Cleanup all resources after check execution."""
        try:
            # Return SSH connections to pool if using connection manager
            if hasattr(self, 'ssh_manager') and self.ssh_manager and self.nodes:
                for node in self.nodes:
                    ssher = node.get("ssher")
                    if ssher:
                        self.ssh_manager.return_connection(ssher)
            else:
                # Note: If SSH connections were created per-task, they are cleaned up in __execute_one
                # No additional cleanup needed here for task-specific connections
                pass
            self._log_verbose("Check execution cleanup completed")
        except Exception as e:
            self._log_warn(f"Cleanup error: {e}")


class CheckOBConnectorPool:
    """Connection pool for OceanBase database connections."""

    def __init__(self, context, max_size, cluster):
        self.max_size = max_size
        self.cluster = cluster
        self.connections = queue.Queue(maxsize=max_size)
        self.stdio = context.stdio
        self.stdio.verbose("CheckOBConnectorPool init success!")
        try:
            for i in range(max_size):
                conn = OBConnector(context=context, ip=self.cluster.get("db_host"), port=self.cluster.get("db_port"), username=self.cluster.get("tenant_sys").get("user"), password=self.cluster.get("tenant_sys").get("password"), timeout=10000)
                self.connections.put(conn)
            self.stdio.verbose("CheckOBConnectorPool init success!")
        except Exception as e:
            self.stdio.error("CheckOBConnectorPool init fail! err: {0}".format(e))

    def get_connection(self):
        """Get a connection from the pool."""
        try:
            return self.connections.get()
        except Exception as e:
            self.stdio.error("get connection fail! err: {0}".format(e))
            return None

    def release_connection(self, conn):
        """Release a connection back to the pool."""
        if conn is not None:
            self.connections.put(conn)
        return
