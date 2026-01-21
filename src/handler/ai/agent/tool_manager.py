#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
obdiag Agent tool manager
"""

from src.common.command import Command
from ..tools.obdiag_tools import GatherTool, CheckTool, RcaTool
from ..tools.system_tools import SshTool, SqlTool


class ToolManager:
    """Tool manager"""

    def __init__(self, context):
        self.context = context
        self.stdio = context.stdio
        self.command = Command()
        self.tools = {'gather': GatherTool(context), 'check': CheckTool(context), 'rca': RcaTool(context), 'ssh': SshTool(context), 'sql': SqlTool(context)}

    def execute_diagnosis(self, query: str, context: dict, knowledge: dict) -> dict:
        """Execute diagnosis"""
        # Select tools based on query and knowledge
        plan = self._create_plan(query, knowledge)

        # Execute plan
        return self._execute_plan(plan)

    def _create_plan(self, query: str, knowledge: dict) -> dict:
        """Create execution plan"""
        # Simplified plan creation logic
        return {'steps': [{'tool': 'check', 'args': {'scope': 'cluster'}}, {'tool': 'gather', 'args': {'type': 'log', 'component': 'observer'}}]}

    def _execute_plan(self, plan: dict) -> dict:
        """Execute plan"""
        results = {}
        for step in plan['steps']:
            tool = self.tools[step['tool']]
            results[step['tool']] = tool.execute(**step['args'])
        return results
