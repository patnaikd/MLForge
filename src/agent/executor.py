"""Executor agent for executing plan steps."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Iterable

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.tools import BaseTool

from src.agent.events import (
    Plan,
    PlanStep,
    StreamEvent,
    error_event,
    execution_completed_event,
    execution_started_event,
    message_event,
    step_completed_event,
    step_started_event,
)
from src.agent.memory import ConversationMemory
from src.agent.streaming import StreamingHandler

EXECUTOR_SYSTEM_PROMPT = """You are an execution agent for a data science and machine learning assistant.
Your role is to execute plan steps using the available tools.

When executing a step:
1. Understand what the step requires
2. Use the appropriate tool with correct parameters
3. Handle any errors gracefully
4. Report the results clearly

Available tools will be provided to you. Use them appropriately to accomplish each step.

IMPORTANT:
- Always validate inputs before execution
- Handle errors gracefully and report them
- Provide clear status updates
- For code execution, ensure code is safe and correct
- For file operations, respect project boundaries

When you complete a step, summarize what was accomplished."""


class ExecutorAgent:
    """Agent responsible for executing plan steps."""

    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[BaseTool],
        project_path: Path | None = None,
    ):
        """Initialize the executor agent.

        Args:
            llm: Language model for execution decisions
            tools: List of available tools
            project_path: Path to the project directory
        """
        self.llm = llm
        self.tools = tools
        self.tools_by_name = {tool.name: tool for tool in tools}
        self.project_path = project_path
        self._agent_cache: dict[tuple[str, ...], Any] = {}

    def _build_execution_prompt(
        self,
        step: PlanStep,
        context: str | None = None,
    ) -> str:
        """Build the execution prompt for a step.

        Args:
            step: Plan step to execute
            context: Additional context

        Returns:
            Execution prompt
        """
        prompt = f"""Execute the following step:

Step {step.step_number}: {step.description}
Tool to use: {step.tool_name or "reasoning only"}

"""
        if context:
            prompt += f"Context from previous steps:\n{context}\n\n"

        prompt += "Execute this step and report the results."
        return prompt

    async def execute_step(
        self,
        step: PlanStep,
        memory: ConversationMemory | None = None,
        streaming_handler: StreamingHandler | None = None,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Execute a single plan step.

        Args:
            step: Step to execute
            memory: Conversation memory
            streaming_handler: Handler for streaming events
            context: Context from previous steps

        Yields:
            StreamEvents during execution
        """
        # Emit step started
        yield step_started_event(step.step_number, step.description)

        try:
            async for event in self._execute_with_agent(
                step, memory, streaming_handler, context
            ):
                yield event

            # Mark step as completed
            step.status = "completed"
            yield step_completed_event(step.step_number, "Step completed successfully")

        except Exception as e:
            step.status = "failed"
            yield error_event(f"Step {step.step_number} failed: {str(e)}")
            yield step_completed_event(step.step_number, f"Failed: {str(e)}")

    def _select_tools(self, step: PlanStep) -> list[BaseTool]:
        """Select tools for the given step."""
        if step.tool_name and step.tool_name in self.tools_by_name:
            return [self.tools_by_name[step.tool_name]]
        return self.tools

    def _get_agent(self, tools: Iterable[BaseTool]) -> Any:
        """Get or create a cached agent for a tool subset."""
        key = tuple(tool.name for tool in tools)
        if key not in self._agent_cache:
            self._agent_cache[key] = create_agent(
                self.llm,
                tools=list(tools),
                system_prompt=EXECUTOR_SYSTEM_PROMPT,
            )
        return self._agent_cache[key]

    async def _drain_streaming_events(
        self,
        streaming_handler: StreamingHandler,
        result_task: "asyncio.Task[Any]",
        poll_interval: float = 0.1,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Yield streaming events while the agent is running."""
        while not result_task.done():
            event = await streaming_handler.get_event(timeout=poll_interval)
            if event:
                yield event

        while True:
            event = await streaming_handler.get_event(timeout=poll_interval)
            if not event:
                break
            yield event

    def _build_messages(
        self,
        step: PlanStep,
        memory: ConversationMemory | None,
        context: dict[str, Any] | None,
    ) -> list[BaseMessage]:
        """Build the message list for the agent call."""
        messages: list[BaseMessage] = []
        if memory:
            messages.extend(memory.get_messages_for_llm())
        prompt = self._build_execution_prompt(step, context=str(context) if context else None)
        messages.append(HumanMessage(content=prompt))
        return messages

    def _extract_response_text(self, result: Any) -> str:
        """Extract the final response text from an agent result."""
        messages = None
        if isinstance(result, dict):
            messages = result.get("messages")
        elif hasattr(result, "messages"):
            messages = getattr(result, "messages")
        elif isinstance(result, list):
            messages = result

        if messages:
            last = messages[-1]
            if hasattr(last, "content"):
                return str(last.content)
            return str(last)

        return str(result)

    async def _execute_with_agent(
        self,
        step: PlanStep,
        memory: ConversationMemory | None = None,
        streaming_handler: StreamingHandler | None = None,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Execute a step using LangChain's create_agent loop."""
        tools = self._select_tools(step)
        agent = self._get_agent(tools)
        messages = self._build_messages(step, memory, context)
        payload = {"messages": messages}

        if streaming_handler:
            result_task = asyncio.create_task(
                agent.ainvoke(payload, config={"callbacks": [streaming_handler]})
            )
            async for event in self._drain_streaming_events(
                streaming_handler, result_task
            ):
                yield event
            result = await result_task
        else:
            result = await agent.ainvoke(payload)

        response = self._extract_response_text(result)
        if response:
            yield message_event(response)

    async def execute_plan(
        self,
        plan: Plan,
        memory: ConversationMemory | None = None,
        streaming_handler: StreamingHandler | None = None,
        approval_callback: Any | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Execute a complete plan.

        Args:
            plan: Plan to execute
            memory: Conversation memory
            streaming_handler: Handler for streaming events
            approval_callback: Callback for approval requests

        Yields:
            StreamEvents during execution
        """
        yield execution_started_event(plan)

        context: dict[str, Any] = {"results": []}

        for step in plan.steps:
            # Check if step requires approval
            if step.requires_approval and approval_callback:
                approved = await approval_callback(step)
                if not approved:
                    step.status = "skipped"
                    yield message_event(
                        f"Step {step.step_number} skipped: User denied approval"
                    )
                    continue

            # Execute the step
            async for event in self.execute_step(
                step, memory, streaming_handler, context
            ):
                yield event

                # Update context with results
                if event.event_type.value == "tool_completed":
                    context["results"].append({
                        "step": step.step_number,
                        "tool": step.tool_name,
                        "result": event.data.get("result"),
                    })

        # Generate summary
        completed_steps = [s for s in plan.steps if s.status == "completed"]
        skipped_steps = [s for s in plan.steps if s.status == "skipped"]
        failed_steps = [s for s in plan.steps if s.status == "failed"]

        summary = f"Execution completed: {len(completed_steps)} steps completed"
        if skipped_steps:
            summary += f", {len(skipped_steps)} skipped"
        if failed_steps:
            summary += f", {len(failed_steps)} failed"

        yield execution_completed_event(summary)

    def get_available_tools(self) -> list[str]:
        """Get list of available tool names.

        Returns:
            List of tool names
        """
        return list(self.tools_by_name.keys())

    def get_tool_descriptions(self) -> dict[str, str]:
        """Get descriptions of available tools.

        Returns:
            Dictionary mapping tool names to descriptions
        """
        return {tool.name: tool.description for tool in self.tools}
