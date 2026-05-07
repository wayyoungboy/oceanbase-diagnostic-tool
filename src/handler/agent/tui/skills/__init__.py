#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# MIT License - Copyright (c) LangChain, Inc.
# Vendored from deepagents-cli into OceanBase Diagnostic Tool.
# See src/handler/agent/tui/LICENSE for full license text.

"""Skills module for deepagents CLI.

Public API:
- execute_skills_command: Execute skills subcommands (list/create/info/delete)
- setup_skills_parser: Setup argparse configuration for skills commands

All other components are internal implementation details.
"""

from src.handler.agent.tui.skills.commands import (
    execute_skills_command,
    setup_skills_parser,
)

__all__ = [
    "execute_skills_command",
    "setup_skills_parser",
]
