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
@time: 2026/02/09
@file: exceptions.py
@desc: Unified exception hierarchy for obdiag
"""

from typing import Optional, Dict, Any


class ObdiagException(Exception):
    """
    Base exception class for all obdiag exceptions.

    All exceptions in obdiag should inherit from this class.
    """

    def __init__(self, message: str, error_code: Optional[str] = None, context: Optional[Dict[str, Any]] = None, suggestion: Optional[str] = None):
        """
        Initialize exception.

        Args:
            message: Error message
            error_code: Error code (e.g., "OBDIAG-1001")
            context: Structured context information
            suggestion: User-actionable suggestion
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.suggestion = suggestion

    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class ConfigException(ObdiagException):
    """Configuration-related exceptions."""

    pass


class ConnectionException(ObdiagException):
    """Base class for connection-related exceptions."""

    pass


class SSHConnectionException(ConnectionException):
    """SSH connection exceptions."""

    pass


class DBConnectionException(ConnectionException):
    """Database connection exceptions."""

    pass


class HandlerException(ObdiagException):
    """Base class for handler execution exceptions."""

    pass


class CheckException(HandlerException):
    """Check handler exceptions."""

    pass


class GatherException(HandlerException):
    """Gather handler exceptions."""

    pass


class AnalyzeException(HandlerException):
    """Analyze handler exceptions."""

    pass


class RCAException(HandlerException):
    """Root Cause Analysis handler exceptions."""

    pass


class TaskException(HandlerException):
    """Task execution exceptions."""

    def __init__(self, message: str, task_name: Optional[str] = None, node: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize task exception.

        Args:
            message: Error message
            task_name: Name of the task that failed
            node: Node information where task failed
            **kwargs: Additional arguments for base class
        """
        super().__init__(message, **kwargs)
        self.task_name = task_name
        self.node = node


class ReportException(ObdiagException):
    """Report generation exceptions."""

    pass


class ValidationException(ObdiagException):
    """Input validation exceptions."""

    pass


# Backward compatibility: Keep old exception classes as aliases
# These will be deprecated in a future version
import warnings
from src.common.obdiag_exception import (
    OBDIAGException as _OBDIAGException,
    OBDIAGSSHConnException as _OBDIAGSSHConnException,
    OBDIAGDBConnException as _OBDIAGDBConnException,
    OBDIAGShellCmdException as _OBDIAGShellCmdException,
)


# Map old exceptions to new ones for backward compatibility
def _deprecated_exception(old_class, new_class):
    """Create a deprecated exception class that inherits from new class."""

    class DeprecatedException(new_class):
        def __init__(self, *args, **kwargs):
            warnings.warn(f"{old_class.__name__} is deprecated. Use {new_class.__name__} instead.", DeprecationWarning, stacklevel=2)
            super().__init__(*args, **kwargs)

    return DeprecatedException


# Note: For now, we keep the old exceptions as-is to avoid breaking existing code
# In Phase 2.3, we'll gradually migrate to the new exception hierarchy
