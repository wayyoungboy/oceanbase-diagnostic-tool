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
@file: core.py
@desc: Lightweight entry coordinator that delegates to specialized managers.
       Refactored from the original God Object (791 lines, 30+ methods).
"""

from __future__ import absolute_import, division, print_function

import os
import traceback
from optparse import Values
from copy import copy

from src.common.ssh_client.remote_client import dis_rsa_algorithms
from src.common.ssh import SshClient, SshConfig
from src.common.context import HandlerContextNamespace, HandlerContext
from src.common.config import ConfigManager, InnerConfigManager
from src.common.context_manager import ContextManager
from src.common.handler_factory import HandlerFactory
from src.common.err import CheckStatus, SUG_SSH_FAILED
from src.common.result_type import ObdiagResult
from src.telemetry.telemetry import telemetry
from colorama import Fore, Style
from src.common.tool import TimeUtils, Util
from src.common.command import get_observer_version_by_sql
from src.common.ob_connector import OBConnector


# ============================================================================
# Handler registration table: maps command names to (module_path, class_name)
# This replaces the 50+ explicit imports in the original code.
# ============================================================================
_HANDLER_MAP = {
    # --- Gather ---
    'gather_log': ('src.handler.gather.gather_component_log', 'GatherComponentLogHandler'),
    'gather_awr': ('src.handler.gather.gather_awr', 'GatherAwrHandler'),
    'gather_clog': ('src.handler.gather.gather_obadmin', 'GatherObAdminHandler'),
    'gather_slog': ('src.handler.gather.gather_obadmin', 'GatherObAdminHandler'),
    'gather_obstack': ('src.handler.gather.gather_obstack2', 'GatherObstack2Handler'),
    'gather_perf': ('src.handler.gather.gather_perf', 'GatherPerfHandler'),
    'gather_plan_monitor': ('src.handler.gather.gather_plan_monitor', 'GatherPlanMonitorHandler'),
    'gather_sysstat': ('src.handler.gather.gather_sysstat', 'GatherOsInfoHandler'),
    'gather_scenes_run': ('src.handler.gather.gather_scenes', 'GatherSceneHandler'),
    'gather_ash_report': ('src.handler.gather.gather_ash_report', 'GatherAshReportHandler'),
    'gather_tabledump': ('src.handler.gather.gather_tabledump', 'GatherTableDumpHandler'),
    'gather_parameters': ('src.handler.gather.gather_parameters', 'GatherParametersHandler'),
    'gather_variables': ('src.handler.gather.gather_variables', 'GatherVariablesHandler'),
    'gather_dbms_xplan': ('src.handler.gather.gather_dbms_xplan', 'GatherDBMSXPLANHandler'),
    'gather_core': ('src.handler.gather.gather_core', 'GatherCoreHandler'),
    # --- Analyze ---
    'analyze_log': ('src.handler.analyzer.analyze_log', 'AnalyzeLogHandler'),
    'analyze_log_offline': ('src.handler.analyzer.analyze_log', 'AnalyzeLogHandler'),
    'analyze_queue': ('src.handler.analyzer.analyze_queue', 'AnalyzeQueueHandler'),
    'analyze_flt_trace': ('src.handler.analyzer.analyze_flt_trace', 'AnalyzeFltTraceHandler'),
    'analyze_parameter_default': ('src.handler.analyzer.analyze_parameter', 'AnalyzeParameterHandler'),
    'analyze_parameter_diff': ('src.handler.analyzer.analyze_parameter', 'AnalyzeParameterHandler'),
    'analyze_variable_diff': ('src.handler.analyzer.analyze_variable', 'AnalyzeVariableHandler'),
    'analyze_sql': ('src.handler.analyzer.analyze_sql', 'AnalyzeSQLHandler'),
    'analyze_sql_review': ('src.handler.analyzer.analyze_sql_review', 'AnalyzeSQLReviewHandler'),
    'analyze_index_space': ('src.handler.analyzer.analyze_index_space', 'AnalyzeIndexSpaceHandler'),
    'analyze_memory': ('src.handler.analyzer.analyze_memory', 'AnalyzeMemoryHandler'),
    'analyze_memory_offline': ('src.handler.analyzer.analyze_memory', 'AnalyzeMemoryHandler'),
    # --- Check ---
    'check': ('src.handler.check.check_handler', 'CheckHandler'),
    'check_list': ('src.handler.check.check_list', 'CheckListHandler'),
    # --- Display ---
    'display_scenes_run': ('src.handler.display.display_scenes', 'DisplaySceneHandler'),
    'display_scenes_list': ('src.handler.display.scenes.list', 'DisplayScenesListHandler'),
    # --- RCA ---
    'rca_run': ('src.handler.rca.rca_handler', 'RCAHandler'),
    'rca_list': ('src.handler.rca.rca_list', 'RcaScenesListHandler'),
    # --- Tools ---
    'tool_crypto_config': ('src.handler.tools.crypto_config_handler', 'CryptoConfigHandler'),
    'tool_ai_assistant': ('src.handler.ai.ai_assistant_handler', 'AiAssistantHandler'),
    'tool_config_check': ('src.handler.tools.config_check_handler', 'ConfigCheckHandler'),
    'tool_io_performance': ('src.handler.tools.io_performance_handler', 'IoPerformanceHandler'),
    # --- Update ---
    'update': ('src.handler.update.update', 'UpdateHandler'),
    # --- Misc ---
    'gather_scenes_list': ('src.handler.gather.scenes.list', 'GatherScenesListHandler'),
}

# Commands that need update_obcluster_nodes before execution
_NEEDS_NODE_UPDATE = {
    'gather_log',
    'gather_awr',
    'gather_clog',
    'gather_slog',
    'gather_obstack',
    'gather_perf',
    'gather_plan_monitor',
    'gather_all',
    'gather_sysstat',
    'gather_scenes_run',
    'gather_ash_report',
    'gather_tabledump',
    'gather_parameters',
    'gather_variables',
    'gather_dbms_xplan',
    'gather_core',
    'analyze_log',
    'analyze_flt_trace',
    'analyze_memory',
    'check',
    'display_scenes_run',
}

# Commands that skip cluster connection
_SKIP_CLUSTER_CONN = {
    'gather_obproxy_log',
    'gather_oms_log',
    'analyze_log_offline',
    'analyze_parameter_diff',
    'analyze_memory_offline',
    'tool_config_check',
}

# Commands that are offline (no config needed for context)
_OFFLINE_COMMANDS = {
    'check_list',
    'rca_list',
    'display_scenes_list',
    'gather_scenes_list',
    'update',
    'tool_crypto_config',
    'tool_ai_assistant',
}


def _lazy_import(module_path, class_name):
    """Lazily import a handler class to avoid loading all handlers at startup."""
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class ObdiagHome(object):
    """
    Lightweight entry coordinator that delegates to specialized managers.

    Responsibilities:
    - Configuration loading and validation
    - Context creation (via ContextManager)
    - Handler dispatch (via lazy import + handler map)
    - Backward-compatible API surface
    """

    def __init__(self, stdio=None, config_path=os.path.expanduser('~/.obdiag/config.yml'), inner_config_change_map=None, custom_config_env_list=None, config_password=None):
        self._optimize_manager = None
        self.stdio = None
        self._stdio_func = None
        self.cmds = []
        self.options = Values()
        self.namespaces = {}
        self.set_stdio(stdio)
        self.context = None

        # --- Managers ---
        self.inner_config_manager = InnerConfigManager(stdio=stdio, inner_config_change_map=inner_config_change_map)
        self._apply_inner_config(stdio)
        self.config_manager = ConfigManager(config_path, stdio, custom_config_env_list, config_password=config_password)

        # --- Context Manager (new) ---
        self.context_mgr = ContextManager(
            stdio=self.stdio,
            config_manager=self.config_manager,
            inner_config_manager=self.inner_config_manager,
        )

    # ====================================================================
    # Private helpers
    # ====================================================================

    def _apply_inner_config(self, stdio):
        """Apply inner configuration settings (error stream, silent, telemetry, RSA)."""
        ic = self.inner_config_manager.config
        obdiag = ic.get("obdiag") if ic else None
        if not obdiag:
            self.set_stdio(stdio)
            return

        basic = obdiag.get("basic", {})
        logger = obdiag.get("logger", {})

        # error stream
        if logger.get("error_stream") is not None:
            stdio.set_err_stream(logger["error_stream"])
        # silent mode
        if logger.get("silent") is not None:
            stdio.set_silent(logger["silent"])

        self.set_stdio(stdio)

        # telemetry
        tel_val = basic.get("telemetry")
        if tel_val is False or (isinstance(tel_val, str) and "false" in tel_val.lower()):
            telemetry.work_tag = False

        # RSA algorithms
        if basic.get("dis_rsa_algorithms") is not None:
            dis_rsa_algorithms(basic["dis_rsa_algorithms"])

    def _require_config(self, config):
        if not config:
            self._call_stdio('error', 'No such custom config')
            return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data='No such custom config')
        return None

    def _create_handler(self, command_name):
        """Create handler instance by command name using lazy import."""
        entry = _HANDLER_MAP.get(command_name)
        if not entry:
            raise ValueError(f"Unknown command: {command_name}")
        module_path, class_name = entry
        handler_class = _lazy_import(module_path, class_name)
        return handler_class()

    def _setup_context(self, command_name, namespace):
        """Setup context for a command, handling node updates and cluster connection."""
        config = self.config_manager

        if command_name in _OFFLINE_COMMANDS:
            self.set_offline_context(command_name, namespace)
        elif command_name in _SKIP_CLUSTER_CONN:
            self.set_context_skip_cluster_conn(command_name, namespace, config)
        else:
            self.set_context_stdio()
            if command_name in _NEEDS_NODE_UPDATE:
                self.update_obcluster_nodes(config)
            self.set_context(command_name, namespace, config)

    # ====================================================================
    # Unified execution entry point (new)
    # ====================================================================

    def execute(self, command_name, namespace='default', init_kwargs=None):
        """
        Unified command execution entry point.

        Args:
            command_name: Command name (e.g. 'gather_log', 'check', 'rca_run')
            namespace: Namespace for the context
            init_kwargs: Additional kwargs for handler.init()

        Returns:
            ObdiagResult
        """
        config = self.config_manager
        if command_name not in _OFFLINE_COMMANDS:
            error_result = self._require_config(config)
            if error_result:
                return error_result

        try:
            if not self.stdio.silent and command_name not in _OFFLINE_COMMANDS:
                self.stdio.print(f"{command_name} start ...")

            self._setup_context(command_name, namespace)

            handler = self._create_handler(command_name)
            handler.init(self.context, **(init_kwargs or {}))
            return handler.handle()

        except Exception as e:
            self.stdio.error(f"{command_name} Exception: {e}")
            self.stdio.verbose(traceback.format_exc())
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data=f"{command_name} Exception: {e}")

    # ====================================================================
    # Backward-compatible public API (delegates to execute or legacy logic)
    # ====================================================================

    def gather_function(self, function_type, opt):
        config = self.config_manager
        error_result = self._require_config(config)
        if error_result:
            return error_result

        if not self.stdio.silent:
            self.stdio.print("{0} start ...".format(function_type))

        self.set_context_stdio()
        self.update_obcluster_nodes(config)
        self.set_context(function_type, 'gather', config)
        options = self.context.options
        timestamp = TimeUtils.get_current_us_timestamp()
        self.context.set_variable('gather_timestamp', timestamp)

        if function_type == 'gather_log':
            handler = self._create_handler('gather_log')
            handler.init(
                self.context,
                target="observer",
                from_option=Util.get_option(options, 'from'),
                to_option=Util.get_option(options, 'to'),
                since=Util.get_option(options, 'since'),
                scope=Util.get_option(options, 'scope'),
                grep=Util.get_option(options, 'grep'),
                store_dir=Util.get_option(options, 'store_dir'),
                temp_dir=Util.get_option(options, 'temp_dir'),
                redact=Util.get_option(options, 'redact'),
                recent_count=Util.get_option(options, 'recent_count'),
            )
            return handler.handle()

        elif function_type in ('gather_clog', 'gather_slog'):
            mode = 'clog' if function_type == 'gather_clog' else 'slog'
            self.context.set_variable('gather_obadmin_mode', mode)
            handler = self._create_handler(function_type)
            handler.init(self.context)
            return handler.handle()

        elif function_type == 'gather_all':
            return self._gather_all(options)

        elif function_type in _HANDLER_MAP:
            handler = self._create_handler(function_type)
            handler.init(self.context)
            return handler.handle()

        else:
            self._call_stdio('error', 'Not support gather function: {0}'.format(function_type))
            return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data='Not support gather function: {0}'.format(function_type))

    def _gather_all(self, options):
        """Run all gather operations."""
        for cmd, kwargs in [
            ('gather_sysstat', {}),
            ('gather_obstack', {}),
            ('gather_perf', {}),
        ]:
            try:
                handler = self._create_handler(cmd)
                handler.init(self.context, **kwargs)
                handler.handle()
            except Exception as e:
                self.stdio.error(f"{cmd} failed: {e}")

        for target in ["observer", "obproxy"]:
            try:
                handler = self._create_handler('gather_log')
                handler.init(
                    self.context,
                    target=target,
                    from_option=Util.get_option(options, 'from'),
                    to_option=Util.get_option(options, 'to'),
                    since=Util.get_option(options, 'since'),
                    grep=Util.get_option(options, 'grep'),
                    store_dir=Util.get_option(options, 'store_dir'),
                    temp_dir=Util.get_option(options, 'temp_dir'),
                    redact=Util.get_option(options, 'redact'),
                    recent_count=Util.get_option(options, 'recent_count'),
                )
                return handler.handle()
            except Exception as e:
                self.stdio.error(f"gather_{target}_log failed: {e}")

    def gather_obproxy_log(self, opt):
        config = self.config_manager
        error_result = self._require_config(config)
        if error_result:
            return error_result
        self.set_context_skip_cluster_conn('gather_obproxy_log', 'gather', config)
        options = self.context.options
        handler = self._create_handler('gather_log')
        handler.init(
            self.context,
            target="obproxy",
            from_option=Util.get_option(options, 'from'),
            to_option=Util.get_option(options, 'to'),
            since=Util.get_option(options, 'since'),
            scope=Util.get_option(options, 'scope'),
            grep=Util.get_option(options, 'grep'),
            store_dir=Util.get_option(options, 'store_dir'),
            temp_dir="/tmp",
            redact=Util.get_option(options, 'redact'),
            recent_count=Util.get_option(options, 'recent_count'),
        )
        return handler.handle()

    def gather_oms_log(self, opt):
        config = self.config_manager
        error_result = self._require_config(config)
        if error_result:
            return error_result
        self.set_context_skip_cluster_conn('gather_oms_log', 'gather', config)
        options = self.context.options
        handler = self._create_handler('gather_log')
        handler.init(
            self.context,
            target="oms",
            from_option=Util.get_option(options, 'from'),
            to_option=Util.get_option(options, 'to'),
            since=Util.get_option(options, 'since'),
            scope=Util.get_option(options, 'scope'),
            grep=Util.get_option(options, 'grep'),
            store_dir=Util.get_option(options, 'store_dir'),
            temp_dir=Util.get_option(options, 'temp_dir'),
            redact=Util.get_option(options, 'redact'),
            recent_count=Util.get_option(options, 'recent_count'),
            oms_component_id=Util.get_option(options, 'oms_component_id'),
        )
        return handler.handle()

    def gather_scenes_list(self, opt):
        self.set_offline_context('gather_scenes_list', 'gather')
        work_path = None
        if hasattr(self, 'inner_config_manager') and self.inner_config_manager:
            work_path = self.inner_config_manager.config.get("gather", {}).get("work_path")
        if not work_path:
            work_path = "~/.obdiag/gather"
        tasks_path = os.path.join(work_path, "tasks")
        handler_class = _lazy_import('src.handler.gather.scenes.list', 'GatherScenesListHandler')
        handler = handler_class(self.context, yaml_tasks_base_path=tasks_path)
        return handler.handle()

    def display_function(self, function_type, opt):
        config = self.config_manager
        error_result = self._require_config(config)
        if error_result:
            return error_result
        if not self.stdio.silent:
            self.stdio.print("{0} start ...".format(function_type))
        self.set_context_stdio()
        self.update_obcluster_nodes(config)
        self.set_context(function_type, 'display', config)
        timestamp = TimeUtils.get_current_us_timestamp()
        self.context.set_variable('display_timestamp', timestamp)
        if function_type == 'display_scenes_run':
            handler = self._create_handler('display_scenes_run')
            handler.init(self.context)
            return handler.handle()
        else:
            self._call_stdio('error', 'Not support display function: {0}'.format(function_type))
            return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data='Not support display function: {0}'.format(function_type))

    def display_scenes_list(self, opt):
        return self.execute('display_scenes_list', 'display')

    def analyze_fuction(self, function_type, opt):
        config = self.config_manager
        error_result = self._require_config(config)
        if error_result:
            return error_result
        if not self.stdio.silent:
            self.stdio.print("{0} start ...".format(function_type))

        # Determine init kwargs for specific analyze types
        init_kwargs = {}
        if function_type == 'analyze_parameter_default':
            init_kwargs = {'analyze_type': 'default'}
        elif function_type == 'analyze_parameter_diff':
            init_kwargs = {'analyze_type': 'diff'}
        elif function_type == 'analyze_variable_diff':
            init_kwargs = {'analyze_type': 'diff'}

        # Setup context based on command type
        skip_cluster = function_type in _SKIP_CLUSTER_CONN
        needs_nodes = function_type in _NEEDS_NODE_UPDATE

        if skip_cluster:
            self.set_context_skip_cluster_conn(function_type, 'analyze', config)
        else:
            if needs_nodes:
                self.set_context_stdio()
                self.update_obcluster_nodes(config)
            self.set_context(function_type, 'analyze', config)

        if function_type in _HANDLER_MAP:
            handler = self._create_handler(function_type)
            handler.init(self.context, **init_kwargs)
            return handler.handle()
        else:
            self._call_stdio('error', 'Not support analyze function: {0}'.format(function_type))
            return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data='Not support analyze function: {0}'.format(function_type))

    def check(self, opts):
        config = self.config_manager
        error_result = self._require_config(config)
        if error_result:
            return error_result
        try:
            if not self.stdio.silent:
                self.stdio.print("check start ...")
            self.set_context_stdio()
            self.update_obcluster_nodes(config)
            self.set_context('check', 'check', config)
            obproxy_check_handler = None
            observer_check_handler = None
            result_data = {}

            if self.context.obproxy_config.get("servers") is not None and len(self.context.obproxy_config.get("servers")) > 0:
                obproxy_check_handler = self._create_handler('check')
                obproxy_check_handler.init(self.context, check_target_type="obproxy")
                obproxy_result = obproxy_check_handler.handle()
                if isinstance(obproxy_result, ObdiagResult):
                    result_data['obproxy'] = obproxy_result.data if obproxy_result.data else {}
                else:
                    result_data['obproxy'] = obproxy_result

            if self.context.cluster_config.get("servers") is not None and len(self.context.cluster_config.get("servers")) > 0:
                observer_check_handler = self._create_handler('check')
                observer_check_handler.init(self.context, check_target_type="observer")
                observer_result = observer_check_handler.handle()
                if isinstance(observer_result, ObdiagResult):
                    result_data['observer'] = observer_result.data if observer_result.data else {}
                else:
                    result_data['observer'] = observer_result

            if obproxy_check_handler is not None and hasattr(obproxy_check_handler, 'report') and obproxy_check_handler.report:
                obproxy_report_path = os.path.expanduser(obproxy_check_handler.report.get_report_path())
                if os.path.exists(obproxy_report_path):
                    result_data['obproxy_report_path'] = os.path.abspath(obproxy_report_path)
                    if not self.stdio.silent:
                        self.stdio.print("Check obproxy finished. For more details, please run cmd '" + Fore.YELLOW + " cat {0} ".format(obproxy_check_handler.report.get_report_path()) + Style.RESET_ALL + "'")

            if observer_check_handler is not None and hasattr(observer_check_handler, 'report') and observer_check_handler.report:
                observer_report_path = os.path.expanduser(observer_check_handler.report.get_report_path())
                if os.path.exists(observer_report_path):
                    result_data['observer_report_path'] = os.path.abspath(observer_report_path)
                    if not self.stdio.silent:
                        self.stdio.print("Check observer finished. For more details, please run cmd'" + Fore.YELLOW + " cat {0} ".format(observer_check_handler.report.get_report_path()) + Style.RESET_ALL + "'")

            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data=result_data)
        except Exception as e:
            self.stdio.error("check Exception: {0}".format(e))
            self.stdio.verbose(traceback.format_exc())
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="check Exception: {0}".format(e))

    def check_list(self, opts):
        return self.execute('check_list', 'check_list')

    def rca_run(self, opts):
        config = self.config_manager
        error_result = self._require_config(config)
        if error_result:
            return error_result
        self.set_context('rca_run', 'rca_run', config)
        if config.get_ob_cluster_config.get("db_host") is not None and config.get_ob_cluster_config.get("servers") is not None:
            self.update_obcluster_nodes(config)
        try:
            handler = self._create_handler('rca_run')
            handler.init(self.context)
            return handler.handle()
        except Exception as e:
            self.stdio.error("rca run Exception: {0}".format(e))
            self.stdio.verbose(traceback.format_exc())
            return ObdiagResult(ObdiagResult.SERVER_ERROR_CODE, error_data="rca run Exception: {0}".format(e))

    def rca_list(self, opts):
        return self.execute('rca_list', 'rca_list')

    def update(self, opts):
        config = self.config_manager
        error_result = self._require_config(config)
        if error_result:
            return error_result
        if not self.stdio.silent:
            self.stdio.print("update start ...")
        self.set_offline_context('update', 'update')
        handler = self._create_handler('update')
        handler.init(self.context)
        handler.__class__.context = self.context
        return handler.handle()

    def tool_crypto_config(self, opt):
        return self.execute('tool_crypto_config', 'tool_crypto_config')

    def tool_ai_assistant(self, opt):
        config = self.config_manager
        if not config:
            self._call_stdio('error', 'No such custom config')
            return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data='No such custom config')
        return self.execute('tool_ai_assistant', 'tool_ai_assistant')

    def tool_config_check(self, opt):
        config = self.config_manager
        if not config:
            self._call_stdio('error', 'No such custom config')
            return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data='No such custom config')
        self.set_context_skip_cluster_conn('tool_config_check', 'tool_config_check', config)
        handler = self._create_handler('tool_config_check')
        handler.init(self.context)
        return handler.handle()

    def tool_io_performance(self, opt):
        config = self.config_manager
        if not config:
            self._call_stdio('error', 'No such custom config')
            return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data='No such custom config')
        self.set_context('tool_io_performance', 'tool_io_performance', config)
        handler = self._create_handler('tool_io_performance')
        handler.init(self.context)
        return handler.handle()

    def config(self, opt):
        config = self.config_manager
        error_result = self._require_config(config)
        if error_result:
            return error_result
        self.set_offline_context('config', 'config')
        from src.common.config_helper import ConfigHelper

        config_helper = ConfigHelper(context=self.context)
        if Util.get_option(opt, 'file'):
            try:
                config_helper.build_configuration_by_file(Util.get_option(opt, ''))
            except Exception as e:
                self._call_stdio('error', 'Build configuration by ini file failed: {0}'.format(e))
                return ObdiagResult(ObdiagResult.INPUT_ERROR_CODE, error_data='Build configuration by ini file failed: {0}'.format(e))
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"msg": "config success"})
        config_helper.build_configuration()
        return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"msg": "config success"})

    # ====================================================================
    # Infrastructure methods (kept for backward compatibility)
    # ====================================================================

    def fork(self, cmds=None, options=None, stdio=None):
        new_obdiag = copy(self)
        if cmds:
            new_obdiag.set_cmds(cmds)
        if options:
            new_obdiag.set_options(options)
        if stdio:
            new_obdiag.set_stdio(stdio)
        return new_obdiag

    def set_cmds(self, cmds):
        self.cmds = cmds

    def set_options(self, options):
        self.options = options

    def set_stdio(self, stdio):
        def _print(msg, *arg, **kwarg):
            sep = kwarg['sep'] if 'sep' in kwarg else None
            end = kwarg['end'] if 'end' in kwarg else None
            return print(msg, sep='' if sep is None else sep, end='\n' if end is None else end)

        self.stdio = stdio
        self._stdio_func = {}
        if not self.stdio:
            return
        for func in ['start_loading', 'stop_loading', 'print', 'confirm', 'verbose', 'warn', 'exception', 'error', 'critical', 'print_list', 'read']:
            self._stdio_func[func] = getattr(self.stdio, func, _print)

    def set_context_stdio(self):
        self.context = HandlerContext(stdio=self.stdio)

    def set_context(self, handler_name, namespace, config):
        self.context = HandlerContext(
            handler_name=handler_name,
            namespace=namespace,
            cluster_config=config.get_ob_cluster_config,
            obproxy_config=config.get_obproxy_config,
            ocp_config=config.get_ocp_config,
            oms_config=config.get_oms_config,
            cmd=self.cmds,
            options=self.options,
            stdio=self.stdio,
            inner_config=self.inner_config_manager.config,
        )
        telemetry.set_cluster_conn(self.context, config.get_ob_cluster_config)

    def set_context_skip_cluster_conn(self, handler_name, namespace, config):
        self.context = HandlerContext(
            handler_name=handler_name,
            namespace=namespace,
            cluster_config=config.get_ob_cluster_config,
            obproxy_config=config.get_obproxy_config,
            ocp_config=config.get_ocp_config,
            oms_config=config.get_oms_config,
            cmd=self.cmds,
            options=self.options,
            stdio=self.stdio,
            inner_config=self.inner_config_manager.config,
        )

    def set_offline_context(self, handler_name, namespace):
        self.context = HandlerContext(
            handler_name=handler_name,
            namespace=namespace,
            cmd=self.cmds,
            options=self.options,
            stdio=self.stdio,
            inner_config=self.inner_config_manager.config,
        )

    def update_obcluster_nodes(self, config):
        config_data = config.config_data
        cluster_config = config_data.get("obcluster", {})
        lst = Util.get_option(self.options, 'config')
        if lst and any(item.startswith('obcluster.servers.nodes') for item in lst):
            self.stdio.verbose("You have already provided node information, so there is no need to query node information from the sys tenant")
            return
        ob_cluster = {
            "db_host": cluster_config.get("db_host"),
            "db_port": cluster_config.get("db_port"),
            "tenant_sys": {
                "user": cluster_config.get("tenant_sys", {}).get("user"),
                "password": cluster_config.get("tenant_sys", {}).get("password"),
            },
        }
        if not ob_cluster["db_host"] or not ob_cluster["db_port"] or not ob_cluster["tenant_sys"]["user"]:
            raise ValueError("Missing required configuration values in ob_cluster or tenant_sys (excluding password)")
        if config_data.get('obcluster') and config_data.get('obcluster').get('servers') and config_data.get('obcluster').get('servers').get('nodes'):
            return
        ob_version = get_observer_version_by_sql(self.context, ob_cluster)
        obConnector = OBConnector(
            context=self.context,
            ip=ob_cluster["db_host"],
            port=ob_cluster["db_port"],
            username=ob_cluster["tenant_sys"]["user"],
            password=ob_cluster["tenant_sys"]["password"],
        )
        sql = "select SVR_IP, SVR_PORT, ZONE, BUILD_VERSION from oceanbase.__all_server"
        if ob_version.startswith(("1", "2", "3")):
            sql = "select SVR_IP, SVR_PORT, ZONE, BUILD_VERSION from oceanbase.DBA_OB_SERVERS"
        try:
            res = obConnector.execute_sql(sql)
            if not res:
                raise Exception(f"Failed to get the node from SQL [{sql}], please check whether the --config option is correct!!!")
            host_info_list = [{"ip": row[0]} for row in res]
            self.stdio.verbose("get host info: %s", host_info_list)
            config_data_new = copy(config_data)
            config_data_new.setdefault('obcluster', {}).setdefault('servers', {}).setdefault('nodes', [])
            for item in host_info_list:
                config_data_new['obcluster']['servers']['nodes'].append({'ip': item['ip']})
            self.stdio.verbose("update nodes config: %s", config_data_new['obcluster']['servers']['nodes'])
            config.update_config_data(config_data_new)
        except Exception as e:
            self.stdio.error(f"An error occurred: {e}")

    def get_namespace(self, spacename):
        if spacename in self.namespaces:
            namespace = self.namespaces[spacename]
        else:
            namespace = HandlerContextNamespace(spacename=spacename)
            self.namespaces[spacename] = namespace
        return namespace

    def call_plugin(self, plugin, spacename=None, target_servers=None, **kwargs):
        args = {
            'namespace': spacename,
            'namespaces': self.namespaces,
            'cluster_config': None,
            'obproxy_config': None,
            'ocp_config': None,
            'cmd': self.cmds,
            'options': self.options,
            'stdio': self.stdio,
            'target_servers': target_servers,
        }
        args.update(kwargs)
        self._call_stdio('verbose', 'Call %s ' % (plugin))
        return plugin(**args)

    def _call_stdio(self, func, msg, *arg, **kwarg):
        if func not in self._stdio_func:
            return None
        return self._stdio_func[func](msg, *arg, **kwarg)

    def ssh_clients_connect(self, servers, ssh_clients, user_config, fail_exit=False):
        self._call_stdio('start_loading', 'Open ssh connection')
        connect_io = self.stdio if fail_exit else self.stdio.sub_io()
        connect_status = {}
        success = True
        for server in servers:
            if server not in ssh_clients:
                client = SshClient(SshConfig(server.ip, user_config.username, user_config.password, user_config.key_file, user_config.port, user_config.timeout), self.stdio)
                error = client.connect(stdio=connect_io)
                connect_status[server] = status = CheckStatus()
                if error is not True:
                    success = False
                    status.status = CheckStatus.FAIL
                    status.error = error
                    status.suggests.append(SUG_SSH_FAILED.format())
                else:
                    status.status = CheckStatus.PASS
                    ssh_clients[server] = client
        self._call_stdio('stop_loading', 'succeed' if success else 'fail')
        return connect_status
