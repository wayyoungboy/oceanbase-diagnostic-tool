#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# See the Mulan PSL v2 for more details.

"""
@time: 2022/11/29
@file: gather_plan_monitor.py
@desc: Backward-compatible shim. The actual implementation has been
       refactored into the plan_monitor/ package.
"""

# Re-export for backward compatibility
from src.handler.gather.plan_monitor.handler import GatherPlanMonitorHandler  # noqa: F401

__all__ = ['GatherPlanMonitorHandler']
