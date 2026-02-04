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
@time: 2024/08/31
@file: display_scene.py
@desc:
"""

import re
from src.common.base_handler import BaseHandler
from src.common.result_type import ObdiagResult
import datetime
from src.handler.display.scenes.base import SceneBase
from src.common.obdiag_exception import OBDIAGFormatException
from src.handler.display.scenes.list import DisplayScenesListHandler
from src.common.tool import StringUtils
from src.common.scene import get_version_by_type
from src.common.tool import Util
from src.common.tool import TimeUtils
from src.common.ob_connector import OBConnector


class DisplaySceneHandler(BaseHandler):

    def _init(self, display_pack_dir='./', tasks_base_path="~/.obdiag/display/tasks/", task_type="observer", is_inner=False, **kwargs):
        """Subclass initialization"""
        self.is_ssh = True
        self.report = None
        self.display_pack_dir = display_pack_dir
        self.yaml_tasks = {}
        self.code_tasks = []
        self.env = {}
        self.scene = "observer.base"
        self.tasks_base_path = tasks_base_path
        self.task_type = task_type
        self.variables = {}
        self.is_inner = is_inner
        self.temp_dir = '/tmp'

        if self.context.get_variable("display_timestamp", None):
            self.display_timestamp = self.context.get_variable("display_timestamp")
        else:
            self.display_timestamp = TimeUtils.get_current_us_timestamp()

        # Initialize config
        self.cluster = self.context.cluster_config
        self.sys_connector = OBConnector(context=self.context, ip=self.cluster.get("db_host"), port=self.cluster.get("db_port"), username=self.cluster.get("tenant_sys").get("user"), password=self.cluster.get("tenant_sys").get("password"), timeout=100)
        self.obproxy_nodes = self.context.obproxy_config['servers']
        self.ob_nodes = self.context.cluster_config['servers']
        new_nodes = Util.get_nodes_list(self.context, self.ob_nodes, self.stdio)
        if new_nodes:
            self.nodes = new_nodes

    def handle(self) -> ObdiagResult:
        """Main handle logic"""
        self._validate_initialized()

        try:
            if not self.init_option():
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="init option failed")
            self.context.set_variable('temp_dir', self.temp_dir)
            self.__init_variables()
            self.__init_task_names()
            data = self.execute()
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"display_data": data})

        except Exception as e:
            return self._handle_error(e)

    def execute(self):
        try:
            return_data = ""
            self._log_verbose(f"execute_tasks. the number of tasks is {len(self.yaml_tasks.keys())} ,tasks is {self.yaml_tasks.keys()}")
            for key, value in zip(self.yaml_tasks.keys(), self.yaml_tasks.values()):
                data = self.__execute_yaml_task_one(key, value)
                if isinstance(data, str):
                    return_data = f"{return_data}\n{data}"
                elif isinstance(data, ObdiagResult):
                    return data
            # Execute code tasks (Python-based tasks)
            # Note: code_tasks are executed after yaml_tasks, and their results are not included in return_data
            # This is intentional - code tasks typically perform actions (like gathering data) rather than returning display data
            for task in self.code_tasks:
                self.__execute_code_task_one(task)
            return return_data
        except Exception as e:
            self._log_error(f"Internal error :{e}")

    def __init_db_connector(self):
        self.db_connector = OBConnector(context=self.context, ip=self.db_conn.get("host"), port=self.db_conn.get("port"), username=self.db_conn.get("user"), password=self.db_conn.get("password"), database=self.db_conn.get("database"), timeout=100)

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
                    return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="get cluster.version failed")
                task = SceneBase(context=self.context, scene=task_data["task"], env=self.env, scene_variable_dict=self.variables, task_type=task_type, db_connector=self.db_connector)
                self._log_verbose(f"{task_name} execute!")
                data = task.execute()
                self._log_verbose(f"execute tasks end : {task_name}")
                return str(data)
            else:
                self._log_error("can't get version")
                return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="can't get version")
        except Exception as e:
            self._log_error(f"__execute_yaml_task_one Exception : {e}")
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data=f"__execute_yaml_task_one Exception : {e}")

    # execute code task
    def __execute_code_task_one(self, task_name):
        try:
            self._log_verbose(f"execute tasks is {task_name}")
            scene = {"name": task_name}
            task = SceneBase(context=self.context, scene=scene, env=self.env, mode='code', task_type=task_name, db_connector=self.db_connector)
            self._log_verbose(f"{task_name} execute!")
            data = task.execute()
            self._log_verbose(f"execute tasks end : {task_name}")
            return data
        except Exception as e:
            self._log_error(f"__execute_code_task_one Exception : {e}")
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data=f"__execute_code_task_one Exception : {e}")

    def __init_task_names(self):
        if self.scene:
            new = re.sub(r'\{|\}', '', self.scene)
            items = re.split(r'[;,]', new)
            # Use new BaseHandler initialization pattern
            scene = DisplayScenesListHandler()
            scene.init(self.context)
            for item in items:
                yaml_task_data = scene.get_one_yaml_task(item)
                is_code_task = scene.is_code_task(item)
                if is_code_task:
                    self.code_tasks.append(item)
                else:
                    if yaml_task_data:
                        self.yaml_tasks[item] = yaml_task_data
                    else:
                        self._log_error(f"Invalid Task :{item}")
            # hard code add display observer.base
            if len(self.code_tasks) > 0:
                yaml_task_base = scene.get_one_yaml_task("observer.base")
                self.yaml_tasks["observer.base"] = yaml_task_base
        else:
            self._log_error("get task name failed")
            return False

    def __init_variables(self):
        try:
            self.variables = {
                "observer_data_dir": self.ob_nodes[0].get("home_path") if self.ob_nodes and self.ob_nodes[0].get("home_path") else "",
                "obproxy_data_dir": self.obproxy_nodes[0].get("home_path") if self.obproxy_nodes and self.obproxy_nodes[0].get("home_path") else "",
                "from_time": self.from_time_str,
                "to_time": self.to_time_str,
            }
            self._log_verbose(f"display scene variables: {self.variables}")
        except Exception as e:
            self._log_error(f"init display scene variables failed, error: {e}")
            return False

    def __get_task_type(self, s):
        trimmed_str = s.strip()
        if '.' in trimmed_str:
            parts = trimmed_str.split('.', 1)
            return parts[0]
        else:
            return None

    def init_option(self):
        from_option = self._get_option('from')
        to_option = self._get_option('to')
        since_option = self._get_option('since')
        env_option = self._get_option('env')
        scene_option = self._get_option('scene')
        temp_dir_option = self._get_option('temp_dir')

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
        else:
            self._log_info('No time option provided, default processing is based on the last 30 minutes')
            now_time = datetime.datetime.now()
            self.to_time_str = (now_time + datetime.timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S')
            if since_option:
                self.from_time_str = (now_time - datetime.timedelta(seconds=TimeUtils.parse_time_length_to_sec(since_option))).strftime('%Y-%m-%d %H:%M:%S')
            else:
                self.from_time_str = (now_time - datetime.timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')

        if scene_option:
            self.scene = scene_option
        if env_option:
            env_dict = StringUtils.parse_env_display(env_option)
            self.env = env_dict

            # Build db_info directly from env_dict parameters (no db_connect string parsing)
            db_conn = StringUtils.build_db_info_from_env(env_dict, self.stdio)
            if db_conn and StringUtils.validate_db_info(db_conn):
                self.db_conn = db_conn
                self.__init_db_connector()
            else:
                self._log_warn("db connection information not provided or invalid, using sys_connector")
                self.db_connector = self.sys_connector
        else:
            self.db_connector = self.sys_connector
        if temp_dir_option:
            self.temp_dir = temp_dir_option
        return True
