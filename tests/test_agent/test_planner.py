"""Tests for planner agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agent.planner import PlannerAgent
from src.agent.events import Plan, PlanStep, EventType


class TestPlannerAgent:
    """Tests for PlannerAgent class."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock()
        return llm

    @pytest.fixture
    def planner(self, mock_llm):
        """Create a planner agent instance."""
        return PlannerAgent(
            llm=mock_llm,
            available_tools=["file_operations", "python_executor"],
        )

    def test_init_default_tools(self, mock_llm):
        """Planner initializes with default tools when none provided."""
        planner = PlannerAgent(llm=mock_llm)

        assert "file_operations" in planner.available_tools
        assert "bash_executor" in planner.available_tools
        assert "python_executor" in planner.available_tools
        assert "web_search" in planner.available_tools
        assert "todo_list" in planner.available_tools

    def test_init_custom_tools(self, planner):
        """Planner uses provided custom tools."""
        assert planner.available_tools == ["file_operations", "python_executor"]

    def test_build_planning_prompt_simple(self, planner):
        """Building planning prompt with no context works."""
        prompt = planner._build_planning_prompt("Analyze the data")

        assert "User Request: Analyze the data" in prompt
        assert "Create a detailed execution plan" in prompt

    def test_build_planning_prompt_with_context(self, planner):
        """Building planning prompt with context includes it."""
        prompt = planner._build_planning_prompt(
            "Continue analysis",
            context="Previous: Loaded data.csv",
        )

        assert "Previous Context:" in prompt
        assert "Previous: Loaded data.csv" in prompt
        assert "Continue analysis" in prompt

    def test_parse_plan_response_valid_json(self, planner):
        """Parsing valid JSON plan response works."""
        response = """{
            "goal": "Analyze customer data",
            "reasoning": "Will use pandas for analysis",
            "steps": [
                {
                    "step_number": 1,
                    "description": "Load the data",
                    "tool_name": "python_executor",
                    "requires_approval": true
                }
            ],
            "requires_approval": true
        }"""

        plan = planner._parse_plan_response(response)

        assert plan.goal == "Analyze customer data"
        assert plan.reasoning == "Will use pandas for analysis"
        assert len(plan.steps) == 1
        assert plan.steps[0].tool_name == "python_executor"
        assert plan.requires_approval is True

    def test_parse_plan_response_markdown_json(self, planner):
        """Parsing JSON in markdown code block works."""
        response = """Here's the plan:

```json
{
    "goal": "Test goal",
    "reasoning": "Test reasoning",
    "steps": [{"step_number": 1, "description": "Step 1"}],
    "requires_approval": false
}
```

Let me know if you need changes."""

        plan = planner._parse_plan_response(response)

        assert plan.goal == "Test goal"
        assert len(plan.steps) == 1

    def test_parse_plan_response_fallback(self, planner):
        """Parsing invalid response creates fallback plan."""
        response = "I cannot parse this as JSON"

        plan = planner._parse_plan_response(response)

        assert plan.goal == "Process user request"
        assert len(plan.steps) == 1
        assert plan.requires_approval is False

    def test_validate_plan_valid(self, planner):
        """Validating a valid plan passes."""
        plan = Plan(
            goal="Test goal",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Load data",
                    tool_name="file_operations",
                    requires_approval=False,
                ),
                PlanStep(
                    step_number=2,
                    description="Run analysis",
                    tool_name="python_executor",
                    requires_approval=True,
                ),
            ],
            reasoning="Test reasoning",
            requires_approval=True,
        )

        is_valid, issues = planner.validate_plan(plan)

        assert is_valid is True
        assert len(issues) == 0

    def test_validate_plan_no_goal(self, planner):
        """Validating plan without goal fails."""
        plan = Plan(
            goal="",
            steps=[PlanStep(step_number=1, description="Test")],
            reasoning="",
        )

        is_valid, issues = planner.validate_plan(plan)

        assert is_valid is False
        assert "Plan has no goal" in issues

    def test_validate_plan_no_steps(self, planner):
        """Validating plan without steps fails."""
        plan = Plan(
            goal="Test goal",
            steps=[],
            reasoning="",
        )

        is_valid, issues = planner.validate_plan(plan)

        assert is_valid is False
        assert "Plan has no steps" in issues

    def test_validate_plan_unknown_tool(self, planner):
        """Validating plan with unknown tool reports issue."""
        plan = Plan(
            goal="Test",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Test",
                    tool_name="unknown_tool",
                )
            ],
            reasoning="",
        )

        is_valid, issues = planner.validate_plan(plan)

        assert is_valid is False
        assert any("unknown tool" in issue for issue in issues)

    def test_validate_plan_code_without_approval(self, planner):
        """Validating plan with code execution without approval reports issue."""
        planner.available_tools.append("python_executor")
        plan = Plan(
            goal="Test",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Run code",
                    tool_name="python_executor",
                    requires_approval=False,
                )
            ],
            reasoning="",
        )

        is_valid, issues = planner.validate_plan(plan)

        assert is_valid is False
        assert any("approval" in issue.lower() for issue in issues)

    @pytest.mark.asyncio
    async def test_create_plan_yields_events(self, planner, mock_llm):
        """Creating a plan yields appropriate events."""
        mock_llm.ainvoke.return_value = MagicMock(
            content="""{
                "goal": "Test",
                "reasoning": "Test reasoning",
                "steps": [{"step_number": 1, "description": "Step 1"}],
                "requires_approval": true
            }"""
        )

        events = []
        final_plan = None
        async for event in planner.create_plan("Test request"):
            if isinstance(event, Plan):
                final_plan = event
            else:
                events.append(event)

        # Should have plan_started, plan_step, and plan_completed events
        event_types = [e.event_type for e in events]
        assert EventType.PLAN_STARTED in event_types
        assert EventType.PLAN_STEP in event_types
        assert EventType.PLAN_COMPLETED in event_types
        assert final_plan is not None
        assert final_plan.goal == "Test"
