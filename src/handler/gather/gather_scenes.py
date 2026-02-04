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
@time: 2024/01/04
@file: gather_scene_handler.py
@desc:
"""

import os
import re
from src.common.base_handler import BaseHandler
from src.common.result_type import ObdiagResult
import datetime
from src.handler.gather.scenes.base import SceneBase
from src.common.obdiag_exception import OBDIAGFormatException
from src.handler.gather.scenes.list import GatherScenesListHandler
from src.common.tool import DirectoryUtil
from src.common.tool import StringUtils
from src.common.scene import get_version_by_type
from colorama import Fore, Style
from src.common.tool import Util
from src.common.tool import TimeUtils


class GatherSceneHandler(BaseHandler):

    def _init(self, gather_pack_dir='./', tasks_base_path="~/.obdiag/gather/tasks/", task_type="observer", is_inner=False, **kwargs):
        """Subclass initialization"""
        self.is_ssh = True
        self.report = None
        self.gather_pack_dir = gather_pack_dir
        self.report_path = None
        self.yaml_tasks = {}
        self.code_tasks = {}
        self.env = {}
        self.scene = "observer.base"
        self.tasks_base_path = tasks_base_path
        self.task_type = task_type
        self.variables = {}
        self.is_inner = is_inner
        self.temp_dir = '/tmp'

        if self.context.get_variable("gather_timestamp", None):
            self.gather_timestamp = self.context.get_variable("gather_timestamp")
        else:
            self.gather_timestamp = TimeUtils.get_current_us_timestamp()

        # Initialize config
        self.cluster = self.context.cluster_config
        self.obproxy_nodes = self.context.obproxy_config['servers']
        self.ob_nodes = self.context.cluster_config['servers']
        new_nodes = Util.get_nodes_list(self.context, self.ob_nodes, self.stdio)
        if new_nodes:
            self.nodes = new_nodes

        # Initialize options
        from_option = self._get_option('from')
        to_option = self._get_option('to')
        since_option = self._get_option('since')
        store_dir_option = self._get_option('store_dir')
        env_option = self._get_option('env')
        scene_option = self._get_option('scene')
        temp_dir_option = self._get_option('temp_dir')
        skip_type_option = self._get_option('skip_type')

        if from_option is not None and to_option is not None:
            try:
                from_timestamp = TimeUtils.parse_time_str(from_option)
                to_timestamp = TimeUtils.parse_time_str(to_option)
                self.from_time_str = from_option
                self.to_time_str = to_option
            except OBDIAGFormatException:
                raise ValueError(f'Error: Datetime is invalid. Must be in format yyyy-mm-dd hh:mm:ss. from_datetime={from_option}, to_datetime={to_option}')
            if to_timestamp <= from_timestamp:
                raise ValueError('Error: from datetime is larger than to datetime, please check.')
        elif (from_option is None or to_option is None) and since_option is not None:
            now_time = datetime.datetime.now()
            self.to_time_str = (now_time + datetime.timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
            self.from_time_str = (now_time - datetime.timedelta(seconds=TimeUtils.parse_time_length_to_sec(since_option))).strftime('%Y-%m-%d %H:%M:%S')
            self._log_info(f'gather from_time: {self.from_time_str}, to_time: {self.to_time_str}')
        else:
            self._log_info('No time option provided, default processing is based on the last 30 minutes')
            now_time = datetime.datetime.now()
            self.to_time_str = (now_time + datetime.timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
            if since_option:
                self.from_time_str = (now_time - datetime.timedelta(seconds=TimeUtils.parse_time_length_to_sec(since_option))).strftime('%Y-%m-%d %H:%M:%S')
            else:
                self.from_time_str = (now_time - datetime.timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
            self._log_info(f'gather from_time: {self.from_time_str}, to_time: {self.to_time_str}')

        if store_dir_option:
            if not os.path.exists(os.path.abspath(store_dir_option)):
                self._log_warn(f'args --store_dir [{os.path.abspath(store_dir_option)}] incorrect: No such directory, Now create it')
                os.makedirs(os.path.abspath(store_dir_option))
            self.gather_pack_dir = os.path.abspath(store_dir_option)
        
        # Use config work_path if available, otherwise use parameter or default
        # tasks_base_path is automatically derived from work_path + "tasks"
        if hasattr(self, 'config') and hasattr(self.config, 'gather_work_path'):
            work_path = self.config.gather_work_path
            self.tasks_base_path = os.path.join(work_path, "tasks")
        elif tasks_base_path == "~/.obdiag/gather/tasks/":
            # If using default, derive from work_path
            if hasattr(self, 'config') and hasattr(self.config, 'gather_work_path'):
                work_path = self.config.gather_work_path
                self.tasks_base_path = os.path.join(work_path, "tasks")
            else:
                self.tasks_base_path = tasks_base_path
        else:
            self.tasks_base_path = tasks_base_path

        if scene_option:
            self.scene = scene_option

        if env_option:
            env_dict = StringUtils.parse_env_display(env_option)
            self.env = env_dict
            self.context.set_variable("env", self.env)

        # Add from_time and to_time to env so they can be accessed by Python tasks
        if hasattr(self, 'from_time_str') and self.from_time_str:
            if self.env is None:
                self.env = {}
            self.env['from_time'] = self.from_time_str
        if hasattr(self, 'to_time_str') and self.to_time_str:
            if self.env is None:
                self.env = {}
            self.env['to_time'] = self.to_time_str
        if self.env:
            self.context.set_variable("env", self.env)

        if temp_dir_option:
            self.temp_dir = temp_dir_option

        if skip_type_option:
            self.context.set_variable('gather_skip_type', skip_type_option)

    def handle(self) -> ObdiagResult:
        """Main handle logic"""
        self._validate_initialized()

        try:
            self.context.set_variable('temp_dir', self.temp_dir)
            self.__init_variables()
            self.__init_report_path()
            self.__init_task_names()
            self.execute()
            if self.is_inner:
                result = self.__get_sql_result()
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"store_dir": self.report_path})
            else:
                self.__print_result()
                return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"store_dir": self.report_path})

        except Exception as e:
            return self._handle_error(e)

    def execute(self):
        try:
            self._log_verbose(f"execute_tasks. the number of tasks is {len(self.yaml_tasks.keys())} ,tasks is {self.yaml_tasks.keys()}")
            for key, value in zip(self.yaml_tasks.keys(), self.yaml_tasks.values()):
                self.__execute_yaml_task_one(key, value)
            for key, value in zip(self.code_tasks.keys(), self.code_tasks.values()):
                self.__execute_code_task_one(key, value)
        except Exception as e:
            self._log_error(f"Internal error :{e}")

    # execute yaml task
    def __execute_yaml_task_one(self, task_name, task_data):
        try:
            self._log_info(f"execute tasks: {task_name}")
            task_type = self.__get_task_type(task_name)
            version = get_version_by_type(self.context, task_type)
            if version:
                match = re.search(r'\d+(\.\d+){2}(?:\.\d+)?', version)
                if match:
                    self.cluster["version"] = match.group(0)
                else:
                    self._log_error("get cluster.version failed")
                    return
                task = SceneBase(context=self.context, scene=task_data["task"], report_dir=self.report_path, env=self.env, scene_variable_dict=self.variables, task_type=task_type)
                self._log_verbose(f"{task_name} execute!")
                task.execute()
                self._log_verbose(f"execute tasks end : {task_name}")
            else:
                self._log_error("can't get version")
        except Exception as e:
            self._log_error(f"__execute_yaml_task_one Exception : {e}")

    # execute code task
    def __execute_code_task_one(self, task_name, task_data):
        try:
            self._log_verbose(f"execute tasks is {task_name}")
            task = task_data["module"]
            task.init(self.context, task_name, self.report_path, self.variables, self.env)
            self._log_verbose(f"{task_name} execute!")
            task.execute()
            self._log_verbose(f"execute tasks end : {task_name}")
        except Exception as e:
            self._log_error(f"__execute_code_task_one Exception : {e}")

    def __init_task_names(self):
        if self.scene:
            new = re.sub(r'\{|\}', '', self.scene)
            items = re.split(r'[;,]', new)
            # Pass work_path to GatherScenesListHandler
            scene = GatherScenesListHandler(self.context, yaml_tasks_base_path=self.tasks_base_path)
            for item in items:
                task_data = scene.get_one_task(item)
                if task_data["task_type"] == 'py':
                    self.code_tasks[item] = task_data
                elif task_data["task_type"] == 'yaml':
                    self.yaml_tasks[item] = task_data
                else:
                    self._log_error(f"Invalid Task :{item}. Please check the task is exist.")
                    if ".yaml" in item:
                        self._log_info(f"'.yaml' in task :{item}. Maybe you can remove it. use '--scene={item.replace('.yaml', '')}'")
            # hard code add gather observer.base
            if len(self.code_tasks) > 0:
                self.yaml_tasks["observer.base"] = scene.get_one_task("observer.base")
        else:
            self._log_error("get task name failed")

    def __init_report_path(self):
        try:
            self.report_path = os.path.join(self.gather_pack_dir, f"obdiag_gather_{TimeUtils.timestamp_to_filename_time(self.gather_timestamp)}")
            self._log_verbose(f"Use {self.report_path} as pack dir.")
            DirectoryUtil.mkdir(path=self.report_path, stdio=self.stdio)
        except Exception as e:
            self._log_error(f"init_report_path failed, error:{e}")

    def __init_variables(self):
        try:
            self.variables = {
                "observer_data_dir": self.ob_nodes[0].get("home_path") if self.ob_nodes and self.ob_nodes[0].get("home_path") else "",
                "obproxy_data_dir": self.obproxy_nodes[0].get("home_path") if self.obproxy_nodes and self.obproxy_nodes[0].get("home_path") else "",
                "from_time": self.from_time_str,
                "to_time": self.to_time_str,
            }
            self._log_verbose(f"gather scene variables: {self.variables}")
        except Exception as e:
            self._log_error(f"init gather scene variables failed, error: {e}")

    def __get_task_type(self, s):
        trimmed_str = s.strip()
        if '.' in trimmed_str:
            parts = trimmed_str.split('.', 1)
            return parts[0]
        else:
            return None

    def __get_sql_result(self):
        try:
            file_path = os.path.join(self.report_path, "sql_result.txt")
            with open(file_path, 'r', encoding='utf-8') as f:
                data = f.read()
            return data
        except Exception as e:
            self._log_error(str(e))
            return None

    def __print_result(self):
        if self.context.get_variable("adapted_version", default=True) == True:
            self._log_info(Fore.YELLOW + f"\nGather scene results stored in this directory: {self.report_path}\n" + Style.RESET_ALL)
        return self.report_path
