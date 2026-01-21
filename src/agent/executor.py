"""Executor agent for executing plan steps."""

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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
    tool_completed_event,
    tool_started_event,
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
            if step.tool_name and step.tool_name in self.tools_by_name:
                # Execute with tool
                async for event in self._execute_with_tool(
                    step, streaming_handler, context
                ):
                    yield event
            else:
                # Execute with LLM reasoning only
                async for event in self._execute_with_reasoning(
                    step, memory, streaming_handler
                ):
                    yield event

            # Mark step as completed
            step.status = "completed"
            yield step_completed_event(step.step_number, "Step completed successfully")

        except Exception as e:
            step.status = "failed"
            yield error_event(f"Step {step.step_number} failed: {str(e)}")
            yield step_completed_event(step.step_number, f"Failed: {str(e)}")

    async def _execute_with_tool(
        self,
        step: PlanStep,
        streaming_handler: StreamingHandler | None = None,
        context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Execute a step using a tool.

        Args:
            step: Step to execute
            streaming_handler: Handler for streaming events
            context: Context from previous steps

        Yields:
            StreamEvents during execution
        """
        tool = self.tools_by_name[step.tool_name]

        # Build tool input from step description and context
        tool_input = await self._build_tool_input(step, context)

        yield tool_started_event(tool.name, tool_input)

        try:
            # Execute the tool
            if hasattr(tool, "ainvoke"):
                result = await tool.ainvoke(tool_input)
            else:
                result = tool.invoke(tool_input)

            yield tool_completed_event(tool.name, str(result))
            yield message_event(f"Tool '{tool.name}' completed: {str(result)[:500]}")

        except Exception as e:
            yield error_event(f"Tool execution failed: {str(e)}")
            raise

    async def _execute_with_reasoning(
        self,
        step: PlanStep,
        memory: ConversationMemory | None = None,
        streaming_handler: StreamingHandler | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Execute a step using LLM reasoning only.

        Args:
            step: Step to execute
            memory: Conversation memory
            streaming_handler: Handler for streaming events

        Yields:
            StreamEvents during execution
        """
        messages = [
            SystemMessage(content=EXECUTOR_SYSTEM_PROMPT),
            HumanMessage(content=self._build_execution_prompt(step)),
        ]

        # Add memory context
        if memory:
            recent = memory.get_recent_messages(3)
            for msg in recent:
                if hasattr(msg, "type") and msg.type == "human":
                    messages.append(HumanMessage(content=msg.content))
                else:
                    messages.append(AIMessage(content=msg.content))

        # Get LLM response
        if streaming_handler:
            response_text = ""
            async for chunk in self.llm.astream(
                messages,
                config={"callbacks": [streaming_handler]},
            ):
                if hasattr(chunk, "content"):
                    response_text += chunk.content
            response = response_text
        else:
            result = await self.llm.ainvoke(messages)
            response = result.content

        yield message_event(response)

    async def _build_tool_input(
        self,
        step: PlanStep,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build input for a tool based on step description.

        Args:
            step: Plan step
            context: Context from previous steps

        Returns:
            Tool input dictionary
        """
        # Use LLM to generate appropriate tool input
        tool = self.tools_by_name[step.tool_name]

        prompt = f"""Given the following step description, generate the appropriate input for the tool.

Step: {step.description}
Tool: {tool.name}
Tool Description: {tool.description}

Context: {context or "No previous context"}

Generate a JSON object with the required tool parameters.
Only return the JSON object, nothing else."""

        messages = [
            SystemMessage(content="You are a helpful assistant that generates tool inputs."),
            HumanMessage(content=prompt),
        ]

        result = await self.llm.ainvoke(messages)

        # Parse the response
        import json
        import re

        response = result.content

        try:
            # Try to parse as JSON directly
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                return json.loads(json_match.group(0))

        # Fallback to simple input
        return {"input": step.description}

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
