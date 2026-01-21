#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
obdiag Agent core class
"""

from src.common.context import Context
from .tool_manager import ToolManager
from .knowledge_manager import KnowledgeManager
from .memory_manager import MemoryManager


class ObdiagAgent:
    """obdiag intelligent diagnostic Agent"""

    def __init__(self, context: Context):
        self.context = context
        self.stdio = context.stdio
        self.tool_manager = ToolManager(context)
        self.knowledge_manager = KnowledgeManager(context)
        self.memory_manager = MemoryManager(context)

    def diagnose(self, query: str) -> dict:
        """Execute diagnosis workflow"""
        # Context collection
        context = self._collect_context()

        # Knowledge retrieval
        knowledge = self.knowledge_manager.search(query, context)

        # Tool execution
        result = self.tool_manager.execute_diagnosis(query, context, knowledge)

        # Save case
        self.memory_manager.save_case(query, context, result)

        return result

    def _collect_context(self) -> dict:
        """Collect context information"""
        return {'cluster_info': self.context.cluster_config, 'tenant_info': self.context.tenant_config, 'node_info': self.context.node_config}
