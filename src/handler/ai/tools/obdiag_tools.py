#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
obdiag Agent obdiag tools wrapper
"""

from src.handler.gather.gather_scenes import GatherScenes
from src.handler.check.checker.check_handler import CheckHandler
from src.handler.rca.rca_handler import RcaHandler


class ObdiagTool:
    """obdiag tool base class"""

    def __init__(self, context):
        self.context = context
        self.stdio = context.stdio


class GatherTool(ObdiagTool):
    """Log collection tool"""

    def execute(self, component: str, start_time: str = None, end_time: str = None) -> str:
        """Execute log collection"""
        gather = GatherScenes(self.context)
        return gather.execute(component, start_time, end_time)


class CheckTool(ObdiagTool):
    """Health check tool"""

    def execute(self, scope: str = "all") -> str:
        """Execute health check"""
        check = CheckHandler(self.context)
        return check.execute(scope)


class RcaTool(ObdiagTool):
    """Root cause analysis tool"""

    def execute(self, scenario: str) -> str:
        """Execute root cause analysis"""
        rca = RcaHandler(self.context)
        return rca.execute(scenario)
