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
@file: error_handler.py
@desc: Unified error handling framework with retry mechanism
"""

import time
import functools
from enum import Enum
from typing import Callable, Any, Optional, Type, Tuple, List
from src.common.result_type import ObdiagResult


class ErrorCategory(Enum):
    """Error category enumeration"""

    NETWORK = "network"  # Network-related errors (SSH, HTTP, etc.)
    DATABASE = "database"  # Database connection/query errors
    FILE_SYSTEM = "file_system"  # File I/O errors
    CONFIGURATION = "configuration"  # Configuration errors
    VALIDATION = "validation"  # Input validation errors
    BUSINESS_LOGIC = "business_logic"  # Business logic errors
    UNKNOWN = "unknown"  # Unknown errors


class RetryStrategy:
    """Retry strategy configuration"""

    def __init__(self, max_attempts: int = 3, initial_delay: float = 1.0, max_delay: float = 60.0, exponential_base: float = 2.0, jitter: bool = True):
        """
        Initialize retry strategy.

        Args:
            max_attempts: Maximum number of retry attempts (default: 3)
            initial_delay: Initial delay in seconds (default: 1.0)
            max_delay: Maximum delay in seconds (default: 60.0)
            exponential_base: Base for exponential backoff (default: 2.0)
            jitter: Whether to add random jitter to delay (default: True)
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry attempt.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.initial_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random

            delay = delay * (0.5 + random.random() * 0.5)

        return delay


class ErrorHandler:
    """
    Unified error handler with retry mechanism.

    Provides:
    - Error categorization
    - Retry strategies
    - Error logging
    - Result conversion
    """

    # Default retry strategies by error category
    DEFAULT_RETRY_STRATEGIES = {
        ErrorCategory.NETWORK: RetryStrategy(max_attempts=3, initial_delay=1.0),
        ErrorCategory.DATABASE: RetryStrategy(max_attempts=3, initial_delay=1.0),
        ErrorCategory.FILE_SYSTEM: RetryStrategy(max_attempts=2, initial_delay=0.5),
        ErrorCategory.CONFIGURATION: RetryStrategy(max_attempts=1, initial_delay=0.0),  # No retry
        ErrorCategory.VALIDATION: RetryStrategy(max_attempts=1, initial_delay=0.0),  # No retry
        ErrorCategory.BUSINESS_LOGIC: RetryStrategy(max_attempts=1, initial_delay=0.0),  # No retry
        ErrorCategory.UNKNOWN: RetryStrategy(max_attempts=2, initial_delay=1.0),
    }

    @staticmethod
    def categorize_error(error: Exception) -> ErrorCategory:
        """
        Categorize error based on exception type.

        Args:
            error: Exception instance

        Returns:
            ErrorCategory
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()

        # Network errors
        if any(keyword in error_type.lower() or keyword in error_msg for keyword in ['ssh', 'connection', 'timeout', 'network', 'socket', 'http']):
            return ErrorCategory.NETWORK

        # Database errors
        if any(keyword in error_type.lower() or keyword in error_msg for keyword in ['database', 'db', 'sql', 'query', 'mysql', 'ob']):
            return ErrorCategory.DATABASE

        # File system errors
        if any(keyword in error_type.lower() or keyword in error_msg for keyword in ['file', 'io', 'permission', 'notfound', 'directory']):
            return ErrorCategory.FILE_SYSTEM

        # Configuration errors
        if any(keyword in error_type.lower() or keyword in error_msg for keyword in ['config', 'configuration', 'invalid', 'missing']):
            return ErrorCategory.CONFIGURATION

        # Validation errors
        if any(keyword in error_type.lower() or keyword in error_msg for keyword in ['validate', 'validation', 'invalid', 'required']):
            return ErrorCategory.VALIDATION

        return ErrorCategory.UNKNOWN

    @staticmethod
    def should_retry(error: Exception, attempt: int, max_attempts: int) -> bool:
        """
        Determine if error should be retried.

        Args:
            error: Exception instance
            attempt: Current attempt number (0-indexed)
            max_attempts: Maximum number of attempts

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= max_attempts:
            return False

        category = ErrorHandler.categorize_error(error)

        # Don't retry configuration or validation errors
        if category in (ErrorCategory.CONFIGURATION, ErrorCategory.VALIDATION):
            return False

        # Don't retry KeyboardInterrupt or SystemExit
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            return False

        return True

    @staticmethod
    def handle_error(error: Exception, stdio=None, error_code: int = ObdiagResult.SERVER_ERROR_CODE, context: Optional[str] = None) -> ObdiagResult:
        """
        Handle error and convert to ObdiagResult.

        Args:
            error: Exception instance
            stdio: Stdio instance for logging (optional)
            error_code: Error code to return
            context: Additional context information

        Returns:
            ObdiagResult with error information
        """
        category = ErrorHandler.categorize_error(error)
        error_msg = str(error)

        if context:
            error_msg = f"{context}: {error_msg}"

        if stdio:
            stdio.error(f"[{category.value}] {error_msg}")
            stdio.exception("")

        return ObdiagResult(error_code, error_data=error_msg)

    @staticmethod
    def handle_with_retry(func: Callable, retry_strategy: Optional[RetryStrategy] = None, stdio=None, context: Optional[str] = None, on_retry: Optional[Callable[[Exception, int], None]] = None) -> Any:
        """
        Execute function with retry mechanism.

        Args:
            func: Function to execute
            retry_strategy: Retry strategy (uses default if None)
            stdio: Stdio instance for logging (optional)
            context: Additional context information
            on_retry: Callback function called on each retry (optional)

        Returns:
            Function result

        Raises:
            Exception: Last exception if all retries fail
        """
        if retry_strategy is None:
            # Use default strategy based on first error
            retry_strategy = RetryStrategy()

        last_error = None

        for attempt in range(retry_strategy.max_attempts):
            try:
                return func()
            except Exception as e:
                last_error = e

                if not ErrorHandler.should_retry(e, attempt, retry_strategy.max_attempts):
                    break

                if stdio:
                    category = ErrorHandler.categorize_error(e)
                    stdio.warn(f"[{category.value}] Attempt {attempt + 1}/{retry_strategy.max_attempts} failed: {str(e)}")

                if on_retry:
                    on_retry(e, attempt)

                if attempt < retry_strategy.max_attempts - 1:
                    delay = retry_strategy.calculate_delay(attempt)
                    if stdio:
                        stdio.verbose(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)

        # All retries failed
        if stdio:
            ErrorHandler.handle_error(last_error, stdio=stdio, context=context)

        raise last_error


def handle_with_retry(retry_strategy: Optional[RetryStrategy] = None, stdio=None, context: Optional[str] = None, on_retry: Optional[Callable[[Exception, int], None]] = None):
    """
    Decorator for automatic retry on failure.

    Usage:
        @handle_with_retry(retry_strategy=RetryStrategy(max_attempts=3))
        def my_function():
            # Your code here
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return ErrorHandler.handle_with_retry(lambda: func(*args, **kwargs), retry_strategy=retry_strategy, stdio=stdio, context=context or func.__name__, on_retry=on_retry)

        return wrapper

    return decorator
