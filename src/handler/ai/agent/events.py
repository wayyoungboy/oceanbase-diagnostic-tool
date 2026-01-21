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
@file: events.py
@desc: Agent event definitions for obdiag Agent
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


class EventType(Enum):
    """Agent event types"""

    # Session events
    SESSION_CREATED = "session_created"
    SESSION_LOADED = "session_loaded"
    SESSION_SAVED = "session_saved"
    SESSION_CLOSED = "session_closed"

    # State events
    STATE_CHANGED = "state_changed"
    PHASE_CHANGED = "phase_changed"

    # Diagnosis events
    DIAGNOSIS_STARTED = "diagnosis_started"
    DIAGNOSIS_COMPLETED = "diagnosis_completed"
    DIAGNOSIS_FAILED = "diagnosis_failed"

    # Context events
    CONTEXT_COLLECTED = "context_collected"
    CONTEXT_UPDATED = "context_updated"

    # Symptom events
    SYMPTOMS_EXTRACTED = "symptoms_extracted"
    SYMPTOMS_ANALYZED = "symptoms_analyzed"

    # Hypothesis events
    HYPOTHESES_GENERATED = "hypotheses_generated"
    HYPOTHESIS_SELECTED = "hypothesis_selected"
    HYPOTHESIS_CONFIRMED = "hypothesis_confirmed"
    HYPOTHESIS_REJECTED = "hypothesis_rejected"

    # Planning events
    EVIDENCE_PLANNED = "evidence_planned"
    PLAN_GENERATED = "plan_generated"
    PLAN_UPDATED = "plan_updated"

    # Tool events
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    TOOL_CONFIRMATION_REQUIRED = "tool_confirmation_required"
    TOOL_CONFIRMATION_GRANTED = "tool_confirmation_granted"
    TOOL_CONFIRMATION_DENIED = "tool_confirmation_denied"

    # Evidence events
    EVIDENCE_COLLECTED = "evidence_collected"
    EVIDENCE_ANALYZED = "evidence_analyzed"
    EVIDENCE_EVALUATED = "evidence_evaluated"

    # Analysis events
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    CONFIDENCE_UPDATED = "confidence_updated"

    # Solution events
    SOLUTIONS_GENERATED = "solutions_generated"
    SOLUTION_SELECTED = "solution_selected"
    SOLUTION_IMPLEMENTED = "solution_implemented"

    # Reflection events
    REFLECTION_STARTED = "reflection_started"
    REFLECTION_COMPLETED = "reflection_completed"

    # Error events
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"

    # User interaction events
    USER_INPUT_RECEIVED = "user_input_received"
    USER_CONFIRMATION = "user_confirmation"
    USER_FEEDBACK = "user_feedback"

    # System events
    AGENT_INITIALIZED = "agent_initialized"
    AGENT_CLOSED = "agent_closed"
    MEMORY_UPDATED = "memory_updated"
    PROGRESS_UPDATED = "progress_updated"


@dataclass
class AgentEvent:
    """
    Agent event data class

    Represents an event that occurs during the agent's operation.
    Events are used for logging, monitoring, and triggering actions.
    """

    # Event metadata
    event_type: EventType
    timestamp: str
    session_id: str

    # Event data
    data: Dict[str, Any] = field(default_factory=dict)

    # Source of the event
    source: str = "agent"

    # Optional correlation ID for tracking related events
    correlation_id: Optional[str] = None

    # Optional severity level
    severity: str = "info"  # info, warning, error, critical

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "data": self.data,
            "source": self.source,
            "correlation_id": self.correlation_id,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentEvent':
        """Create event from dictionary"""
        return cls(
            event_type=EventType(data["event_type"]),
            timestamp=data["timestamp"],
            session_id=data["session_id"],
            data=data.get("data", {}),
            source=data.get("source", "agent"),
            correlation_id=data.get("correlation_id"),
            severity=data.get("severity", "info"),
        )


class EventBus:
    """
    Simple event bus for agent event handling

    Provides publish-subscribe pattern for agent events.
    """

    def __init__(self):
        self._subscribers: Dict[EventType, list] = {}

    def subscribe(self, event_type: EventType, callback):
        """
        Subscribe to events of a specific type

        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event occurs
                      Signature: callback(event: AgentEvent) -> None
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback):
        """Unsubscribe from events"""
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    def publish(self, event: AgentEvent):
        """
        Publish an event to all subscribers

        Args:
            event: Event to publish
        """
        event_type = event.event_type

        # Notify subscribers for this specific event type
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    # Don't let subscriber errors break the event bus
                    print(f"Event subscriber error: {e}")

        # Also notify wildcard subscribers if any
        if EventType.ERROR_OCCURRED in self._subscribers and event.severity in ["error", "critical"]:
            for callback in self._subscribers[EventType.ERROR_OCCURRED]:
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error event subscriber error: {e}")


# Event factory functions for common events


def create_session_event(event_type: EventType, session_id: str, data: Dict[str, Any] = None, source: str = "agent") -> AgentEvent:
    """Create a session-related event"""
    return AgentEvent(
        event_type=event_type,
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        data=data or {},
        source=source,
    )


def create_state_event(session_id: str, old_state: str, new_state: str, old_phase: str = None, new_phase: str = None, source: str = "agent") -> AgentEvent:
    """Create a state change event"""
    data = {
        "old_state": old_state,
        "new_state": new_state,
    }

    if old_phase:
        data["old_phase"] = old_phase
    if new_phase:
        data["new_phase"] = new_phase

    return AgentEvent(
        event_type=EventType.STATE_CHANGED,
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        data=data,
        source=source,
    )


def create_tool_event(event_type: EventType, session_id: str, tool_name: str, arguments: Dict[str, Any] = None, output: str = None, success: bool = None, error: str = None, source: str = "agent") -> AgentEvent:
    """Create a tool-related event"""
    data = {
        "tool_name": tool_name,
        "arguments": arguments or {},
    }

    if output is not None:
        data["output"] = output
    if success is not None:
        data["success"] = success
    if error is not None:
        data["error"] = error

    return AgentEvent(
        event_type=event_type,
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        data=data,
        source=source,
        severity="error" if error else "info",
    )


def create_error_event(session_id: str, error_message: str, error_type: str = None, stack_trace: str = None, context: Dict[str, Any] = None, source: str = "agent") -> AgentEvent:
    """Create an error event"""
    data = {
        "error_message": error_message,
    }

    if error_type:
        data["error_type"] = error_type
    if stack_trace:
        data["stack_trace"] = stack_trace
    if context:
        data["context"] = context

    return AgentEvent(
        event_type=EventType.ERROR_OCCURRED,
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        data=data,
        source=source,
        severity="error",
    )


def create_progress_event(session_id: str, progress: float, message: str = None, current_step: str = None, total_steps: int = None, source: str = "agent") -> AgentEvent:  # 0.0 to 1.0
    """Create a progress update event"""
    data = {
        "progress": progress,
    }

    if message:
        data["message"] = message
    if current_step:
        data["current_step"] = current_step
    if total_steps:
        data["total_steps"] = total_steps

    return AgentEvent(
        event_type=EventType.PROGRESS_UPDATED,
        timestamp=datetime.now().isoformat(),
        session_id=session_id,
        data=data,
        source=source,
    )


# Event handlers for common use cases


class EventLogger:
    """Event handler that logs events to console"""

    def __init__(self, stdio=None):
        self.stdio = stdio

    def __call__(self, event: AgentEvent):
        """Handle event by logging it"""
        if self.stdio:
            if event.severity == "error":
                self.stdio.error(f"[{event.event_type.value}] {event.data}")
            elif event.severity == "warning":
                self.stdio.warn(f"[{event.event_type.value}] {event.data}")
            else:
                self.stdio.verbose(f"[{event.event_type.value}] {event.data}")
        else:
            # Fallback to print
            print(f"[{event.timestamp}] [{event.event_type.value}] {event.data}")


class EventPersister:
    """Event handler that persists events to storage"""

    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or "~/.obdiag/agent_events.log"

    def __call__(self, event: AgentEvent):
        """Handle event by persisting it"""
        import json
        import os

        event_dict = event.to_dict()
        event_line = json.dumps(event_dict, ensure_ascii=False)

        # Ensure directory exists
        storage_path = os.path.expanduser(self.storage_path)
        storage_dir = os.path.dirname(storage_path)
        if storage_dir and not os.path.exists(storage_dir):
            os.makedirs(storage_dir, exist_ok=True)

        # Append event to file
        try:
            with open(storage_path, 'a', encoding='utf-8') as f:
                f.write(event_line + "\n")
        except Exception:
            pass  # Don't fail if persisting fails
