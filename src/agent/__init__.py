"""Agent module for plan-then-execute architecture.

This module provides the core agent components:
- AgentEngine: Main orchestrator
- PlannerAgent: Creates execution plans
- ExecutorAgent: Executes plan steps
- ConversationMemory: Manages conversation history
- StreamingHandler: Handles streaming events
"""

from src.agent.engine import AgentEngine, AgentState, create_agent_engine
from src.agent.events import (
    EventType,
    Plan,
    PlanStep,
    StreamEvent,
)
from src.agent.executor import ExecutorAgent
from src.agent.memory import ConversationMemory, MemoryManager
from src.agent.planner import PlannerAgent
from src.agent.streaming import EventAggregator, StreamingHandler

__all__ = [
    # Engine
    "AgentEngine",
    "AgentState",
    "create_agent_engine",
    # Planning
    "PlannerAgent",
    "Plan",
    "PlanStep",
    # Execution
    "ExecutorAgent",
    # Memory
    "ConversationMemory",
    "MemoryManager",
    # Streaming
    "StreamingHandler",
    "EventAggregator",
    "StreamEvent",
    "EventType",
]
