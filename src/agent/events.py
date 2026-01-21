"""Streaming events for agent communication."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Types of streaming events."""

    # Planning events
    PLAN_STARTED = "plan_started"
    PLAN_STEP = "plan_step"
    PLAN_COMPLETED = "plan_completed"

    # Approval events
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"

    # Execution events
    EXECUTION_STARTED = "execution_started"
    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    EXECUTION_COMPLETED = "execution_completed"

    # Tool events
    TOOL_STARTED = "tool_started"
    TOOL_OUTPUT = "tool_output"
    TOOL_COMPLETED = "tool_completed"

    # Document events
    DOCUMENT_UPDATE = "document_update"

    # Job events
    JOB_STARTED = "job_started"
    JOB_PROGRESS = "job_progress"
    JOB_COMPLETED = "job_completed"

    # LLM events
    LLM_TOKEN = "llm_token"
    LLM_RESPONSE = "llm_response"

    # Error events
    ERROR = "error"

    # Message events
    MESSAGE = "message"


@dataclass
class StreamEvent:
    """Base streaming event."""

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class PlanStep:
    """A step in the execution plan."""

    step_number: int
    description: str
    tool_name: str | None = None
    requires_approval: bool = False
    status: str = "pending"  # pending, in_progress, completed, failed, skipped


@dataclass
class Plan:
    """Execution plan created by the planner."""

    goal: str
    steps: list[PlanStep]
    reasoning: str
    requires_approval: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert plan to dictionary."""
        return {
            "goal": self.goal,
            "steps": [
                {
                    "step_number": step.step_number,
                    "description": step.description,
                    "tool_name": step.tool_name,
                    "requires_approval": step.requires_approval,
                    "status": step.status,
                }
                for step in self.steps
            ],
            "reasoning": self.reasoning,
            "requires_approval": self.requires_approval,
        }


# Event factory functions for convenience
def plan_started_event(goal: str) -> StreamEvent:
    """Create a plan started event."""
    return StreamEvent(
        event_type=EventType.PLAN_STARTED,
        data={"goal": goal},
    )


def plan_step_event(step: PlanStep) -> StreamEvent:
    """Create a plan step event."""
    return StreamEvent(
        event_type=EventType.PLAN_STEP,
        data={
            "step_number": step.step_number,
            "description": step.description,
            "tool_name": step.tool_name,
            "requires_approval": step.requires_approval,
        },
    )


def plan_completed_event(plan: Plan) -> StreamEvent:
    """Create a plan completed event."""
    return StreamEvent(
        event_type=EventType.PLAN_COMPLETED,
        data=plan.to_dict(),
    )


def approval_requested_event(plan: Plan) -> StreamEvent:
    """Create an approval requested event."""
    return StreamEvent(
        event_type=EventType.APPROVAL_REQUESTED,
        data=plan.to_dict(),
    )


def approval_granted_event() -> StreamEvent:
    """Create an approval granted event."""
    return StreamEvent(event_type=EventType.APPROVAL_GRANTED)


def approval_denied_event(reason: str = "") -> StreamEvent:
    """Create an approval denied event."""
    return StreamEvent(
        event_type=EventType.APPROVAL_DENIED,
        data={"reason": reason},
    )


def tool_started_event(tool_name: str, tool_input: dict[str, Any]) -> StreamEvent:
    """Create a tool started event."""
    return StreamEvent(
        event_type=EventType.TOOL_STARTED,
        data={"tool_name": tool_name, "tool_input": tool_input},
    )


def tool_output_event(tool_name: str, output: str) -> StreamEvent:
    """Create a tool output event."""
    return StreamEvent(
        event_type=EventType.TOOL_OUTPUT,
        data={"tool_name": tool_name, "output": output},
    )


def tool_completed_event(tool_name: str, result: Any) -> StreamEvent:
    """Create a tool completed event."""
    return StreamEvent(
        event_type=EventType.TOOL_COMPLETED,
        data={"tool_name": tool_name, "result": str(result)},
    )


def llm_token_event(token: str) -> StreamEvent:
    """Create an LLM token event."""
    return StreamEvent(
        event_type=EventType.LLM_TOKEN,
        data={"token": token},
    )


def llm_response_event(response: str) -> StreamEvent:
    """Create an LLM response event."""
    return StreamEvent(
        event_type=EventType.LLM_RESPONSE,
        data={"response": response},
    )


def error_event(error: str, details: dict[str, Any] | None = None) -> StreamEvent:
    """Create an error event."""
    return StreamEvent(
        event_type=EventType.ERROR,
        data={"error": error, "details": details or {}},
    )


def message_event(content: str, role: str = "assistant") -> StreamEvent:
    """Create a message event."""
    return StreamEvent(
        event_type=EventType.MESSAGE,
        data={"content": content, "role": role},
    )


def document_update_event(
    block_type: str,
    content: dict[str, Any],
    position: int | None = None,
) -> StreamEvent:
    """Create a document update event."""
    return StreamEvent(
        event_type=EventType.DOCUMENT_UPDATE,
        data={
            "block_type": block_type,
            "content": content,
            "position": position,
        },
    )


def step_started_event(step_number: int, description: str) -> StreamEvent:
    """Create a step started event."""
    return StreamEvent(
        event_type=EventType.STEP_STARTED,
        data={"step_number": step_number, "description": description},
    )


def step_completed_event(step_number: int, result: str) -> StreamEvent:
    """Create a step completed event."""
    return StreamEvent(
        event_type=EventType.STEP_COMPLETED,
        data={"step_number": step_number, "result": result},
    )


def execution_started_event(plan: Plan) -> StreamEvent:
    """Create an execution started event."""
    return StreamEvent(
        event_type=EventType.EXECUTION_STARTED,
        data=plan.to_dict(),
    )


def execution_completed_event(summary: str) -> StreamEvent:
    """Create an execution completed event."""
    return StreamEvent(
        event_type=EventType.EXECUTION_COMPLETED,
        data={"summary": summary},
    )
