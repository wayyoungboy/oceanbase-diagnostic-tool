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
@time: 2025/12/08
@file: ai_assistant_handler.py
@desc: AI Assistant interactive handler
"""

import os
import json
import yaml
from typing import Dict, List, Optional

from src.common.base_handler import BaseHandler
from src.handler.ai.openai_client import ObdiagAIClient
from src.handler.ai.obi_client import OBIClient
from src.common.tool import Util
from src.common.result_type import ObdiagResult

# Rich library for Markdown rendering in terminal
try:
    from rich.console import Console
    from rich.markdown import Markdown

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# prompt_toolkit for better input handling (especially for CJK characters)
try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.history import InMemoryHistory

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


class AiAssistantHandler(BaseHandler):
    """AI Assistant interactive handler"""

    BETA_WARNING = """
╔══════════════════════════════════════════════════════════════════════════╗
║                          ⚠️  BETA FEATURE WARNING  ⚠️                      ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  This is a BETA feature and may change in future versions.               ║
║  Compatibility with previous versions is not guaranteed.                 ║
║                                                                          ║
║  If you encounter any issues, please report them at:                     ║
║  https://github.com/oceanbase/obdiag/issues                              ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

    WELCOME_MESSAGE = """
╔══════════════════════════════════════════════════════════════════════════╗
║                    obdiag AI Assistant                                   ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                          ║
║  Welcome! I'm your AI assistant for OceanBase diagnostics.               ║
║  You can ask me to:                                                      ║
║    - Collect diagnostic information (logs, perf, sysstat)                ║
║    - Analyze logs and performance data                                   ║
║    - Run health checks                                                   ║
║    - Perform root cause analysis                                         ║
║    - And much more...                                                    ║
║                                                                          ║
║  Type 'exit' or 'quit' to end the session.                               ║
║  Type 'help' for more information.                                       ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

    # AI config file path
    AI_CONFIG_PATH = os.path.expanduser("~/.obdiag/ai.yml")

    def _init(self, **kwargs):
        """Subclass initialization"""
        self.ai_client = None
        self.obi_client = None
        self.conversation_history: List[Dict] = []

        # Initialize Rich console for Markdown rendering
        if RICH_AVAILABLE:
            self.console = Console()
        else:
            self.console = None

        # Initialize prompt_toolkit history for input
        if PROMPT_TOOLKIT_AVAILABLE:
            self.input_history = InMemoryHistory()
        else:
            self.input_history = None

    def _load_config(self) -> Dict:
        """
        Load AI assistant configuration from ~/.obdiag/ai.yml

        Config file path: ~/.obdiag/ai.yml
        """
        # Default configuration - no external MCP servers, use built-in server
        default_config = {
            "llm": {
                "api_type": "openai",
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "base_url": os.getenv("OPENAI_BASE_URL", ""),
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            "mcp": {
                "enabled": True,
                "servers": {},  # Empty means use built-in MCP server
            },
            "obi": {
                "enabled": False,
                "base_url": "",
                "app_code": "",
                "cookie": "",
            },
            "ui": {
                "show_welcome": True,
                "show_beta_warning": True,
                "clear_screen": True,
                "prompt": "obdiag AI> ",
            },
        }

        # Try to load config from ~/.obdiag/ai.yml
        ai_config = {}
        config_path = self.AI_CONFIG_PATH

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    ai_config = yaml.safe_load(f) or {}
                self._log_verbose(f"Loaded AI config from {config_path}")
            except Exception as e:
                self._log_warn(f"Failed to load AI config from {config_path}: {e}")
        else:
            self._log_verbose(f"AI config file not found: {config_path}, using defaults")

        # Merge with user configuration
        llm_config = {**default_config["llm"], **ai_config.get("llm", {})}
        obi_config = {**default_config["obi"], **ai_config.get("obi", {})}
        ui_config = {**default_config["ui"], **ai_config.get("ui", {})}

        # Handle MCP configuration
        mcp_config = {**default_config["mcp"]}
        user_mcp_config = ai_config.get("mcp", {})

        if "enabled" in user_mcp_config:
            mcp_config["enabled"] = user_mcp_config["enabled"]

        # Parse MCP servers - supports JSON string format
        # Empty or missing servers means use built-in MCP server
        if "servers" in user_mcp_config:
            servers_value = user_mcp_config["servers"]
            if isinstance(servers_value, str) and servers_value.strip():
                # JSON string format (non-empty)
                try:
                    parsed = json.loads(servers_value)
                    if parsed:  # Only use if non-empty
                        mcp_config["servers"] = parsed
                except json.JSONDecodeError as e:
                    self._log_warn(f"Failed to parse MCP servers JSON: {e}, using built-in server")
                    mcp_config["servers"] = {}
            elif isinstance(servers_value, dict) and servers_value:
                # Direct dict format (non-empty)
                mcp_config["servers"] = servers_value
            # else: keep empty dict to use built-in server

        return {
            "llm": llm_config,
            "mcp": mcp_config,
            "obi": obi_config,
            "ui": ui_config,
        }

    def _init_ai_client(self, config: Dict):
        """Initialize AI client"""
        llm_config = config["llm"]
        mcp_config = config["mcp"]
        obi_config = config["obi"]

        # Check API key
        api_key = llm_config.get("api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is required. " "Please set OPENAI_API_KEY environment variable or configure it in ~/.obdiag/ai.yml")

        # Get base URL
        base_url = llm_config.get("base_url") or os.getenv("OPENAI_BASE_URL") or None

        # Get config path
        config_path = self._get_option("c") or os.path.expanduser("~/.obdiag/config.yml")

        # Get MCP settings
        use_mcp = mcp_config.get("enabled", True)
        mcp_servers = mcp_config.get("servers", {})

        # Get system prompt (use None for default)
        system_prompt = llm_config.get("system_prompt") or None

        # Initialize OBI client if enabled
        if obi_config.get("enabled", False):
            try:
                self.obi_client = OBIClient(
                    base_url=obi_config.get("base_url", ""),
                    app_code=obi_config.get("app_code", ""),
                    cookie=obi_config.get("cookie", ""),
                    enabled=obi_config.get("enabled", False),
                    stdio=self.stdio,
                )
                if self.obi_client.is_configured():
                    # Test connection
                    test_result = self.obi_client.test_connection()
                    if test_result.get("success"):
                        self._log_verbose("OBI client initialized successfully")
                    else:
                        self._log_warn(f"OBI client initialized but connection test failed: {test_result.get('error')}")
                else:
                    self._log_warn("OBI is enabled but not properly configured (missing app_code or cookie)")
                    self.obi_client = None
            except Exception as e:
                self._log_warn(f"Failed to initialize OBI client: {e}")
                self.obi_client = None
        else:
            self.obi_client = None

        # Initialize AI client with OBI client
        self.ai_client = ObdiagAIClient(
            context=self.context,
            api_key=api_key,
            base_url=base_url,
            model=llm_config.get("model", "gpt-4"),
            config_path=config_path,
            use_mcp=use_mcp,
            mcp_servers=mcp_servers,
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 2000),
            system_prompt=system_prompt,
            obi_client=self.obi_client,
        )

    def _clear_screen(self):
        """Clear screen"""
        os.system("clear" if os.name != "nt" else "cls")

    def _render_markdown(self, text: str):
        """
        Render text as Markdown in terminal

        Args:
            text: The text to render (may contain Markdown formatting)
        """
        if RICH_AVAILABLE and self.console:
            try:
                md = Markdown(text)
                self.console.print(md)
            except Exception as e:
                # Fallback to plain text if rendering fails
                self._log_verbose(f"Markdown rendering failed: {e}")
                self._log_info(text)
        else:
            # Fallback to plain text if rich is not available
            self._log_info(text)

    def _show_welcome(self, config: Dict):
        """Show welcome message and beta warning"""
        ui_config = config["ui"]

        if ui_config.get("clear_screen", True):
            self._clear_screen()

        if ui_config.get("show_beta_warning", True):
            self._log_info(self.BETA_WARNING)
            self._log_info("")

        if ui_config.get("show_welcome", True):
            self._log_info(self.WELCOME_MESSAGE)
            self._log_info("")

    def _show_help(self):
        """Show help information"""
        help_text = """
Available commands:
  help, ?          - Show this help message
  exit, quit, q    - Exit the AI assistant
  clear            - Clear conversation history
  history          - Show conversation history
  tools            - List available diagnostic tools

You can also ask me questions in natural language, such as:
  - "帮我检查数据库的健康状态"
  - "收集最近1小时的日志"
  - "分析日志中的错误信息"
  - "检查IO性能"
  - "执行根因分析"
"""
        self._log_info(help_text)

    def _show_tools(self):
        """Show available tools"""
        tools_text = """
Available diagnostic tools:

📦 Information Gathering:
  - gather_log         : Collect OceanBase observer logs
  - gather_sysstat     : Collect system statistics
  - gather_perf        : Collect performance data (flame graph, pstack)
  - gather_obproxy_log : Collect OBProxy logs
  - gather_ash         : Generate ASH (Active Session History) report
  - gather_awr         : Collect AWR data

🔍 Analysis:
  - analyze_log        : Analyze OceanBase logs for errors/warnings

✅ Health Check:
  - check              : Run health checks on OceanBase cluster
  - check_list         : List available check tasks

🔎 Root Cause Analysis:
  - rca_run            : Run root cause analysis for specific scenarios
  - rca_list           : List available RCA scenarios

🛠️ Tools:
  - tool_io_performance: Check disk IO performance
"""
        self._log_info(tools_text)

    def _show_loaded_tools(self):
        """Show loaded MCP tools information"""
        try:
            # Show OBI status
            if self.obi_client and self.obi_client.is_configured():
                test_result = self.obi_client.test_connection()
                if test_result.get("success"):
                    self._log_info("🔍 OBI (OceanBase Intelligence): ✓ Connected")
                else:
                    self._log_info("🔍 OBI (OceanBase Intelligence): ✗ Connection failed")
            elif self.obi_client:
                self._log_info("🔍 OBI (OceanBase Intelligence): ⚠ Not configured")
            else:
                self._log_info("🔍 OBI (OceanBase Intelligence): ○ Disabled")
            self._log_info("")

            # Check external MCP client first
            if self.ai_client and self.ai_client.mcp_client and self.ai_client.mcp_client.is_connected():
                # Get connected servers info
                connected_servers = self.ai_client.mcp_client.get_connected_servers()
                servers_info = self.ai_client.mcp_client.get_server_info()

                self._log_info(f"🔌 MCP Servers ({len(connected_servers)} connected):")
                for server_name in connected_servers:
                    info = servers_info.get(server_name, {})
                    version = info.get("version", "unknown")
                    self._log_info(f"   • {server_name} (v{version})")

                # List all tools
                tools = self.ai_client.mcp_client.list_tools()
                self._log_info(f"\n📦 Loaded {len(tools)} tools via MCP protocol:")
                for tool in tools:
                    tool_name = tool.get("name", "")
                    self._log_info(f"   • {tool_name}")
                self._log_info("")
            # Check built-in MCP server
            elif self.ai_client and self.ai_client.builtin_mcp_server:
                self._log_info("🔌 Using built-in MCP server")

                # List tools from built-in server
                tools = self.ai_client.builtin_mcp_server.tools
                self._log_info(f"\n📦 Loaded {len(tools)} tools:")
                for tool in tools:
                    tool_name = tool.get("name", "")
                    self._log_info(f"   • {tool_name}")
                self._log_info("")
            else:
                self._log_warn("⚠️  No MCP server connected. Tools will not be available.")
                self._log_info("")
        except Exception as e:
            self._log_verbose(f"Failed to show loaded tools: {e}")

    def _show_history(self):
        """Show conversation history"""
        if not self.conversation_history:
            self._log_info("No conversation history.\n")
            return

        self._log_info("\n=== Conversation History ===\n")
        for i, msg in enumerate(self.conversation_history, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                self._log_info(f"[{i}] User: {content}\n")
            elif role == "assistant":
                display_content = content[:200] + "..." if len(content) > 200 else content
                self._log_info(f"[{i}] Assistant: {display_content}\n")
        self._log_info("===========================\n")

    def handle(self) -> ObdiagResult:
        """Main handler method"""
        self._validate_initialized()

        try:
            # Load configuration
            config = self._load_config()

            # Show welcome and warning
            self._show_welcome(config)

            # Initialize AI client
            self._log_verbose("Initializing AI client...")
            self._init_ai_client(config)
            self._log_verbose("AI client initialized successfully")

            # Show loaded tools info
            self._show_loaded_tools()

            # Debug: show if prompt_toolkit is available
            if PROMPT_TOOLKIT_AVAILABLE:
                self._log_verbose("Using prompt_toolkit for input (CJK character support enabled)")
            else:
                self._log_verbose("prompt_toolkit not available, using standard input")

            # Interactive loop
            ui_config = config["ui"]
            prompt = ui_config.get("prompt", "obdiag AI> ")

            while True:
                try:
                    # Get user input
                    # Use prompt_toolkit for better CJK character handling (backspace works correctly)
                    if PROMPT_TOOLKIT_AVAILABLE:
                        user_input = pt_prompt(prompt, history=self.input_history).strip()
                    else:
                        user_input = input(prompt).strip()

                    if not user_input:
                        continue

                    # Handle special commands
                    if user_input.lower() in ["exit", "quit", "q"]:
                        self._log_info("\nGoodbye! Have a nice day!\n")
                        break
                    elif user_input.lower() in ["help", "?"]:
                        self._show_help()
                        continue
                    elif user_input.lower() == "clear":
                        self.conversation_history = []
                        self._log_info("Conversation history cleared.\n")
                        continue
                    elif user_input.lower() == "history":
                        self._show_history()
                        continue
                    elif user_input.lower() == "tools":
                        self._show_tools()
                        continue

                    # Process user input with AI
                    self._log_info("")  # New line
                    self.stdio.start_loading("Thinking...")

                    try:
                        response = self.ai_client.chat(user_input, self.conversation_history)
                        self.stdio.stop_loading("succeed")
                        self._log_info("\r" + " " * 20 + "\r", end="")  # Clear "Thinking..."

                        # Render response as Markdown
                        self._render_markdown(response)
                        self._log_info("")  # New line after response

                        # Update conversation history
                        self.conversation_history.append({"role": "user", "content": user_input})
                        self.conversation_history.append({"role": "assistant", "content": response})

                        # Limit history size to prevent context overflow
                        if len(self.conversation_history) > 20:
                            self.conversation_history = self.conversation_history[-20:]

                    except Exception as e:
                        self._log_info(f"\rError: {str(e)}\n")
                        self._log_error(f"Failed to get AI response: {str(e)}")

                except KeyboardInterrupt:
                    self._log_info("\n\nInterrupted. Type 'exit' to quit.\n")
                except EOFError:
                    self._log_info("\n\nGoodbye!\n")
                    break

            return ObdiagResult(ObdiagResult.SUCCESS_CODE, data={"message": "AI assistant session ended"})

        except Exception as e:
            return self._handle_error(e)
        finally:
            # Cleanup
            if self.ai_client:
                try:
                    self.ai_client.close()
                except Exception as e:
                    # Client cleanup failure is non-critical, log verbosely
                    self.stdio.verbose("Failed to close AI client: {0}".format(e))
