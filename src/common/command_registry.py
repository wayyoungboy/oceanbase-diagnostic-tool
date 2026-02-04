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
@file: command_registry.py
@desc: Command registry for automatic command discovery and registration
"""

import importlib
import pkgutil
from typing import Dict, Type, Optional
from src.common.diag_cmd import ObdiagOriginCommand


class CommandRegistry:
    """
    Registry for command classes.

    Supports automatic discovery and registration of commands.
    """

    _instance = None
    _registry: Dict[str, Type[ObdiagOriginCommand]] = {}

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, command_class: Type[ObdiagOriginCommand]):
        """
        Register command class.

        Can be used as decorator:
            @CommandRegistry.register
            class MyCommand(ObdiagOriginCommand):
                pass

        Args:
            command_class: Command class to register
        """
        command_name = command_class.__name__
        cls._registry[command_name] = command_class
        return command_class

    @classmethod
    def get(cls, command_name: str) -> Optional[Type[ObdiagOriginCommand]]:
        """
        Get command class by name.

        Args:
            command_name: Command class name

        Returns:
            Command class or None if not found
        """
        return cls._registry.get(command_name)

    @classmethod
    def list_commands(cls) -> list:
        """
        List all registered commands.

        Returns:
            List of command names
        """
        return list(cls._registry.keys())

    @classmethod
    def auto_discover(cls, package_path: str = "src.common"):
        """
        Automatically discover and register commands.

        Args:
            package_path: Package path to search for commands
        """
        try:
            package = importlib.import_module(package_path)
            package_dir = package.__path__

            for importer, modname, ispkg in pkgutil.walk_packages(package_dir, package_path + "."):
                if not ispkg and "command" in modname.lower():
                    try:
                        cls._register_commands_from_module(modname)
                    except Exception:
                        # Skip modules that can't be imported
                        pass
        except Exception:
            # If auto-discovery fails, continue with manual registration
            pass

    @classmethod
    def _register_commands_from_module(cls, module_name: str):
        """
        Register commands from a module.

        Args:
            module_name: Module name to import
        """
        try:
            module = importlib.import_module(module_name)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # Check if it's a Command class
                if isinstance(attr, type) and issubclass(attr, ObdiagOriginCommand) and attr != ObdiagOriginCommand and (attr_name.endswith('Command') or 'Command' in attr_name):

                    # Register command
                    cls.register(attr)
        except Exception:
            # Skip modules that can't be processed
            pass

    @classmethod
    def create_command(cls, command_name: str, *args, **kwargs) -> Optional[ObdiagOriginCommand]:
        """
        Create command instance.

        Args:
            command_name: Command class name
            *args: Positional arguments for command constructor
            **kwargs: Keyword arguments for command constructor

        Returns:
            Command instance or None if not found
        """
        command_class = cls.get(command_name)
        if command_class:
            return command_class(*args, **kwargs)
        return None
