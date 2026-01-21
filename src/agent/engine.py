"""Main agent engine orchestrator."""

import asyncio
from collections.abc import AsyncGenerator, Callable
from enum import Enum
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.agent.events import (
    Plan,
    StreamEvent,
    approval_denied_event,
    approval_granted_event,
    approval_requested_event,
    error_event,
    message_event,
)
from src.agent.executor import ExecutorAgent
from src.agent.memory import ConversationMemory, MemoryManager
from src.agent.planner import PlannerAgent
from src.agent.streaming import EventAggregator
from src.database.connection import Database


class AgentState(str, Enum):
    """State of the agent engine."""

    IDLE = "idle"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    ERROR = "error"


class AgentEngine:
    """Main orchestrator for the plan-then-execute agent architecture.

    Coordinates between the planner, executor, memory, and streaming components
    to process user requests in a structured manner.
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        db: Database,
        project_path: Path | None = None,
    ):
        """Initialize the agent engine.

        Args:
            llm: Language model for planning and execution
            tools: List of available tools
            db: Database instance for persistence
            project_path: Path to the project directory
        """
        self.llm = llm
        self.tools = tools
        self.db = db
        self.project_path = project_path

        # Initialize components
        self.planner = PlannerAgent(
            llm=llm,
            available_tools=[tool.name for tool in tools],
        )
        self.executor = ExecutorAgent(
            llm=llm,
            tools=tools,
            project_path=project_path,
        )
        self.memory_manager = MemoryManager(db)
        self.event_aggregator = EventAggregator()

        # State
        self.state = AgentState.IDLE
        self.current_plan: Plan | None = None
        self._approval_future: asyncio.Future | None = None

    def get_memory(self, conversation_id: str) -> ConversationMemory:
        """Get conversation memory for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            ConversationMemory instance
        """
        return self.memory_manager.get_memory(conversation_id)

    async def run(
        self,
        user_input: str,
        conversation_id: str,
        approval_callback: Callable[[Plan], Any] | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Run the agent for a user input.

        This implements the plan-then-execute pattern:
        1. Create a plan from user input
        2. Request user approval if needed
        3. Execute the plan step by step
        4. Stream events throughout

        Args:
            user_input: User's request
            conversation_id: ID of the conversation
            approval_callback: Optional callback for approval (sync returns, or sets future)

        Yields:
            StreamEvents during processing
        """
        memory = self.get_memory(conversation_id)
        planning_handler = self.event_aggregator.create_handler()

        try:
            # Add user message to memory
            memory.add_user_message(user_input)

            # Phase 1: Planning
            self.state = AgentState.PLANNING
            yield message_event("Creating execution plan...", role="system")

            plan: Plan | None = None
            async for event_or_plan in self.planner.create_plan(
                user_input=user_input,
                memory=memory,
                streaming_handler=planning_handler,
            ):
                if isinstance(event_or_plan, Plan):
                    plan = event_or_plan
                else:
                    yield event_or_plan

            if not plan:
                yield error_event("Failed to create plan")
                self.state = AgentState.ERROR
                return

            self.current_plan = plan

            # Validate plan
            is_valid, issues = self.planner.validate_plan(plan)
            if not is_valid:
                yield message_event(
                    f"Plan validation issues: {', '.join(issues)}", role="system"
                )

            # Phase 2: Approval (if required)
            if plan.requires_approval:
                self.state = AgentState.AWAITING_APPROVAL
                yield approval_requested_event(plan)

                # Wait for approval
                if approval_callback:
                    approved = await self._wait_for_approval(approval_callback, plan)
                else:
                    # Auto-approve if no callback (for testing)
                    approved = True

                if approved:
                    yield approval_granted_event()
                else:
                    yield approval_denied_event("User denied plan execution")
                    memory.add_ai_message(
                        "Plan execution was cancelled by user. Let me know if you'd like "
                        "to modify the approach or try something different."
                    )
                    self.state = AgentState.COMPLETED
                    return

            # Phase 3: Execution
            self.state = AgentState.EXECUTING
            yield message_event("Executing plan...", role="system")

            # Create per-step approval callback if needed
            step_approval_callback = None
            if approval_callback:

                async def _step_approval(step):
                    if step.requires_approval:
                        # For now, assume plan-level approval covers steps
                        return True
                    return True

                step_approval_callback = _step_approval

            execution_handler = self.event_aggregator.create_handler()
            async for event in self.executor.execute_plan(
                plan=plan,
                memory=memory,
                streaming_handler=execution_handler,
                approval_callback=step_approval_callback,
            ):
                yield event

            # Generate summary response
            summary = self._generate_summary(plan)
            memory.add_ai_message(summary)
            yield message_event(summary)

            self.state = AgentState.COMPLETED

        except Exception as e:
            self.state = AgentState.ERROR
            yield error_event(f"Agent error: {str(e)}")
            memory.add_ai_message(f"I encountered an error: {str(e)}")

    async def _wait_for_approval(
        self,
        callback: Callable[[Plan], Any],
        plan: Plan,
    ) -> bool:
        """Wait for plan approval.

        Args:
            callback: Approval callback function
            plan: Plan to approve

        Returns:
            True if approved, False otherwise
        """
        result = callback(plan)

        # Handle both sync and async callbacks
        if asyncio.iscoroutine(result):
            return await result
        elif asyncio.isfuture(result):
            return await result

        return bool(result)

    def grant_approval(self) -> None:
        """Grant approval for the current plan (called from UI)."""
        if self._approval_future and not self._approval_future.done():
            self._approval_future.set_result(True)

    def deny_approval(self) -> None:
        """Deny approval for the current plan (called from UI)."""
        if self._approval_future and not self._approval_future.done():
            self._approval_future.set_result(False)

    def _generate_summary(self, plan: Plan) -> str:
        """Generate a summary of plan execution.

        Args:
            plan: Executed plan

        Returns:
            Summary string
        """
        completed = sum(1 for s in plan.steps if s.status == "completed")
        skipped = sum(1 for s in plan.steps if s.status == "skipped")
        failed = sum(1 for s in plan.steps if s.status == "failed")
        total = len(plan.steps)

        summary_parts = [f"Completed {completed}/{total} steps for: {plan.goal}"]

        if skipped:
            summary_parts.append(f"{skipped} steps were skipped")
        if failed:
            summary_parts.append(f"{failed} steps failed")

        return ". ".join(summary_parts) + "."

    async def chat(
        self,
        user_input: str,
        conversation_id: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Simple chat without planning (for quick responses).

        Args:
            user_input: User's message
            conversation_id: Conversation ID

        Yields:
            StreamEvents for the response
        """
        memory = self.get_memory(conversation_id)
        streaming_handler = self.event_aggregator.create_handler()

        memory.add_user_message(user_input)

        try:
            # Get messages for LLM
            messages = memory.get_messages_for_llm()

            # Stream response
            response_text = ""
            async for chunk in self.llm.astream(
                messages,
                config={"callbacks": [streaming_handler]},
            ):
                if hasattr(chunk, "content"):
                    response_text += chunk.content

            memory.add_ai_message(response_text)
            yield message_event(response_text)

        except Exception as e:
            yield error_event(f"Chat error: {str(e)}")

    def reset(self) -> None:
        """Reset the agent state."""
        self.state = AgentState.IDLE
        self.current_plan = None
        self._approval_future = None
        self.event_aggregator.clear()


def create_agent_engine(
    llm: BaseChatModel,
    tools: list[BaseTool],
    db: Database,
    project_path: Path | None = None,
) -> AgentEngine:
    """Factory function to create an agent engine.

    Args:
        llm: Language model
        tools: Available tools
        db: Database instance
        project_path: Project directory path

    Returns:
        Configured AgentEngine
    """
    return AgentEngine(
        llm=llm,
        tools=tools,
        db=db,
        project_path=project_path,
    )
