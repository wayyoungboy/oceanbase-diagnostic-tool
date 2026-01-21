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
@file: obdiag_agent_integration.py
@desc: Main integration point for obdiag Agent - connects all components
"""

import os
import sys
import json
import yaml
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.handler.ai.agent import DiagnosticAgent, AgentState, DiagnosisPhase
from src.handler.ai.agent.context_collector import AgentContextCollector
from src.handler.ai.reasoning import DiagnosticReasoningChain
from src.handler.ai.planning import ToolPlanner, PlanPriority
from src.handler.ai.memory import SessionManager, LocalCaseMemory
from src.handler.ai.openai_client_enhanced import ObdiagAIClientEnhanced
from src.handler.ai.mcp_server_enhanced import EnhancedMCPServer, ConfirmationMode, ToolSensitivityLevel
from src.handler.ai.ai_assistant_handler_enhanced import AiAssistantHandlerEnhanced


class ObdiagAgentIntegration:
    """
    Main integration class for obdiag Agent.
    Connects all components and provides unified interface.
    """

    def __init__(self, context, config_path: str = None):
        self.context = context
        self.stdio = context.stdio
        self.config_path = config_path or os.path.expanduser("~/.obdiag/ai.yml")

        # Load configuration
        self.config = self._load_config()

        # Initialize components
        self.ai_client = None
        self.mcp_server = None
        self.session_manager = None
        self.case_memory = None
        self.context_collector = None
        self.tool_planner = None
        self.reasoning_chain = None
        self.diagnostic_agent = None
        self.ai_assistant = None

        # State
        self.initialized = False
        self.current_session_id = None

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        default_config = {
            "llm": {
                "api_type": "openai",
                "api_key": os.getenv("OPENAI_API_KEY", ""),
                "base_url": os.getenv("OPENAI_BASE_URL", ""),
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2000,
                "system_prompt": None,
            },
            "mcp": {
                "enabled": True,
                "servers": {},
                "confirmation_mode": "always",
                "auto_confirm_level": "medium",
                "audit_logging": True,
            },
            "memory": {
                "session_dir": "~/.obdiag/ai_sessions",
                "cases_dir": "~/.obdiag/cases",
                "max_turns": 50,
                "similarity_threshold": 0.8,
                "max_similar_cases": 3,
                "auto_save_resolved": True,
            },
            "agent": {
                "mode": "advanced",  # basic, advanced
                "max_hypotheses": 5,
                "evidence_threshold": 0.7,
                "confidence_threshold": 0.8,
                "max_iterations": 10,
                "enable_reflection": True,
            },
            "ui": {
                "show_welcome": True,
                "show_beta_warning": True,
                "clear_screen": True,
                "prompt": "obdiag Agent> ",
                "stream_output": True,
            },
        }

        # Load from file if exists
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f) or {}

                # Deep merge with defaults
                config = self._deep_merge(default_config, user_config)
                self.stdio.verbose(f"Loaded config from {self.config_path}")
                return config

            except Exception as e:
                self.stdio.warn(f"Failed to load config from {self.config_path}: {e}")
                return default_config
        else:
            self.stdio.verbose(f"Config file not found: {self.config_path}, using defaults")
            return default_config

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = base.copy()

        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def initialize(self) -> bool:
        """Initialize all components"""
        try:
            self.stdio.verbose("Initializing obdiag Agent...")

            # 1. Initialize AI client
            self._init_ai_client()

            # 2. Initialize MCP server
            self._init_mcp_server()

            # 3. Initialize memory components
            self._init_memory_components()

            # 4. Initialize reasoning and planning
            self._init_reasoning_planning()

            # 5. Initialize diagnostic agent
            self._init_diagnostic_agent()

            # 6. Initialize AI assistant (for backward compatibility)
            self._init_ai_assistant()

            self.initialized = True
            self.stdio.verbose("obdiag Agent initialized successfully")
            return True

        except Exception as e:
            self.stdio.error(f"Failed to initialize obdiag Agent: {e}")
            return False

    def _init_ai_client(self):
        """Initialize AI client"""
        llm_config = self.config["llm"]

        api_key = llm_config.get("api_key")
        if not api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY or configure in ~/.obdiag/ai.yml")

        self.ai_client = ObdiagAIClientEnhanced(
            context=self.context,
            api_key=api_key,
            base_url=llm_config.get("base_url"),
            model=llm_config.get("model", "gpt-4"),
            config_path=self.config_path,
            use_mcp=False,  # We'll handle MCP separately
            mcp_servers={},
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 2000),
            system_prompt=llm_config.get("system_prompt"),
            confirmation_mode=ConfirmationMode.ALWAYS,  # Will be overridden by MCP server
            auto_confirm_level=ToolSensitivityLevel.MEDIUM,
        )

        self.stdio.verbose("AI client initialized")

    def _init_mcp_server(self):
        """Initialize enhanced MCP server"""
        mcp_config = self.config["mcp"]

        if not mcp_config.get("enabled", True):
            self.stdio.verbose("MCP server disabled")
            return

        # Parse confirmation settings
        confirmation_mode_str = mcp_config.get("confirmation_mode", "always")
        try:
            confirmation_mode = ConfirmationMode(confirmation_mode_str)
        except ValueError:
            self.stdio.warn(f"Invalid confirmation mode: {confirmation_mode_str}, using 'always'")
            confirmation_mode = ConfirmationMode.ALWAYS

        auto_confirm_level_str = mcp_config.get("auto_confirm_level", "medium")
        try:
            auto_confirm_level = ToolSensitivityLevel(auto_confirm_level_str)
        except ValueError:
            self.stdio.warn(f"Invalid auto confirm level: {auto_confirm_level_str}, using 'medium'")
            auto_confirm_level = ToolSensitivityLevel.MEDIUM

        audit_logging = mcp_config.get("audit_logging", True)

        self.mcp_server = EnhancedMCPServer(
            context=self.context,
            confirmation_mode=confirmation_mode,
            auto_confirm_level=auto_confirm_level,
            audit_logging=audit_logging,
        )

        # Connect external MCP servers if configured
        external_servers = mcp_config.get("servers", {})
        if external_servers:
            self.mcp_server.connect_external_servers(external_servers)

        self.stdio.verbose(f"MCP server initialized with {len(self.mcp_server.tools)} tools")

    def _init_memory_components(self):
        """Initialize memory components"""
        memory_config = self.config["memory"]

        # Session manager
        session_dir = os.path.expanduser(memory_config.get("session_dir", "~/.obdiag/ai_sessions"))
        self.session_manager = SessionManager(storage_dir=session_dir, stdio=self.stdio)

        # Case memory
        cases_dir = os.path.expanduser(memory_config.get("cases_dir", "~/.obdiag/cases"))
        self.case_memory = LocalCaseMemory(storage_dir=cases_dir, stdio=self.stdio)

        # Context collector
        self.context_collector = AgentContextCollector(
            diagnostic_agent=None,  # Will be set later
            config_path=self.config_path,
            stdio=self.stdio,
        )

        self.stdio.verbose(f"Memory components initialized: {len(self.session_manager.sessions)} sessions, {len(self.case_memory.cases)} cases")

    def _init_reasoning_planning(self):
        """Initialize reasoning and planning components"""
        # Tool planner
        self.tool_planner = ToolPlanner(
            ai_client=self.ai_client,
            mcp_server=self.mcp_server,
            stdio=self.stdio,
        )

        # Reasoning chain
        self.reasoning_chain = DiagnosticReasoningChain(
            chain_id="diagnostic_chain",
            ai_client=self.ai_client,
            stdio=self.stdio,
        )

        self.stdio.verbose("Reasoning and planning components initialized")

    def _init_diagnostic_agent(self):
        """Initialize diagnostic agent"""
        agent_config = self.config["agent"]

        self.diagnostic_agent = DiagnosticAgent(
            context=self.context,
            ai_client=self.ai_client,
            session_manager=self.session_manager,
            case_memory=self.case_memory,
            context_collector=self.context_collector,
            tool_planner=self.tool_planner,
            reasoning_chain=self.reasoning_chain,
            mcp_server=self.mcp_server,
            mode=agent_config.get("mode", "advanced"),
            max_hypotheses=agent_config.get("max_hypotheses", 5),
            evidence_threshold=agent_config.get("evidence_threshold", 0.7),
            confidence_threshold=agent_config.get("confidence_threshold", 0.8),
            max_iterations=agent_config.get("max_iterations", 10),
            enable_reflection=agent_config.get("enable_reflection", True),
        )

        # Update context collector with agent reference
        self.context_collector.diagnostic_agent = self.diagnostic_agent

        self.stdio.verbose("Diagnostic Agent initialized")

    def _init_ai_assistant(self):
        """Initialize AI assistant for backward compatibility"""
        self.ai_assistant = AiAssistantHandlerEnhanced(self.context)
        self.stdio.verbose("AI Assistant initialized (backward compatibility)")

    def start_session(self, user_query: str, auto_collect_context: bool = True) -> Optional[str]:
        """Start a new diagnosis session"""
        if not self.initialized:
            self.stdio.error("Agent not initialized. Call initialize() first.")
            return None

        try:
            # Create new session
            session = self.session_manager.create_session(user_query)
            self.current_session_id = session.session_id

            # Collect context if requested
            context = {}
            if auto_collect_context:
                self.stdio.verbose("Collecting context...")
                context = self.context_collector.collect_for_agent()
                session.context = context
                self.session_manager.save_session(session.session_id)

            # Update session state
            session.update_state(AgentState.ACTIVE, DiagnosisPhase.CONTEXT_COLLECTION)
            self.session_manager.save_session(session.session_id)

            self.stdio.verbose(f"Started session: {session.session_id}")
            return session.session_id

        except Exception as e:
            self.stdio.error(f"Failed to start session: {e}")
            return None

    def diagnose(self, session_id: str = None) -> Dict[str, Any]:
        """
        Perform diagnosis for a session.
        If session_id is None, uses current session.
        """
        if not self.initialized:
            self.stdio.error("Agent not initialized. Call initialize() first.")
            return {"error": "Agent not initialized"}

        session_id = session_id or self.current_session_id
        if not session_id:
            self.stdio.error("No active session. Call start_session() first.")
            return {"error": "No active session"}

        try:
            session = self.session_manager.get_session(session_id)
            if not session:
                self.stdio.error(f"Session not found: {session_id}")
                return {"error": f"Session not found: {session_id}"}

            self.stdio.verbose(f"Starting diagnosis for session: {session_id}")

            # Perform diagnosis
            results = self.diagnostic_agent.diagnose(
                user_query=session.user_query,
                context=session.context,
                session_id=session_id,
            )

            # Update session with results
            session.hypotheses = results.get("hypotheses", [])
            session.evidence = results.get("evidence", [])
            session.root_causes = results.get("root_causes", [])
            session.solutions = results.get("solutions", [])
            session.reflection = results.get("reflection", {})
            session.reasoning_chain = results.get("reasoning_chain", {})

            # Update state
            if results.get("error"):
                session.update_state(AgentState.FAILED, DiagnosisPhase.COMPLETED)
            else:
                session.update_state(AgentState.COMPLETED, DiagnosisPhase.COMPLETED)

            # Save session
            self.session_manager.save_session(session_id)

            # Auto-save as case if configured and successful
            if self.config["memory"].get("auto_save_resolved", True) and not results.get("error") and results.get("solutions"):

                case = self.case_memory.create_case_from_session(session=session.to_dict(), title=f"Diagnosis: {session.user_query[:50]}...")
                if case:
                    self.stdio.verbose(f"Auto-saved case: {case.case_id}")

            self.stdio.verbose(f"Diagnosis completed for session: {session_id}")
            return results

        except Exception as e:
            self.stdio.error(f"Diagnosis failed: {e}")

            # Update session state on error
            if session_id:
                session = self.session_manager.get_session(session_id)
                if session:
                    session.update_state(AgentState.FAILED, DiagnosisPhase.ERROR)
                    self.session_manager.save_session(session_id)

            return {"error": str(e)}

    def search_similar_cases(self, query: str, threshold: float = 0.3, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar cases"""
        if not self.initialized:
            self.stdio.error("Agent not initialized. Call initialize() first.")
            return []

        try:
            results = self.case_memory.search_similar(query, threshold, limit)

            formatted_results = []
            for case, similarity in results:
                formatted_results.append(
                    {
                        "case_id": case.case_id,
                        "title": case.title,
                        "category": case.category.value,
                        "similarity": similarity,
                        "summary": case.get_summary(),
                    }
                )

            return formatted_results

        except Exception as e:
            self.stdio.error(f"Case search failed: {e}")
            return []

    def get_session_summary(self, session_id: str = None) -> Optional[Dict[str, Any]]:
        """Get summary of a session"""
        session_id = session_id or self.current_session_id
        if not session_id:
            return None

        session = self.session_manager.get_session(session_id)
        if not session:
            return None

        return session.get_summary()

    def list_sessions(self, limit: int = 10, state: str = None) -> List[Dict[str, Any]]:
        """List recent sessions"""
        if not self.initialized:
            return []

        sessions = self.session_manager.get_recent_sessions(limit * 2)  # Get more for filtering

        if state:
            from src.handler.ai.memory.session_manager import SessionState

            try:
                target_state = SessionState(state)
                sessions = [s for s in sessions if s.state == target_state]
            except ValueError:
                pass

        sessions = sessions[:limit]

        return [s.get_summary() for s in sessions]

    def list_cases(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """List cases with optional filters"""
        if not self.initialized:
            return []

        cases = self.case_memory.list_cases(filters)
        return [c.get_summary() for c in cases]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about agent usage"""
        if not self.initialized:
            return {}

        session_stats = self.session_manager.get_session_summary()
        case_stats = self.case_memory.get_statistics()

        return {
            "sessions": session_stats,
            "cases": case_stats,
            "agent": {
                "initialized": self.initialized,
                "components": {
                    "ai_client": self.ai_client is not None,
                    "mcp_server": self.mcp_server is not None,
                    "session_manager": self.session_manager is not None,
                    "case_memory": self.case_memory is not None,
                    "diagnostic_agent": self.diagnostic_agent is not None,
                },
                "current_session": self.current_session_id,
            },
        }

    def run_interactive(self):
        """Run interactive mode"""
        if not self.initialized:
            self.stdio.error("Agent not initialized. Call initialize() first.")
            return

        # Use AI assistant for interactive mode
        if self.ai_assistant:
            self.stdio.verbose("Starting interactive mode via AI Assistant...")
            self.ai_assistant.handle()
        else:
            self.stdio.error("AI Assistant not available for interactive mode")

    def cleanup(self, max_age_days: int = 30):
        """Clean up old data"""
        if not self.initialized:
            return

        session_count = self.session_manager.cleanup_old_sessions(max_age_days)
        case_count = self.case_memory.cleanup_old_cases(max_age_days * 12)  # Cases older than 1 year

        self.stdio.verbose(f"Cleanup completed: {session_count} sessions, {case_count} cases")

    def export_data(self, export_dir: str):
        """Export agent data"""
        if not self.initialized:
            return

        os.makedirs(export_dir, exist_ok=True)

        # Export sessions
        sessions_export_path = os.path.join(export_dir, "sessions_export.json")
        sessions = list(self.session_manager.sessions.values())
        sessions_data = {
            "sessions": [s.to_dict() for s in sessions],
            "exported_at": datetime.now().isoformat(),
            "count": len(sessions),
        }

        with open(sessions_export_path, 'w', encoding='utf-8') as f:
            json.dump(sessions_data, f, indent=2, ensure_ascii=False)

        # Export cases
        cases_export_path = os.path.join(export_dir, "cases_export.json")
        self.case_memory.export_cases(cases_export_path)

        self.stdio.verbose(f"Data exported to {export_dir}")

    def shutdown(self):
        """Shutdown agent and cleanup"""
        self.stdio.verbose("Shutting down obdiag Agent...")

        # Save all sessions
        if self.session_manager:
            self.session_manager.save_all_sessions()

        # Cleanup
        self.cleanup()

        self.stdio.verbose("obdiag Agent shutdown complete")


def create_obdiag_agent_command():
    """Create obdiag agent command for CLI integration"""

    def agent_command(context):
        """Main agent command handler"""
        stdio = context.stdio

        # Parse options
        options = context.options
        subcommand = options.get("subcommand", "interactive")

        # Initialize agent
        agent = ObdiagAgentIntegration(context)

        try:
            if not agent.initialize():
                stdio.error("Failed to initialize obdiag Agent")
                return False

            # Handle subcommands
            if subcommand == "interactive":
                agent.run_interactive()

            elif subcommand == "diagnose":
                query = options.get("query")
                if not query:
                    stdio.error("Query is required for diagnose command")
                    return False

                session_id = agent.start_session(query)
                if not session_id:
                    stdio.error("Failed to start session")
                    return False

                results = agent.diagnose(session_id)
                if "error" in results:
                    stdio.error(f"Diagnosis failed: {results['error']}")
                    return False

                # Display results
                stdio.print("\n" + "=" * 60)
                stdio.print("📊 DIAGNOSIS RESULTS")
                stdio.print("=" * 60)

                if results.get("root_causes"):
                    stdio.print("\n🔍 Root Causes:")
                    for i, cause in enumerate(results["root_causes"], 1):
                        stdio.print(f"  {i}. {cause.get('description', 'Unknown')}")
                        if cause.get("confidence"):
                            stdio.print(f"     Confidence: {cause['confidence']:.2f}")

                if results.get("solutions"):
                    stdio.print("\n💡 Solutions:")
                    for i, solution in enumerate(results["solutions"], 1):
                        stdio.print(f"  {i}. {solution.get('description', 'Unknown')}")
                        if solution.get("risk"):
                            stdio.print(f"     Risk: {solution['risk']}")

                stdio.print(f"\n📝 Session ID: {session_id}")
                stdio.print("=" * 60)

            elif subcommand == "search":
                query = options.get("query")
                if not query:
                    stdio.error("Query is required for search command")
                    return False

                results = agent.search_similar_cases(query)
                if not results:
                    stdio.print("No similar cases found.")
                else:
                    stdio.print(f"\n🔍 Found {len(results)} similar cases:")
                    for i, result in enumerate(results, 1):
                        stdio.print(f"\n{i}. {result['title']}")
                        stdio.print(f"   Category: {result['category']}")
                        stdio.print(f"   Similarity: {result['similarity']:.2f}")
                        stdio.print(f"   Case ID: {result['case_id']}")

            elif subcommand == "sessions":
                limit = options.get("limit", 10)
                state = options.get("state")

                sessions = agent.list_sessions(limit, state)
                if not sessions:
                    stdio.print("No sessions found.")
                else:
                    stdio.print(f"\n📋 Recent Sessions (showing {len(sessions)}):")
                    for i, session in enumerate(sessions, 1):
                        stdio.print(f"\n{i}. {session['user_query'][:50]}...")
                        stdio.print(f"   State: {session['state']}")
                        stdio.print(f"   Created: {session['created_at']}")
                        stdio.print(f"   ID: {session['session_id']}")

            elif subcommand == "cases":
                filters = {}
                if options.get("category"):
                    filters["category"] = options["category"]
                if options.get("min_confidence"):
                    filters["min_confidence"] = float(options["min_confidence"])

                cases = agent.list_cases(filters)
                if not cases:
                    stdio.print("No cases found.")
                else:
                    stdio.print(f"\n📚 Cases (showing {len(cases)}):")
                    for i, case in enumerate(cases, 1):
                        stdio.print(f"\n{i}. {case['title']}")
                        stdio.print(f"   Category: {case['category']}")
                        stdio.print(f"   Confidence: {case['confidence']:.2f}")
                        stdio.print(f"   References: {case['reference_count']}")
                        stdio.print(f"   Case ID: {case['case_id']}")

            elif subcommand == "stats":
                stats = agent.get_statistics()
                stdio.print("\n📈 Agent Statistics:")
                stdio.print(json.dumps(stats, indent=2, ensure_ascii=False))

            elif subcommand == "cleanup":
                max_age = options.get("max_age", 30)
                agent.cleanup(max_age)
                stdio.print(f"Cleanup completed for data older than {max_age} days")

            elif subcommand == "export":
                export_dir = options.get("export_dir", "./obdiag_agent_export")
                agent.export_data(export_dir)
                stdio.print(f"Data exported to {export_dir}")

            elif subcommand == "help":
                stdio.print(
                    """
obdiag Agent Commands:
  interactive    - Start interactive mode (default)
  diagnose       - Run diagnosis for a query
  search         - Search similar cases
  sessions       - List recent sessions
  cases          - List stored cases
  stats          - Show agent statistics
  cleanup        - Clean up old data
  export         - Export agent data
  help           - Show this help

Examples:
  obdiag agent diagnose --query "OceanBase high CPU usage"
  obdiag agent search --query "performance issue"
  obdiag agent sessions --limit 5 --state completed
  obdiag agent cases --category performance --min_confidence 0.7
                """
                )

            else:
                stdio.error(f"Unknown subcommand: {subcommand}")
                stdio.print("Use 'obdiag agent help' for available commands")
                return False

            # Shutdown agent
            agent.shutdown()
            return True

        except Exception as e:
            stdio.error(f"Agent command failed: {e}")
            return False

    return agent_command


# For direct script execution
if __name__ == "__main__":
    print("This module is for integration with obdiag CLI.")
    print("Use 'obdiag agent' command to run the agent.")
