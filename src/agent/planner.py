"""Planner agent for creating execution plans."""

import json
import re
from collections.abc import AsyncGenerator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.agent.events import (
    Plan,
    PlanStep,
    StreamEvent,
    plan_completed_event,
    plan_started_event,
    plan_step_event,
)
from src.agent.memory import ConversationMemory
from src.agent.streaming import StreamingHandler

PLANNER_SYSTEM_PROMPT = """You are a planning agent for a data science and machine learning assistant.
Your role is to analyze user requests and create structured execution plans.

You have access to the following tools:
- file_operations: Read, write, list, delete, and move files within the project
- bash_executor: Execute bash commands for system operations
- python_executor: Execute Python code for data analysis, ML, and visualization
- web_search: Search the web for documentation, datasets, and information
- todo_list: Track and manage task progress

For each user request, create a detailed plan with the following structure:
1. Understand the user's goal
2. Break it down into concrete, actionable steps
3. Identify which tools are needed for each step
4. Mark steps that require user approval (especially code execution)

IMPORTANT GUIDELINES:
- Always start with understanding the data/context when relevant
- For ML tasks, include data exploration before model training
- For code execution, always require user approval
- Be specific about what each step will accomplish
- Consider error handling and edge cases

Respond with a JSON object in this exact format:
{
    "goal": "Clear description of what the user wants to achieve",
    "reasoning": "Your analysis of how to approach this task",
    "steps": [
        {
            "step_number": 1,
            "description": "What this step accomplishes",
            "tool_name": "tool to use (or null if just reasoning)",
            "requires_approval": true/false
        }
    ],
    "requires_approval": true
}

Always set requires_approval to true for the overall plan if any code will be executed."""


class PlannerAgent:
    """Agent responsible for creating execution plans from user requests."""

    def __init__(
        self,
        llm: BaseChatModel,
        available_tools: list[str] | None = None,
    ):
        """Initialize the planner agent.

        Args:
            llm: Language model for planning
            available_tools: List of available tool names
        """
        self.llm = llm
        self.available_tools = available_tools or [
            "file_operations",
            "bash_executor",
            "python_executor",
            "web_search",
            "todo_list",
        ]

    def _build_system_prompt(self) -> str:
        """Build the system prompt with available tools.

        Returns:
            Complete system prompt
        """
        return PLANNER_SYSTEM_PROMPT

    def _build_planning_prompt(
        self,
        user_input: str,
        context: str | None = None,
    ) -> str:
        """Build the planning prompt.

        Args:
            user_input: User's request
            context: Additional context from conversation

        Returns:
            Complete planning prompt
        """
        prompt = f"User Request: {user_input}"

        if context:
            prompt = f"Previous Context:\n{context}\n\n{prompt}"

        prompt += "\n\nCreate a detailed execution plan for this request."
        return prompt

    def _parse_plan_response(self, response: str) -> Plan:
        """Parse LLM response into a Plan object.

        Args:
            response: LLM response text

        Returns:
            Parsed Plan object
        """
        # Extract JSON from response
        try:
            # Try to parse as JSON directly
            data = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
            if json_match:
                data = json.loads(json_match.group(1))
            else:
                # Try to find JSON object in response
                json_match = re.search(r"\{[\s\S]*\}", response)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    # Fallback to simple plan
                    data = {
                        "goal": "Process user request",
                        "reasoning": response,
                        "steps": [
                            {
                                "step_number": 1,
                                "description": "Analyze and respond to the request",
                                "tool_name": None,
                                "requires_approval": False,
                            }
                        ],
                        "requires_approval": False,
                    }

        # Convert to Plan object
        steps = [
            PlanStep(
                step_number=s.get("step_number", i + 1),
                description=s.get("description", ""),
                tool_name=s.get("tool_name"),
                requires_approval=s.get("requires_approval", False),
            )
            for i, s in enumerate(data.get("steps", []))
        ]

        return Plan(
            goal=data.get("goal", ""),
            steps=steps,
            reasoning=data.get("reasoning", ""),
            requires_approval=data.get("requires_approval", True),
        )

    async def create_plan(
        self,
        user_input: str,
        memory: ConversationMemory | None = None,
        streaming_handler: StreamingHandler | None = None,
    ) -> AsyncGenerator[StreamEvent | Plan, None]:
        """Create an execution plan for the user's request.

        Args:
            user_input: User's request
            memory: Conversation memory for context
            streaming_handler: Handler for streaming events

        Yields:
            StreamEvents during planning, then the final Plan
        """
        # Emit plan started event
        yield plan_started_event(user_input)

        # Build context from memory
        context = None
        if memory:
            recent = memory.get_recent_messages(5)
            if recent:
                context_parts = []
                for msg in recent:
                    role = "User" if hasattr(msg, "type") and msg.type == "human" else "Assistant"
                    context_parts.append(f"{role}: {msg.content[:200]}...")
                context = "\n".join(context_parts)

        # Build messages
        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=self._build_planning_prompt(user_input, context)),
        ]

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

        # Parse the plan
        plan = self._parse_plan_response(response)

        # Emit step events
        for step in plan.steps:
            yield plan_step_event(step)

        # Emit plan completed event
        yield plan_completed_event(plan)

        # Yield the final plan
        yield plan

    async def refine_plan(
        self,
        original_plan: Plan,
        feedback: str,
        memory: ConversationMemory | None = None,
    ) -> Plan:
        """Refine a plan based on user feedback.

        Args:
            original_plan: The original plan
            feedback: User's feedback
            memory: Conversation memory

        Returns:
            Refined Plan
        """
        refinement_prompt = f"""The user provided feedback on the following plan:

Original Plan:
Goal: {original_plan.goal}
Steps:
{chr(10).join(f"  {s.step_number}. {s.description}" for s in original_plan.steps)}

User Feedback: {feedback}

Please create a refined plan that addresses the user's feedback.
Respond with a JSON object in the same format as before."""

        messages = [
            SystemMessage(content=self._build_system_prompt()),
            HumanMessage(content=refinement_prompt),
        ]

        result = await self.llm.ainvoke(messages)
        return self._parse_plan_response(result.content)

    def validate_plan(self, plan: Plan) -> tuple[bool, list[str]]:
        """Validate a plan for completeness and safety.

        Args:
            plan: Plan to validate

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        if not plan.goal:
            issues.append("Plan has no goal")

        if not plan.steps:
            issues.append("Plan has no steps")

        for step in plan.steps:
            if not step.description:
                issues.append(f"Step {step.step_number} has no description")

            if step.tool_name and step.tool_name not in self.available_tools:
                issues.append(
                    f"Step {step.step_number} uses unknown tool: {step.tool_name}"
                )

            # Code execution should require approval
            if step.tool_name in ["python_executor", "bash_executor"]:
                if not step.requires_approval:
                    issues.append(
                        f"Step {step.step_number} executes code but doesn't require approval"
                    )

        return len(issues) == 0, issues
