#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

"""
obdiag Agent system tools wrapper
"""

from src.common.ssh import SshClient
from src.common.ob_connector import OBConnector


class SystemTool:
    """System tool base class"""

    def __init__(self, context):
        self.context = context
        self.stdio = context.stdio


class SshTool(SystemTool):
    """SSH tool"""

    def execute(self, host: str, command: str) -> str:
        """Execute SSH command"""
        ssh = SshClient(self.context)
        if self._confirm_execution(host, command):
            return ssh.execute(host, command)
        return "User cancelled execution"

    def _confirm_execution(self, host: str, command: str) -> bool:
        """Confirm execution"""
        return self.stdio.confirm(f"Confirm execution on {host}: {command}")


class SqlTool(SystemTool):
    """SQL query tool"""

    def execute(self, sql: str) -> str:
        """Execute SQL query"""
        ob = OBConnector(self.context)
        if self._confirm_execution(sql):
            return ob.execute(sql)
        return "User cancelled execution"

    def _confirm_execution(self, sql: str) -> bool:
        """Confirm execution"""
        return self.stdio.confirm(f"Confirm SQL execution: {sql}")
