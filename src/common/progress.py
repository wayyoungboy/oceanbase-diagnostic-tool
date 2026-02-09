#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (c) 2022 OceanBase
# OceanBase Diagnostic Tool is licensed under Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.

"""
@time: 2026/02/09
@file: progress.py
@desc: Unified progress tracking for all handlers
"""

from contextlib import contextmanager
from typing import Optional, List, Dict, Any


class ProgressTracker:
    """
    Unified progress tracker for long-running operations.
    
    Provides consistent progress feedback across all handlers.
    """
    
    def __init__(self, stdio, total: Optional[int] = None, description: str = "Processing"):
        """
        Initialize progress tracker.
        
        Args:
            stdio: Stdio handler for output
            total: Total number of items to process (optional)
            description: Description of the operation
        """
        self.stdio = stdio
        self.total = total
        self.description = description
        self._current = 0
    
    @contextmanager
    def task(self, name: str):
        """
        Context manager for single task progress tracking.
        
        Usage:
            with tracker.task("Connecting to nodes"):
                # do work
                pass
        
        Args:
            name: Task name
        """
        if self.stdio:
            self.stdio.start_loading(f"{self.description}: {name}")
        
        try:
            yield
            self._current += 1
            if self.stdio:
                self.stdio.stop_loading('succeed')
        except Exception:
            if self.stdio:
                self.stdio.stop_loading('fail')
            raise
    
    def step(self, message: str):
        """
        Log a progress step.
        
        Args:
            message: Step message
        """
        if self.total:
            prefix = f"[{self._current}/{self.total}]"
        else:
            prefix = f"[{self._current}]"
        
        if self.stdio:
            self.stdio.print(f"{prefix} {message}")
    
    @contextmanager
    def node_progress(self, nodes: List[Dict[str, Any]], action: str = "Processing"):
        """
        Context manager for node-level progress tracking.
        
        Usage:
            with tracker.node_progress(nodes, "Gathering logs"):
                for node in nodes:
                    # process node
                    pass
        
        Args:
            nodes: List of node dictionaries
            action: Action description
        """
        total = len(nodes)
        
        for i, node in enumerate(nodes, 1):
            ip = node.get('ip', 'unknown')
            if self.stdio:
                self.stdio.print(f"  [{i}/{total}] {action} {ip}...")
            yield node
    
    def update(self, value: int, message: Optional[str] = None):
        """
        Update progress value.
        
        Args:
            value: Current progress value
            message: Optional progress message
        """
        self._current = value
        if message and self.stdio:
            self.stdio.print(message)
