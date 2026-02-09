#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: log_config.py
@desc: Unified logging configuration for obdiag.

Usage:
    from src.common.log_config import get_logger

    # In each module, use a named logger:
    logger = get_logger(__name__)
    logger.info("Starting gather operation")
    logger.error("Failed to connect: %s", error)

    # Configure logging at startup:
    from src.common.log_config import configure_logging
    configure_logging(log_dir="~/.obdiag/log", level="DEBUG")
"""

import os
import logging
import logging.handlers
from typing import Optional


# Unified log format for all obdiag loggers
LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)-30s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# File log format (more detailed)
FILE_LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-8s] [%(process)d:%(thread)d] %(name)-40s %(funcName)s:%(lineno)d - %(message)s"

# Default log file name
DEFAULT_LOG_FILE = "obdiag.log"
DEFAULT_LOG_DIR = os.path.expanduser("~/.obdiag/log")

# Logger registry for named loggers
_loggers = {}

# Module-level configured flag
_configured = False


def configure_logging(
    log_dir: Optional[str] = None,
    level: str = "INFO",
    max_bytes: int = 50 * 1024 * 1024,  # 50MB
    backup_count: int = 5,
    console: bool = False,
):
    """
    Configure unified logging for obdiag.

    Args:
        log_dir: Directory for log files. Default: ~/.obdiag/log
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Max size of each log file before rotation
        backup_count: Number of rotated log files to keep
        console: Whether to also log to console (stderr)
    """
    global _configured

    log_dir = log_dir or DEFAULT_LOG_DIR
    log_dir = os.path.expanduser(log_dir)
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, DEFAULT_LOG_FILE)
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger for obdiag
    root_logger = logging.getLogger("obdiag")
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(FILE_LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    root_logger.addHandler(file_handler)

    # Console handler (optional)
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        root_logger.addHandler(console_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger under the obdiag namespace.

    Args:
        name: Logger name. Typically __name__ of the module.
              Will be prefixed with 'obdiag.' if not already.

    Returns:
        logging.Logger instance

    Examples:
        # In src/handler/gather/gather_log.py
        logger = get_logger(__name__)
        # Creates logger: obdiag.src.handler.gather.gather_log

        # Explicit name
        logger = get_logger("gather.plan_monitor")
        # Creates logger: obdiag.gather.plan_monitor
    """
    if not name.startswith("obdiag."):
        name = f"obdiag.{name}"

    if name not in _loggers:
        logger = logging.getLogger(name)
        _loggers[name] = logger

    return _loggers[name]


# Pre-defined module loggers for common components
def get_core_logger():
    """Logger for core/coordinator operations."""
    return get_logger("core")


def get_handler_logger(handler_type: str):
    """Logger for handler operations (gather, check, analyze, etc.)."""
    return get_logger(f"handler.{handler_type}")


def get_ssh_logger():
    """Logger for SSH operations."""
    return get_logger("ssh")


def get_db_logger():
    """Logger for database operations."""
    return get_logger("db")


def get_config_logger():
    """Logger for configuration operations."""
    return get_logger("config")
