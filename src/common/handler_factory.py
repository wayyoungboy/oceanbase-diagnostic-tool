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
@file: handler_factory.py
@desc: Handler factory for creating and managing handlers
"""

import importlib
import pkgutil
from typing import Dict, Type, Optional, Any
from src.common.base_handler import BaseHandler
from src.common.context import HandlerContext


class HandlerFactory:
    """
    Handler factory for creating and managing handlers.

    Supports:
    - Handler registration
    - Handler creation with dependency injection
    - Automatic handler discovery
    """

    def __init__(self):
        """Initialize handler factory"""
        self._handler_registry: Dict[str, Type[BaseHandler]] = {}
        self._initialized = False

    def register(self, handler_name: str, handler_class: Type[BaseHandler]):
        """
        Register handler class.

        Args:
            handler_name: Handler name (e.g., 'gather_log')
            handler_class: Handler class (must inherit from BaseHandler)
        """
        if not issubclass(handler_class, BaseHandler):
            raise ValueError(f"Handler {handler_name} must inherit from BaseHandler")

        self._handler_registry[handler_name] = handler_class

    def create(self, handler_name: str, context: HandlerContext, **kwargs) -> BaseHandler:
        """
        Create handler instance.

        Args:
            handler_name: Handler name
            context: Handler context
            **kwargs: Additional initialization parameters

        Returns:
            Initialized handler instance

        Raises:
            ValueError: If handler not found
        """
        if handler_name not in self._handler_registry:
            raise ValueError(f"Handler '{handler_name}' not found. Available handlers: {list(self._handler_registry.keys())}")

        handler_class = self._handler_registry[handler_name]

        # Create handler instance
        handler = handler_class()

        # Initialize handler
        handler.init(context, **kwargs)

        return handler

    def auto_discover(self, package_path: str = "src.handler"):
        """
        Automatically discover and register handlers.

        Args:
            package_path: Package path to search for handlers
        """
        if self._initialized:
            return

        try:
            package = importlib.import_module(package_path)
            package_dir = package.__path__

            for importer, modname, ispkg in pkgutil.walk_packages(package_dir, package_path + "."):
                if not ispkg:
                    try:
                        self._register_handlers_from_module(modname)
                    except Exception:
                        # Skip modules that can't be imported
                        pass

        except Exception:
            # If auto-discovery fails, continue with manual registration
            pass

        self._initialized = True

    def _register_handlers_from_module(self, module_name: str):
        """
        Register handlers from a module.

        Args:
            module_name: Module name to import
        """
        try:
            module = importlib.import_module(module_name)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # Check if it's a Handler class
                if isinstance(attr, type) and issubclass(attr, BaseHandler) and attr != BaseHandler and attr_name.endswith('Handler'):

                    # Generate handler name from class name
                    # e.g., GatherLogHandler -> gather_log
                    handler_name = self._class_name_to_handler_name(attr_name)

                    # Register handler
                    self.register(handler_name, attr)

        except Exception:
            # Skip modules that can't be processed
            pass

    def _class_name_to_handler_name(self, class_name: str) -> str:
        """
        Convert class name to handler name.

        Args:
            class_name: Class name (e.g., 'GatherLogHandler')

        Returns:
            Handler name (e.g., 'gather_log')
        """
        # Remove 'Handler' suffix
        name = class_name.replace('Handler', '')

        # Convert CamelCase to snake_case
        import re

        name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

        return name

    def list_handlers(self) -> list:
        """
        List all registered handlers.

        Returns:
            List of handler names
        """
        return list(self._handler_registry.keys())

    def is_registered(self, handler_name: str) -> bool:
        """
        Check if handler is registered.

        Args:
            handler_name: Handler name

        Returns:
            True if registered, False otherwise
        """
        return handler_name in self._handler_registry

    def get_handler_class(self, handler_name: str) -> Optional[Type[BaseHandler]]:
        """
        Get handler class by name.

        Args:
            handler_name: Handler name

        Returns:
            Handler class or None if not found
        """
        return self._handler_registry.get(handler_name)
