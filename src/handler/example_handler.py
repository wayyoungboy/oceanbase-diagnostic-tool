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
@time: 2026/02/03
@file: example_handler.py
@desc: Example handler demonstrating the new BaseHandler pattern
"""

from src.common.base_handler import BaseHandler
from src.common.config_accessor import ConfigAccessor
from src.common.result_type import ObdiagResult


class ExampleHandler(BaseHandler):
    """
    Example handler demonstrating the new unified pattern.

    This handler shows:
    - How to use BaseHandler
    - How to use ConfigAccessor
    - How to implement handle() method
    - How to use unified error handling
    """

    def _init(self, **kwargs):
        """Subclass initialization"""
        # Initialize config accessor
        if self.context:
            self.config = ConfigAccessor(config_manager=self.context.cluster_config if hasattr(self.context, 'cluster_config') else None, inner_config_manager=self.context.inner_config if hasattr(self.context, 'inner_config') else None)

        # Get configuration values
        self.max_workers = self.config.check_max_workers if hasattr(self, 'config') else 12
        self.work_path = self.config.check_work_path if hasattr(self, 'config') else "~/.obdiag/check"

        self._log_verbose(f"ExampleHandler initialized: max_workers={self.max_workers}, work_path={self.work_path}")

    def handle(self) -> ObdiagResult:
        """
        Execute handler logic.

        Returns:
            ObdiagResult: Execution result
        """
        self._validate_initialized()

        try:
            self._log_info("ExampleHandler: Starting execution")

            # Example: Get option value
            option_value = self._get_option('example_option', default='default_value')
            self._log_verbose(f"Example option value: {option_value}")

            # Example: Set variable
            self._set_variable('example_var', 'example_value')

            # Example: Get variable
            var_value = self._get_variable('example_var', default='default')
            self._log_verbose(f"Example variable value: {var_value}")

            # Example business logic
            result_data = {
                "message": "Example handler executed successfully",
                "max_workers": self.max_workers,
                "work_path": self.work_path,
            }

            self._log_info("ExampleHandler: Execution completed")
            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data=result_data)

        except Exception as e:
            return self._handle_error(e)
