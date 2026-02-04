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
@file: config_accessor.py
@desc: Unified configuration access layer with type-safe access
"""

import os
from typing import Any, Optional, Dict
from enum import Enum
from src.common.tool import FileUtil


class ConfigSection(Enum):
    """Configuration section enumeration"""

    OBDIAG = "obdiag"
    CHECK = "check"
    GATHER = "gather"
    ANALYZE = "analyze"
    RCA = "rca"
    AI = "ai"  # AI configuration file (ai.yml)


class ConfigValue:
    """Configuration value wrapper with type conversion and validation"""

    def __init__(self, value: Any, default: Any = None, validator: Optional[callable] = None):
        self.value = value
        self.default = default
        self.validator = validator

    def get(self, default: Any = None) -> Any:
        """Get configuration value"""
        val = self.value if self.value is not None else (default or self.default)
        if self.validator:
            val = self.validator(val)
        return val

    def get_int(self, default: int = 0) -> int:
        """Get integer configuration value"""
        val = self.get(default)
        return int(val) if val is not None else default

    def get_bool(self, default: bool = False) -> bool:
        """Get boolean configuration value"""
        val = self.get(default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes', 'on')
        return bool(val) if val is not None else default

    def get_path(self, default: str = "") -> str:
        """Get path configuration value (auto-expand ~)"""
        val = self.get(default)
        return os.path.expanduser(str(val)) if val else default

    def get_size(self, default: str = "0") -> int:
        """Get size configuration value (convert to bytes)"""
        val = self.get(default)
        if isinstance(val, int):
            return val
        if isinstance(val, str):
            return FileUtil.size(val)
        return 0


class ConfigAccessor:
    """
    Unified configuration accessor.

    Provides type-safe, centralized access to configuration values
    with default values and automatic type conversion.
    """

    def __init__(self, config_manager=None, inner_config_manager=None):
        """
        Initialize configuration accessor.

        Args:
            config_manager: ConfigManager instance (user config)
            inner_config_manager: InnerConfigManager instance (internal config)
        """
        self.config = config_manager
        self.inner_config = inner_config_manager
        self._ai_config: Optional[Dict[str, Any]] = None

    # ========== Check Configuration ==========

    @property
    def check_max_workers(self) -> int:
        """Get check max workers (default: 12)"""
        return ConfigValue(self.inner_config.get("check", {}).get("max_workers") if self.inner_config else None, default=12).get_int()

    @property
    def check_work_path(self) -> str:
        """Get check work path (default: ~/.obdiag/check)"""
        return ConfigValue(self.inner_config.get("check", {}).get("work_path") if self.inner_config else None, default="~/.obdiag/check").get_path()

    @property
    def check_report_path(self) -> str:
        """Get check report path (default: ./check_report/)"""
        return ConfigValue(self.inner_config.get("check", {}).get("report", {}).get("report_path") if self.inner_config else None, default="./check_report/").get_path()

    @property
    def check_report_type(self) -> str:
        """Get check report type (default: table)"""
        return ConfigValue(self.inner_config.get("check", {}).get("report", {}).get("export_type") if self.inner_config else None, default="table").get()

    @property
    def check_ignore_version(self) -> bool:
        """Get check ignore version flag (default: False)"""
        return ConfigValue(self.inner_config.get("check", {}).get("ignore_version") if self.inner_config else None, default=False).get_bool()

    @property
    def check_tasks_base_path(self) -> str:
        """Get check tasks base path"""
        return ConfigValue(self.inner_config.get("check", {}).get("tasks_base_path") if self.inner_config else None, default="~/.obdiag/check/tasks/").get_path()

    # ========== Gather Configuration ==========

    @property
    def gather_thread_nums(self) -> int:
        """Get gather thread numbers (default: 3)"""
        return ConfigValue(self.inner_config.get("gather", {}).get("thread_nums") if self.inner_config else None, default=3).get_int()

    @property
    def gather_scenes_base_path(self) -> str:
        """Get gather scenes base path"""
        return ConfigValue(self.inner_config.get("gather", {}).get("scenes_base_path") if self.inner_config else None, default="~/.obdiag/gather/tasks").get_path()

    @property
    def gather_file_number_limit(self) -> int:
        """Get gather file number limit (default: 20)"""
        return ConfigValue(self.inner_config.get("obdiag", {}).get("basic", {}).get("file_number_limit") if self.inner_config else None, default=20).get_int()

    @property
    def gather_file_size_limit(self) -> int:
        """Get gather file size limit in bytes (default: 2GB)"""
        return ConfigValue(self.inner_config.get("obdiag", {}).get("basic", {}).get("file_size_limit") if self.inner_config else None, default="2G").get_size()

    @property
    def gather_redact_processing_num(self) -> int:
        """Get gather redact processing number (default: 3)"""
        return ConfigValue(self.inner_config.get("gather", {}).get("redact_processing_num") if self.inner_config else None, default=3).get_int()

    # ========== Analyze Configuration ==========

    @property
    def analyze_thread_nums(self) -> int:
        """Get analyze thread numbers (default: 3)"""
        return ConfigValue(self.inner_config.get("analyze", {}).get("thread_nums") if self.inner_config else None, default=3).get_int()

    # ========== RCA Configuration ==========

    @property
    def rca_result_path(self) -> str:
        """Get RCA result path (default: ./obdiag_rca/)"""
        return ConfigValue(self.inner_config.get("rca", {}).get("result_path") if self.inner_config else None, default="./obdiag_rca/").get_path()

    # ========== Basic Configuration ==========

    @property
    def basic_config_path(self) -> str:
        """Get basic config path"""
        return ConfigValue(self.inner_config.get("obdiag", {}).get("basic", {}).get("config_path") if self.inner_config else None, default="~/.obdiag/config.yml").get_path()

    @property
    def basic_file_number_limit(self) -> int:
        """Get basic file number limit"""
        return ConfigValue(self.inner_config.get("obdiag", {}).get("basic", {}).get("file_number_limit") if self.inner_config else None, default=20).get_int()

    @property
    def basic_file_size_limit(self) -> int:
        """Get basic file size limit in bytes"""
        return ConfigValue(self.inner_config.get("obdiag", {}).get("basic", {}).get("file_size_limit") if self.inner_config else None, default="2G").get_size()

    # ========== AI Configuration ==========

    @property
    def ai_config(self) -> Dict[str, Any]:
        """Get AI configuration (lazy loaded)"""
        if self._ai_config is None:
            self._ai_config = self._load_ai_config()
        return self._ai_config

    def _load_ai_config(self) -> Dict[str, Any]:
        """Load AI configuration from ai.yml"""
        import yaml

        ai_config_path = os.path.expanduser("~/.obdiag/ai.yml")
        default_config = {
            "llm": {
                "api_type": "openai",
                "api_key": "",
                "api_base": "",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            "mcp": {
                "enabled": False,
                "server_path": "",
            },
            "obi": {
                "enabled": False,
                "api_key": "",
                "api_base": "",
            },
            "ui": {
                "theme": "light",
                "font_size": 14,
            },
        }

        if os.path.exists(ai_config_path):
            try:
                with open(ai_config_path, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f) or {}
                    # Merge with defaults
                    merged_config = default_config.copy()
                    merged_config.update(loaded_config)
                    return merged_config
            except Exception:
                return default_config

        return default_config

    @property
    def ai_llm_config(self) -> Dict[str, Any]:
        """Get AI LLM configuration"""
        return self.ai_config.get("llm", {})

    @property
    def ai_mcp_config(self) -> Dict[str, Any]:
        """Get AI MCP configuration"""
        return self.ai_config.get("mcp", {})

    @property
    def ai_obi_config(self) -> Dict[str, Any]:
        """Get AI OBI configuration"""
        return self.ai_config.get("obi", {})

    @property
    def ai_ui_config(self) -> Dict[str, Any]:
        """Get AI UI configuration"""
        return self.ai_config.get("ui", {})

    # ========== Helper Methods ==========

    def get(self, *keys, default: Any = None) -> Any:
        """
        Generic getter for nested configuration values.

        Args:
            *keys: Nested keys (e.g., 'check', 'report', 'path')
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        if not self.inner_config:
            return default

        current = self.inner_config
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default

        return current if current is not None else default
