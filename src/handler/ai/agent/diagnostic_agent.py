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
@file: diagnostic_agent.py
@desc: Diagnostic Agent core class for obdiag Agent
"""

import json
import os
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict

from src.handler.ai.openai_client_enhanced import ObdiagAIClientEnhanced
from src.handler.ai.mcp_server_enhanced import EnhancedMCPServer, ConfirmationMode, ToolSensitivityLevel


class AgentState(Enum):
    """Agent state enumeration"""

    IDLE = "idle"
    COLLECTING_CONTEXT = "collecting_context"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    ERROR = "error"


class DiagnosisPhase(Enum):
    """Diagnosis phase enumeration"""

    INITIAL = "initial"
    SYMPTOM_COLLECTION = "symptom_collection"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    EVIDENCE_COLLECTION = "evidence_collection"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    SOLUTION_RECOMMENDATION = "solution_recommendation"
    VALIDATION = "validation"


@dataclass
class AgentEvent:
    """Agent event data class"""

    timestamp: str
    event_type: str
    data: Dict[str, Any]
    source: str = "agent"


@dataclass
class DiagnosisSession:
    """Diagnosis session data class"""

    session_id: str
    created_at: str
    updated_at: str
    state: AgentState
    current_phase: DiagnosisPhase
    user_query: str
    context: Dict[str, Any] = field(default_factory=dict)
    symptoms: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    conclusions: List[Dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    def update(self, **kwargs):
        """Update session fields"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now().isoformat()


@dataclass
class ToolExecutionResult:
    """Tool execution result data class"""

    tool_name: str
    arguments: Dict[str, Any]
    success: bool
    output: str
    execution_time: float
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class DiagnosticAgent:
    """
    Diagnostic Agent core class for obdiag Agent.

    Manages the complete diagnostic process including:
    1. Context collection
    2. Symptom analysis
    3. Hypothesis generation
    4. Evidence collection
    5. Root cause analysis
    6. Solution recommendation
    7. Self-reflection
    """

    def __init__(
        self,
        context,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "gpt-4",
        config_path: Optional[str] = None,
        session_id: Optional[str] = None,
        confirmation_mode: ConfirmationMode = ConfirmationMode.ALWAYS,
        auto_confirm_level: ToolSensitivityLevel = ToolSensitivityLevel.MEDIUM,
    ):
        """
        Initialize Diagnostic Agent

        Args:
            context: Application context
            api_key: OpenAI API key
            base_url: Optional custom API base URL
            model: Model name to use
            config_path: Path to obdiag config file
            session_id: Optional session ID (generated if not provided)
            confirmation_mode: Confirmation mode for sensitive tools
            auto_confirm_level: Auto-confirm level for tools
        """
        self.context = context
        self.stdio = context.stdio
        self.config_path = config_path or os.path.expanduser("~/.obdiag/config.yml")

        # Generate session ID if not provided
        self.session_id = session_id or self._generate_session_id()

        # Initialize AI client
        self.ai_client = ObdiagAIClientEnhanced(
            context=context,
            api_key=api_key,
            base_url=base_url,
            model=model,
            config_path=self.config_path,
            confirmation_mode=confirmation_mode,
            auto_confirm_level=auto_confirm_level,
        )

        # Initialize session
        self.session = DiagnosisSession(
            session_id=self.session_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            state=AgentState.IDLE,
            current_phase=DiagnosisPhase.INITIAL,
            user_query="",
        )

        # Event handlers
        self.event_handlers: List[Callable[[AgentEvent], None]] = []

        # Tool execution history
        self.tool_history: List[ToolExecutionResult] = []

        # Load existing session if available
        self._load_session()

        self.stdio.verbose(f"Diagnostic Agent initialized with session ID: {self.session_id}")

    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = os.urandom(4).hex()
        return f"obdiag_agent_{timestamp}_{random_suffix}"

    def _emit_event(self, event_type: str, data: Dict[str, Any], source: str = "agent"):
        """Emit agent event"""
        event = AgentEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            data=data,
            source=source,
        )

        # Call event handlers
        for handler in self.event_handlers:
            try:
                handler(event)
            except Exception as e:
                self.stdio.warn(f"Event handler failed: {e}")

        # Log event
        self.stdio.verbose(f"Agent event: {event_type} - {data}")

    def _load_session(self):
        """Load session from persistent storage"""
        session_dir = os.path.expanduser("~/.obdiag/agent_sessions")
        session_file = os.path.join(session_dir, f"{self.session_id}.json")

        if os.path.exists(session_file):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)

                # Update session from loaded data
                for key, value in session_data.items():
                    if hasattr(self.session, key):
                        setattr(self.session, key, value)

                self.stdio.verbose(f"Loaded existing session: {self.session_id}")
                self._emit_event("session_loaded", {"session_id": self.session_id})
            except Exception as e:
                self.stdio.warn(f"Failed to load session: {e}")

    def _save_session(self):
        """Save session to persistent storage"""
        session_dir = os.path.expanduser("~/.obdiag/agent_sessions")

        # Ensure directory exists
        if not os.path.exists(session_dir):
            os.makedirs(session_dir, exist_ok=True)

        session_file = os.path.join(session_dir, f"{self.session_id}.json")

        try:
            session_data = self.session.to_dict()
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            self.stdio.verbose(f"Session saved: {self.session_id}")
            self._emit_event("session_saved", {"session_id": self.session_id})
        except Exception as e:
            self.stdio.warn(f"Failed to save session: {e}")

    def register_event_handler(self, handler: Callable[[AgentEvent], None]):
        """Register event handler"""
        self.event_handlers.append(handler)

    def update_state(self, new_state: AgentState, phase: Optional[DiagnosisPhase] = None):
        """Update agent state"""
        old_state = self.session.state
        self.session.state = new_state

        if phase:
            old_phase = self.session.current_phase
            self.session.current_phase = phase

        self._emit_event(
            "state_changed",
            {
                "old_state": old_state.value,
                "new_state": new_state.value,
                "old_phase": old_phase.value if phase else None,
                "new_phase": phase.value if phase else None,
            },
        )

        self._save_session()

    def start_diagnosis(self, user_query: str) -> DiagnosisSession:
        """
        Start a new diagnosis session

        Args:
            user_query: User's query or problem description

        Returns:
            DiagnosisSession object
        """
        self.stdio.verbose(f"Starting diagnosis for query: {user_query}")

        # Update session
        self.session.user_query = user_query
        self.update_state(AgentState.COLLECTING_CONTEXT, DiagnosisPhase.INITIAL)

        self._emit_event(
            "diagnosis_started",
            {
                "session_id": self.session_id,
                "user_query": user_query,
            },
        )

        # Collect initial context
        self._collect_initial_context()

        return self.session

    def _collect_initial_context(self):
        """Collect initial context information"""
        self.stdio.verbose("Collecting initial context...")

        # Update state
        self.update_state(AgentState.COLLECTING_CONTEXT, DiagnosisPhase.SYMPTOM_COLLECTION)

        # Collect basic cluster information
        context_info = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "user_query": self.session.user_query,
        }

        # Try to gather basic cluster info from config
        if os.path.exists(self.config_path):
            try:
                import yaml

                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)

                if config and "obcluster" in config:
                    obcluster = config["obcluster"]
                    context_info["cluster_name"] = obcluster.get("ob_cluster_name", "unknown")
                    context_info["db_host"] = obcluster.get("db_host", "unknown")
                    context_info["db_port"] = obcluster.get("db_port", 2881)

                    # Count nodes
                    nodes = obcluster.get("servers", {}).get("nodes", [])
                    context_info["node_count"] = len(nodes)

                    self.stdio.verbose(f"Found cluster: {context_info['cluster_name']} with {context_info['node_count']} nodes")
            except Exception as e:
                self.stdio.warn(f"Failed to parse config for context: {e}")

        # Update session context
        self.session.context = context_info

        self._emit_event("context_collected", {"context": context_info})

        # Move to analysis phase
        self.update_state(AgentState.ANALYZING, DiagnosisPhase.SYMPTOM_COLLECTION)

    def analyze_symptoms(self) -> List[Dict[str, Any]]:
        """
        Analyze user query to extract symptoms

        Returns:
            List of extracted symptoms
        """
        self.stdio.verbose("Analyzing symptoms from user query...")

        # Update state
        self.update_state(AgentState.ANALYZING, DiagnosisPhase.SYMPTOM_COLLECTION)

        # Use AI to extract symptoms
        prompt = f"""
        Analyze the following user query about OceanBase database issues and extract symptoms:
        
        User Query: {self.session.user_query}
        
        Extract symptoms in the following format:
        1. Symptom description
        2. Severity (low, medium, high, critical)
        3. Affected components (database, network, storage, memory, CPU, etc.)
        4. Timeframe (if mentioned)
        
        Return the symptoms as a JSON array.
        """

        try:
            response = self.ai_client.chat(prompt, [])

            # Parse response (assuming JSON format)
            try:
                symptoms = json.loads(response)
                if not isinstance(symptoms, list):
                    symptoms = [{"description": response, "severity": "medium"}]
            except json.JSONDecodeError:
                # If not JSON, create a simple symptom entry
                symptoms = [
                    {
                        "description": response,
                        "severity": "medium",
                        "components": ["unknown"],
                        "extracted_from": self.session.user_query,
                    }
                ]

            # Update session
            self.session.symptoms = symptoms

            self._emit_event(
                "symptoms_analyzed",
                {
                    "symptom_count": len(symptoms),
                    "symptoms": symptoms,
                },
            )

            self.stdio.verbose(f"Extracted {len(symptoms)} symptoms")

            # Move to hypothesis generation
            self.update_state(AgentState.ANALYZING, DiagnosisPhase.HYPOTHESIS_GENERATION)

            return symptoms

        except Exception as e:
            self.stdio.error(f"Failed to analyze symptoms: {e}")
            self.update_state(AgentState.ERROR)
            return []

    def generate_hypotheses(self, symptoms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate hypotheses based on symptoms

        Args:
            symptoms: List of extracted symptoms

        Returns:
            List of generated hypotheses
        """
        self.stdio.verbose("Generating hypotheses...")

        # Update state
        self.update_state(AgentState.ANALYZING, DiagnosisPhase.HYPOTHESIS_GENERATION)

        # Format symptoms for prompt
        symptoms_text = "\n".join([f"{i+1}. {s.get('description', 'Unknown')} (Severity: {s.get('severity', 'medium')})" for i, s in enumerate(symptoms)])

        prompt = f"""
        Based on the following OceanBase database symptoms, generate possible root cause hypotheses:
        
        Symptoms:
        {symptoms_text}
        
        Context:
        - Cluster: {self.session.context.get('cluster_name', 'unknown')}
        - Nodes: {self.session.context.get('node_count', 'unknown')}
        
        For each hypothesis, provide:
        1. Hypothesis description
        2. Likelihood (low, medium, high)
        3. Required evidence to confirm
        4. Potential impact
        5. Suggested diagnostic tools/tests
        
        Return the hypotheses as a JSON array.
        """

        try:
            response = self.ai_client.chat(prompt, [])

            # Parse response
            try:
                hypotheses = json.loads(response)
                if not isinstance(hypotheses, list):
                    hypotheses = [{"description": response, "likelihood": "medium"}]
            except json.JSONDecodeError:
                # If not JSON, create a simple hypothesis
                hypotheses = [
                    {
                        "description": response,
                        "likelihood": "medium",
                        "required_evidence": ["unknown"],
                        "impact": "unknown",
                        "tools": ["check", "gather_log"],
                    }
                ]

            # Add IDs and timestamps
            for i, hypothesis in enumerate(hypotheses):
                hypothesis["id"] = f"hypothesis_{i+1}"
                hypothesis["generated_at"] = datetime.now().isoformat()
                hypothesis["confidence"] = 0.0  # Initial confidence

            # Update session
            self.session.hypotheses = hypotheses

            self._emit_event(
                "hypotheses_generated",
                {
                    "hypothesis_count": len(hypotheses),
                    "hypotheses": hypotheses,
                },
            )

            self.stdio.verbose(f"Generated {len(hypotheses)} hypotheses")

            # Move to evidence collection
            self.update_state(AgentState.PLANNING, DiagnosisPhase.EVIDENCE_COLLECTION)

            return hypotheses

        except Exception as e:
            self.stdio.error(f"Failed to generate hypotheses: {e}")
            self.update_state(AgentState.ERROR)
            return []

    def plan_evidence_collection(self, hypotheses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Plan evidence collection for hypotheses

        Args:
            hypotheses: List of hypotheses to investigate

        Returns:
            List of planned evidence collection actions
        """
        self.stdio.verbose("Planning evidence collection...")

        # Update state
        self.update_state(AgentState.PLANNING, DiagnosisPhase.EVIDENCE_COLLECTION)

        # Format hypotheses for prompt
        hypotheses_text = "\n".join([f"{i+1}. {h.get('description', 'Unknown')} (Likelihood: {h.get('likelihood', 'medium')})" for i, h in enumerate(hypotheses)])

        prompt = f"""
        Plan evidence collection for the following OceanBase database hypotheses:
        
        Hypotheses:
        {hypotheses_text}
        
        Available diagnostic tools:
        - gather_log: Collect OceanBase logs
        - gather_sysstat: Collect system statistics
        - gather_perf: Collect performance data
        - analyze_log: Analyze logs for errors
        - check: Run health checks
        - rca_run: Run root cause analysis
        - execute_sql: Execute SQL queries (sensitive)
        - execute_ssh: Execute commands via SSH (sensitive)
        
        For each hypothesis, plan:
        1. Which tools to use
        2. What specific evidence to collect
        3. Execution order (parallel vs sequential)
        4. Expected outcomes
        
        Consider:
        - Start with low-risk, high-value evidence
        - Minimize impact on production systems
        - Use sensitive tools only when necessary
        
        Return the plan as a JSON array of evidence collection actions.
        """

        try:
            response = self.ai_client.chat(prompt, [])

            # Parse response
            try:
                plan = json.loads(response)
                if not isinstance(plan, list):
                    plan = [{"action": response, "tools": ["check"]}]
            except json.JSONDecodeError:
                # If not JSON, create a simple plan
                plan = [
                    {
                        "action": "Run basic health checks",
                        "tools": ["check"],
                        "hypothesis_ids": [h.get("id") for h in hypotheses],
                        "priority": "high",
                    }
                ]

            # Add metadata
            for i, action in enumerate(plan):
                action["id"] = f"action_{i+1}"
                action["planned_at"] = datetime.now().isoformat()
                action["status"] = "pending"
                action["execution_order"] = i + 1

            self._emit_event(
                "evidence_planned",
                {
                    "action_count": len(plan),
                    "plan": plan,
                },
            )

            self.stdio.verbose(f"Planned {len(plan)} evidence collection actions")

            # Move to execution
            self.update_state(AgentState.EXECUTING, DiagnosisPhase.EVIDENCE_COLLECTION)

            return plan

        except Exception as e:
            self.stdio.error(f"Failed to plan evidence collection: {e}")
            self.update_state(AgentState.ERROR)
            return []

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """
        Execute a diagnostic tool

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            ToolExecutionResult object
        """
        self.stdio.verbose(f"Executing tool: {tool_name} with args: {arguments}")

        # Update state
        self.update_state(AgentState.EXECUTING)

        start_time = time.time()

        self._emit_event(
            "tool_execution_started",
            {
                "tool_name": tool_name,
                "arguments": arguments,
            },
        )

        try:
            # Execute tool via AI client
            output = self.ai_client._execute_tool(tool_name, arguments)

            execution_time = time.time() - start_time

            # Create result
            result = ToolExecutionResult(
                tool_name=tool_name,
                arguments=arguments,
                success=True,  # Assume success for now
                output=output,
                execution_time=execution_time,
                timestamp=datetime.now().isoformat(),
                metadata={"session_id": self.session_id},
            )

            # Add to history
            self.tool_history.append(result)

            # Add to session
            self.session.tool_calls.append(
                {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "success": True,
                    "execution_time": execution_time,
                    "timestamp": result.timestamp,
                }
            )

            self._emit_event(
                "tool_execution_completed",
                {
                    "tool_name": tool_name,
                    "success": True,
                    "execution_time": execution_time,
                    "output_preview": output[:200] + "..." if len(output) > 200 else output,
                },
            )

            self.stdio.verbose(f"Tool {tool_name} executed successfully in {execution_time:.2f}s")

            return result

        except Exception as e:
            execution_time = time.time() - start_time

            result = ToolExecutionResult(
                tool_name=tool_name,
                arguments=arguments,
                success=False,
                output=f"Tool execution failed: {str(e)}",
                execution_time=execution_time,
                timestamp=datetime.now().isoformat(),
                metadata={"error": str(e), "session_id": self.session_id},
            )

            # Add to history
            self.tool_history.append(result)

            # Add to session
            self.session.tool_calls.append(
                {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "success": False,
                    "execution_time": execution_time,
                    "timestamp": result.timestamp,
                    "error": str(e),
                }
            )

            self._emit_event(
                "tool_execution_failed",
                {
                    "tool_name": tool_name,
                    "error": str(e),
                    "execution_time": execution_time,
                },
            )

            self.stdio.error(f"Tool {tool_name} execution failed: {e}")

            return result

    def analyze_evidence(self, tool_results: List[ToolExecutionResult]) -> List[Dict[str, Any]]:
        """
        Analyze collected evidence

        Args:
            tool_results: List of tool execution results

        Returns:
            List of evidence analysis results
        """
        self.stdio.verbose("Analyzing collected evidence...")

        # Update state
        self.update_state(AgentState.ANALYZING, DiagnosisPhase.ROOT_CAUSE_ANALYSIS)

        # Format tool results for analysis
        evidence_text = "\n".join([f"Tool: {r.tool_name}\n" f"Arguments: {r.arguments}\n" f"Output: {r.output[:500]}...\n" f"Success: {r.success}\n" for r in tool_results[-10:]])  # Last 10 results

        prompt = f"""
        Analyze the following diagnostic evidence collected from OceanBase database:
        
        Evidence Collected:
        {evidence_text}
        
        Original Symptoms:
        {json.dumps(self.session.symptoms, indent=2, ensure_ascii=False)}
        
        Hypotheses Being Investigated:
        {json.dumps(self.session.hypotheses, indent=2, ensure_ascii=False)}
        
        Analyze this evidence to:
        1. Confirm or reject each hypothesis
        2. Identify root causes
        3. Calculate confidence scores
        4. Suggest additional evidence if needed
        
        Return analysis as a JSON object with:
        - confirmed_hypotheses: List of confirmed hypotheses with confidence scores
        - rejected_hypotheses: List of rejected hypotheses with reasons
        - root_causes: List of identified root causes
        - confidence_overall: Overall confidence score (0.0-1.0)
        - next_steps: Suggested next actions
        """

        try:
            response = self.ai_client.chat(prompt, [])

            # Parse response
            try:
                analysis = json.loads(response)
                if not isinstance(analysis, dict):
                    analysis = {"root_causes": [response], "confidence_overall": 0.5}
            except json.JSONDecodeError:
                # If not JSON, create simple analysis
                analysis = {
                    "root_causes": ["Analysis could not be parsed"],
                    "confidence_overall": 0.0,
                    "next_steps": ["Collect more evidence"],
                }

            # Update session
            self.session.evidence = [r.to_dict() for r in tool_results]

            # Store conclusions
            self.session.conclusions = [
                {
                    "type": "evidence_analysis",
                    "analysis": analysis,
                    "timestamp": datetime.now().isoformat(),
                }
            ]

            # Update confidence
            if "confidence_overall" in analysis:
                self.session.confidence_score = analysis["confidence_overall"]

            self._emit_event(
                "evidence_analyzed",
                {
                    "analysis": analysis,
                    "confidence": self.session.confidence_score,
                },
            )

            self.stdio.verbose(f"Evidence analysis completed. Confidence: {self.session.confidence_score:.2f}")

            # Move to solution recommendation
            self.update_state(AgentState.ANALYZING, DiagnosisPhase.SOLUTION_RECOMMENDATION)

            return analysis

        except Exception as e:
            self.stdio.error(f"Failed to analyze evidence: {e}")
            self.update_state(AgentState.ERROR)
            return {}

    def generate_solutions(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate solutions based on analysis

        Args:
            analysis: Evidence analysis results

        Returns:
            List of recommended solutions
        """
        self.stdio.verbose("Generating solutions...")

        # Update state
        self.update_state(AgentState.ANALYZING, DiagnosisPhase.SOLUTION_RECOMMENDATION)

        prompt = f"""
        Based on the following OceanBase database diagnosis analysis, generate recommended solutions:
        
        Analysis:
        {json.dumps(analysis, indent=2, ensure_ascii=False)}
        
        Original Problem:
        {self.session.user_query}
        
        For each solution, provide:
        1. Solution description
        2. Implementation steps
        3. Expected outcome
        4. Risk level (low, medium, high)
        5. Estimated time/effort
        6. Required permissions/tools
        
        Prioritize solutions by:
        1. Quick wins (low effort, high impact)
        2. Preventive measures
        3. Long-term fixes
        
        Return solutions as a JSON array.
        """

        try:
            response = self.ai_client.chat(prompt, [])

            # Parse response
            try:
                solutions = json.loads(response)
                if not isinstance(solutions, list):
                    solutions = [{"description": response, "risk": "medium"}]
            except json.JSONDecodeError:
                # If not JSON, create simple solution
                solutions = [
                    {
                        "description": "Review the analysis and implement appropriate fixes",
                        "implementation": ["Review findings", "Plan implementation", "Execute fixes"],
                        "risk": "medium",
                        "effort": "medium",
                    }
                ]

            # Add metadata
            for i, solution in enumerate(solutions):
                solution["id"] = f"solution_{i+1}"
                solution["generated_at"] = datetime.now().isoformat()
                solution["priority"] = i + 1

            # Update session conclusions
            self.session.conclusions.append(
                {
                    "type": "solutions",
                    "solutions": solutions,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            self._emit_event(
                "solutions_generated",
                {
                    "solution_count": len(solutions),
                    "solutions": solutions,
                },
            )

            self.stdio.verbose(f"Generated {len(solutions)} solutions")

            # Move to validation
            self.update_state(AgentState.REFLECTING, DiagnosisPhase.VALIDATION)

            return solutions

        except Exception as e:
            self.stdio.error(f"Failed to generate solutions: {e}")
            self.update_state(AgentState.ERROR)
            return []

    def reflect_on_diagnosis(self) -> Dict[str, Any]:
        """
        Reflect on the diagnosis process and outcomes

        Returns:
            Reflection results
        """
        self.stdio.verbose("Reflecting on diagnosis process...")

        # Update state
        self.update_state(AgentState.REFLECTING, DiagnosisPhase.VALIDATION)

        # Prepare reflection data
        reflection_data = {
            "session": self.session.to_dict(),
            "tool_history": [r.to_dict() for r in self.tool_history],
            "timeline": {
                "start": self.session.created_at,
                "end": datetime.now().isoformat(),
                "duration_seconds": (datetime.fromisoformat(datetime.now().isoformat()) - datetime.fromisoformat(self.session.created_at)).total_seconds(),
            },
        }

        prompt = f"""
        Reflect on the following OceanBase database diagnosis session:
        
        {json.dumps(reflection_data, indent=2, ensure_ascii=False)}
        
        Evaluate:
        1. Quality of diagnosis process
        2. Effectiveness of tool usage
        3. Accuracy of hypotheses
        4. Completeness of evidence
        5. Usefulness of solutions
        6. Areas for improvement
        
        Provide reflection as a JSON object with:
        - strengths: What worked well
        - weaknesses: What could be improved
        - lessons_learned: Key takeaways
        - improvement_suggestions: Specific suggestions
        - overall_rating: 1-10 scale
        """

        try:
            response = self.ai_client.chat(prompt, [])

            # Parse response
            try:
                reflection = json.loads(response)
                if not isinstance(reflection, dict):
                    reflection = {"overall_rating": 5, "strengths": [response]}
            except json.JSONDecodeError:
                # If not JSON, create simple reflection
                reflection = {
                    "overall_rating": 5,
                    "strengths": ["Diagnosis process completed"],
                    "weaknesses": ["Reflection could not be parsed"],
                }

            # Update session
            self.session.conclusions.append(
                {
                    "type": "reflection",
                    "reflection": reflection,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Final state update
            self.update_state(AgentState.COMPLETED)

            self._emit_event(
                "diagnosis_completed",
                {
                    "session_id": self.session_id,
                    "reflection": reflection,
                    "confidence": self.session.confidence_score,
                },
            )

            self.stdio.verbose(f"Diagnosis completed. Reflection rating: {reflection.get('overall_rating', 'N/A')}")

            # Save final session state
            self._save_session()

            return reflection

        except Exception as e:
            self.stdio.error(f"Failed to reflect on diagnosis: {e}")
            self.update_state(AgentState.ERROR)
            return {}

    def run_complete_diagnosis(self, user_query: str) -> DiagnosisSession:
        """
        Run complete diagnosis workflow

        Args:
            user_query: User's query or problem description

        Returns:
            Completed DiagnosisSession
        """
        try:
            # Start diagnosis
            self.start_diagnosis(user_query)

            # Analyze symptoms
            symptoms = self.analyze_symptoms()
            if not symptoms:
                raise ValueError("No symptoms could be extracted")

            # Generate hypotheses
            hypotheses = self.generate_hypotheses(symptoms)
            if not hypotheses:
                raise ValueError("No hypotheses could be generated")

            # Plan evidence collection
            plan = self.plan_evidence_collection(hypotheses)

            # Execute evidence collection (simplified - execute first action)
            tool_results = []
            if plan:
                # Execute the first planned action
                first_action = plan[0]
                if "tools" in first_action and first_action["tools"]:
                    # Execute first tool from the plan
                    tool_name = first_action["tools"][0]
                    # Use default arguments or extract from plan
                    arguments = first_action.get("arguments", {})
                    result = self.execute_tool(tool_name, arguments)
                    tool_results.append(result)

            # Analyze evidence
            analysis = self.analyze_evidence(tool_results)

            # Generate solutions
            solutions = self.generate_solutions(analysis)

            # Reflect on process
            reflection = self.reflect_on_diagnosis()

            self.stdio.verbose(f"Complete diagnosis workflow finished for: {user_query}")

            return self.session

        except Exception as e:
            self.stdio.error(f"Diagnosis workflow failed: {e}")
            self.update_state(AgentState.ERROR)
            raise

    def get_session_summary(self) -> Dict[str, Any]:
        """Get session summary"""
        return {
            "session_id": self.session_id,
            "state": self.session.state.value,
            "phase": self.session.current_phase.value,
            "user_query": self.session.user_query,
            "symptom_count": len(self.session.symptoms),
            "hypothesis_count": len(self.session.hypotheses),
            "tool_call_count": len(self.session.tool_calls),
            "confidence": self.session.confidence_score,
            "created_at": self.session.created_at,
            "updated_at": self.session.updated_at,
        }

    def close(self):
        """Clean up resources"""
        if self.ai_client:
            self.ai_client.close()

        # Save final session state
        self._save_session()

        self.stdio.verbose(f"Diagnostic Agent closed for session: {self.session_id}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False
