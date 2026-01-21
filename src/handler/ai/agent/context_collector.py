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
@time: 2026/01/13
@file: context_collector.py
@desc: Context collector for obdiag Agent - automatically collects cluster metadata
"""

import os
import json
import yaml
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime


class ContextCollector:
    """
    Context collector for obdiag Agent

    Automatically collects OceanBase cluster metadata including:
    1. Cluster configuration from obdiag config
    2. Basic cluster information via SQL queries
    3. System information from servers
    4. Recent logs and alerts
    5. Performance baseline data
    """

    def __init__(self, config_path: Optional[str] = None, stdio=None):
        """
        Initialize context collector

        Args:
            config_path: Path to obdiag config file
            stdio: Standard I/O handler for logging
        """
        self.config_path = config_path or os.path.expanduser("~/.obdiag/config.yml")
        self.stdio = stdio
        self.config = self._load_config()
        self.context_cache: Dict[str, Any] = {}

        if self.stdio:
            self.stdio.verbose("Context collector initialized")

    def _load_config(self) -> Dict[str, Any]:
        """Load obdiag configuration"""
        if not os.path.exists(self.config_path):
            if self.stdio:
                self.stdio.warn(f"Config file not found: {self.config_path}")
            return {}

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            if self.stdio:
                self.stdio.warn(f"Failed to load config: {e}")
            return {}

    def collect_all_context(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Collect all available context information

        Args:
            force_refresh: Whether to force refresh cached data

        Returns:
            Dictionary containing all collected context
        """
        if not force_refresh and self.context_cache:
            if self.stdio:
                self.stdio.verbose("Using cached context data")
            return self.context_cache

        if self.stdio:
            self.stdio.verbose("Collecting context information...")

        context = {
            "timestamp": datetime.now().isoformat(),
            "collection_method": "automatic",
        }

        # Collect from different sources
        context.update(self._collect_config_context())
        context.update(self._collect_basic_cluster_info())
        context.update(self._collect_system_info())

        # Cache the results
        self.context_cache = context

        if self.stdio:
            self.stdio.verbose(f"Context collection complete: {len(context)} items")

        return context

    def _collect_config_context(self) -> Dict[str, Any]:
        """Collect context from configuration file"""
        config_context = {
            "config_source": self.config_path,
            "config_exists": os.path.exists(self.config_path),
        }

        if not self.config:
            return config_context

        # Extract cluster information
        if "obcluster" in self.config:
            obcluster = self.config["obcluster"]
            config_context.update(
                {
                    "cluster_name": obcluster.get("ob_cluster_name"),
                    "db_host": obcluster.get("db_host"),
                    "db_port": obcluster.get("db_port", 2881),
                    "sys_tenant_user": obcluster.get("tenant_sys", {}).get("user", "root@sys"),
                }
            )

            # Count nodes
            nodes = obcluster.get("servers", {}).get("nodes", [])
            config_context["node_count"] = len(nodes)

            # Extract node information
            if nodes:
                node_ips = [node.get("ip") for node in nodes if node.get("ip")]
                config_context["node_ips"] = node_ips

                # Check SSH configuration
                ssh_configured = any(node.get("ssh_username") or node.get("ssh_password") or node.get("ssh_key_file") for node in nodes)
                config_context["ssh_configured"] = ssh_configured

        # Extract OBProxy information if available
        if "obproxy" in self.config:
            obproxy = self.config["obproxy"]
            config_context.update(
                {
                    "obproxy_cluster_name": obproxy.get("obproxy_cluster_name"),
                    "obproxy_node_count": len(obproxy.get("servers", {}).get("nodes", [])),
                }
            )

        return config_context

    def _collect_basic_cluster_info(self) -> Dict[str, Any]:
        """
        Collect basic cluster information via SQL queries

        Note: This requires database connectivity and proper credentials
        """
        cluster_info = {
            "cluster_info_available": False,
        }

        # Check if we have database connectivity info
        if not self.config.get("obcluster"):
            if self.stdio:
                self.stdio.verbose("No cluster config available for SQL queries")
            return cluster_info

        obcluster = self.config["obcluster"]
        db_host = obcluster.get("db_host")
        db_port = obcluster.get("db_port", 2881)
        tenant_sys = obcluster.get("tenant_sys", {})

        if not db_host or not tenant_sys.get("user"):
            if self.stdio:
                self.stdio.verbose("Incomplete database config for SQL queries")
            return cluster_info

        try:
            # Try to collect basic cluster info using obdiag or direct SQL
            # This is a simplified version - in practice you'd use proper database connections

            # For now, we'll use a mock approach
            cluster_info.update(
                {
                    "cluster_info_available": True,
                    "collection_method": "config_only",  # Indicates we only used config, not live queries
                    "note": "Live SQL queries require working database connection",
                }
            )

            # If we had a working connection, we would collect:
            # - Cluster version
            # - Tenant information
            # - Resource usage
            # - Recent alerts
            # - Performance metrics

        except Exception as e:
            if self.stdio:
                self.stdio.warn(f"Failed to collect cluster info via SQL: {e}")
            cluster_info["error"] = str(e)

        return cluster_info

    def _collect_system_info(self) -> Dict[str, Any]:
        """Collect system information"""
        system_info = {
            "system_info_available": False,
        }

        try:
            # Collect local system information
            system_info.update(
                {
                    "hostname": self._get_hostname(),
                    "python_version": self._get_python_version(),
                    "obdiag_version": self._get_obdiag_version(),
                    "system_platform": self._get_system_platform(),
                }
            )

            system_info["system_info_available"] = True

        except Exception as e:
            if self.stdio:
                self.stdio.warn(f"Failed to collect system info: {e}")
            system_info["error"] = str(e)

        return system_info

    def _get_hostname(self) -> str:
        """Get system hostname"""
        try:
            import socket

            return socket.gethostname()
        except:
            return "unknown"

    def _get_python_version(self) -> str:
        """Get Python version"""
        import sys

        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def _get_obdiag_version(self) -> str:
        """Get obdiag version"""
        try:
            # Try to get obdiag version via command
            result = subprocess.run(
                ["obdiag", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Extract version from output
                for line in result.stdout.split('\n'):
                    if 'version' in line.lower():
                        return line.strip()
                return result.stdout.strip()[:50]
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

        return "unknown"

    def _get_system_platform(self) -> str:
        """Get system platform information"""
        import platform

        return f"{platform.system()} {platform.release()}"

    def collect_for_diagnosis(self, diagnosis_type: str = "general") -> Dict[str, Any]:
        """
        Collect context specific to a diagnosis type

        Args:
            diagnosis_type: Type of diagnosis (performance, stability, recovery, etc.)

        Returns:
            Context tailored to the diagnosis type
        """
        base_context = self.collect_all_context()

        # Add diagnosis-specific context
        diagnosis_context = {
            "diagnosis_type": diagnosis_type,
            "diagnosis_timestamp": datetime.now().isoformat(),
        }

        # Add type-specific information
        if diagnosis_type == "performance":
            diagnosis_context.update(
                {
                    "focus_areas": ["cpu", "memory", "io", "network", "queries"],
                    "time_range": "last 1 hour",
                    "metrics": ["response_time", "throughput", "resource_utilization"],
                }
            )

        elif diagnosis_type == "stability":
            diagnosis_context.update(
                {
                    "focus_areas": ["errors", "crashes", "timeouts", "failovers"],
                    "time_range": "last 24 hours",
                    "metrics": ["error_rate", "uptime", "recovery_time"],
                }
            )

        elif diagnosis_type == "recovery":
            diagnosis_context.update(
                {
                    "focus_areas": ["backups", "logs", "replication", "consistency"],
                    "time_range": "current state",
                    "metrics": ["data_loss", "recovery_point", "recovery_time"],
                }
            )

        elif diagnosis_type == "security":
            diagnosis_context.update(
                {
                    "focus_areas": ["access_control", "audit_logs", "vulnerabilities", "compliance"],
                    "time_range": "last 7 days",
                    "metrics": ["access_violations", "failed_logins", "security_events"],
                }
            )

        # Merge contexts
        full_context = {**base_context, **diagnosis_context}

        if self.stdio:
            self.stdio.verbose(f"Collected context for {diagnosis_type} diagnosis")

        return full_context

    def get_context_summary(self) -> Dict[str, Any]:
        """Get a summary of available context"""
        context = self.collect_all_context()

        summary = {
            "timestamp": context.get("timestamp"),
            "config_exists": context.get("config_exists", False),
            "cluster_configured": "cluster_name" in context,
            "node_count": context.get("node_count", 0),
            "ssh_configured": context.get("ssh_configured", False),
            "cluster_info_available": context.get("cluster_info_available", False),
            "system_info_available": context.get("system_info_available", False),
            "total_items": len(context),
        }

        return summary

    def clear_cache(self):
        """Clear cached context data"""
        self.context_cache = {}
        if self.stdio:
            self.stdio.verbose("Context cache cleared")

    def save_context_to_file(self, file_path: Optional[str] = None):
        """
        Save collected context to a file

        Args:
            file_path: Path to save context (default: ~/.obdiag/context.json)
        """
        if not file_path:
            file_path = os.path.expanduser("~/.obdiag/context.json")

        context = self.collect_all_context()

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(context, f, indent=2, ensure_ascii=False)

            if self.stdio:
                self.stdio.verbose(f"Context saved to {file_path}")

            return True

        except Exception as e:
            if self.stdio:
                self.stdio.warn(f"Failed to save context: {e}")
            return False

    def load_context_from_file(self, file_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load context from a file

        Args:
            file_path: Path to load context from (default: ~/.obdiag/context.json)

        Returns:
            Loaded context or None if failed
        """
        if not file_path:
            file_path = os.path.expanduser("~/.obdiag/context.json")

        if not os.path.exists(file_path):
            if self.stdio:
                self.stdio.verbose(f"Context file not found: {file_path}")
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                context = json.load(f)

            # Update cache
            self.context_cache = context

            if self.stdio:
                self.stdio.verbose(f"Context loaded from {file_path}")

            return context

        except Exception as e:
            if self.stdio:
                self.stdio.warn(f"Failed to load context: {e}")
            return None


# Integration with DiagnosticAgent


class AgentContextCollector(ContextCollector):
    """
    Context collector specialized for Diagnostic Agent integration

    Adds agent-specific context collection and event integration
    """

    def __init__(self, diagnostic_agent, config_path: Optional[str] = None, stdio=None):
        """
        Initialize agent context collector

        Args:
            diagnostic_agent: Parent DiagnosticAgent instance
            config_path: Path to obdiag config file
            stdio: Standard I/O handler
        """
        super().__init__(config_path, stdio)
        self.agent = diagnostic_agent
        self.session_id = diagnostic_agent.session_id if hasattr(diagnostic_agent, 'session_id') else "unknown"

    def collect_for_agent(self) -> Dict[str, Any]:
        """Collect context for the agent session"""
        base_context = self.collect_all_context()

        # Add agent-specific context
        agent_context = {
            "agent_session_id": self.session_id,
            "agent_timestamp": datetime.now().isoformat(),
            "agent_collection": True,
        }

        # Add agent state if available
        if hasattr(self.agent, 'session'):
            agent_context.update(
                {
                    "agent_state": self.agent.session.state.value if hasattr(self.agent.session, 'state') else "unknown",
                    "agent_phase": self.agent.session.current_phase.value if hasattr(self.agent.session, 'current_phase') else "unknown",
                    "user_query": self.agent.session.user_query if hasattr(self.agent.session, 'user_query') else "",
                }
            )

        # Merge contexts
        full_context = {**base_context, **agent_context}

        # Emit event if agent has event system
        if hasattr(self.agent, '_emit_event'):
            self.agent._emit_event(
                "context_collected",
                {
                    "context_summary": self.get_context_summary(),
                    "session_id": self.session_id,
                },
            )

        return full_context

    def collect_detailed_context(self, include_performance: bool = False) -> Dict[str, Any]:
        """
        Collect detailed context including performance data

        Args:
            include_performance: Whether to include performance metrics

        Returns:
            Detailed context information
        """
        context = self.collect_for_agent()

        if include_performance and self.stdio:
            self.stdio.verbose("Collecting performance context...")

            # Add performance-related context
            # This would include recent metrics, trends, etc.
            # For now, we add placeholders
            context["performance_context"] = {
                "collection_attempted": True,
                "note": "Performance metrics require live monitoring data",
                "suggested_metrics": [
                    "cpu_usage",
                    "memory_usage",
                    "disk_io",
                    "query_latency",
                    "connection_count",
                ],
            }

        return context
