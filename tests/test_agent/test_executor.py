"""Tests for executor agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agent.executor import ExecutorAgent
from src.agent.events import Plan, PlanStep, EventType


class TestExecutorAgent:
    """Tests for ExecutorAgent class."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        llm = MagicMock()
        llm.ainvoke = AsyncMock()
        llm.astream = MagicMock()
        return llm

    @pytest.fixture
    def mock_tool(self):
        """Create a mock tool."""
        tool = MagicMock()
        tool.name = "test_tool"
        tool.description = "A test tool"
        tool.ainvoke = AsyncMock(return_value="Tool result")
        return tool

    @pytest.fixture
    def executor(self, mock_llm, mock_tool):
        """Create an executor agent instance."""
        return ExecutorAgent(
            llm=mock_llm,
            tools=[mock_tool],
        )

    def test_init_builds_tools_by_name(self, executor, mock_tool):
        """Executor builds tools_by_name dictionary correctly."""
        assert "test_tool" in executor.tools_by_name
        assert executor.tools_by_name["test_tool"] is mock_tool

    def test_get_available_tools(self, executor):
        """Getting available tools returns tool names."""
        tools = executor.get_available_tools()

        assert tools == ["test_tool"]

    def test_get_tool_descriptions(self, executor):
        """Getting tool descriptions returns name-description mapping."""
        descriptions = executor.get_tool_descriptions()

        assert descriptions == {"test_tool": "A test tool"}

    @pytest.mark.asyncio
    async def test_execute_step_with_tool(self, executor, mock_llm, mock_tool):
        """Executing a step with a tool invokes the tool."""
        mock_llm.ainvoke.return_value = MagicMock(content='{"input": "test"}')

        step = PlanStep(
            step_number=1,
            description="Run the test tool",
            tool_name="test_tool",
            requires_approval=False,
        )

        events = []
        async for event in executor.execute_step(step):
            events.append(event)

        # Should have step_started, tool_started, tool_completed, step_completed
        event_types = [e.event_type for e in events]
        assert EventType.STEP_STARTED in event_types
        assert EventType.TOOL_STARTED in event_types
        assert EventType.TOOL_COMPLETED in event_types
        assert EventType.STEP_COMPLETED in event_types

        # Tool should have been called
        mock_tool.ainvoke.assert_called()

    @pytest.mark.asyncio
    async def test_execute_step_without_tool(self, executor, mock_llm):
        """Executing a step without a tool uses LLM reasoning."""
        # Mock streaming response
        async def mock_stream(*args, **kwargs):
            yield MagicMock(content="Reasoning result")

        mock_llm.astream = mock_stream

        step = PlanStep(
            step_number=1,
            description="Think about the problem",
            tool_name=None,
            requires_approval=False,
        )

        events = []
        async for event in executor.execute_step(step):
            events.append(event)

        # Should have step_started, message, step_completed
        event_types = [e.event_type for e in events]
        assert EventType.STEP_STARTED in event_types
        assert EventType.MESSAGE in event_types
        assert EventType.STEP_COMPLETED in event_types

    @pytest.mark.asyncio
    async def test_execute_step_marks_status(self, executor, mock_llm, mock_tool):
        """Executing a step updates the step's status."""
        mock_llm.ainvoke.return_value = MagicMock(content='{"input": "test"}')

        step = PlanStep(
            step_number=1,
            description="Test",
            tool_name="test_tool",
        )

        assert step.status == "pending"

        async for _ in executor.execute_step(step):
            pass

        assert step.status == "completed"

    @pytest.mark.asyncio
    async def test_execute_step_handles_error(self, executor, mock_llm, mock_tool):
        """Executing a step handles tool errors gracefully."""
        mock_llm.ainvoke.return_value = MagicMock(content='{"input": "test"}')
        mock_tool.ainvoke.side_effect = Exception("Tool failed")

        step = PlanStep(
            step_number=1,
            description="Test",
            tool_name="test_tool",
        )

        events = []
        async for event in executor.execute_step(step):
            events.append(event)

        # Should have error event
        event_types = [e.event_type for e in events]
        assert EventType.ERROR in event_types
        assert step.status == "failed"

    @pytest.mark.asyncio
    async def test_execute_plan(self, executor, mock_llm, mock_tool):
        """Executing a complete plan processes all steps."""
        mock_llm.ainvoke.return_value = MagicMock(content='{"input": "test"}')

        plan = Plan(
            goal="Test goal",
            steps=[
                PlanStep(step_number=1, description="Step 1", tool_name="test_tool"),
                PlanStep(step_number=2, description="Step 2", tool_name="test_tool"),
            ],
            reasoning="Test",
        )

        events = []
        async for event in executor.execute_plan(plan):
            events.append(event)

        # Should have execution_started and execution_completed
        event_types = [e.event_type for e in events]
        assert EventType.EXECUTION_STARTED in event_types
        assert EventType.EXECUTION_COMPLETED in event_types

        # Both steps should be completed
        assert plan.steps[0].status == "completed"
        assert plan.steps[1].status == "completed"

    @pytest.mark.asyncio
    async def test_execute_plan_with_approval_callback(self, executor, mock_llm, mock_tool):
        """Executing a plan with approval callback skips denied steps."""
        mock_llm.ainvoke.return_value = MagicMock(content='{"input": "test"}')

        plan = Plan(
            goal="Test goal",
            steps=[
                PlanStep(
                    step_number=1,
                    description="Step 1",
                    tool_name="test_tool",
                    requires_approval=True,
                ),
            ],
            reasoning="Test",
        )

        async def deny_approval(step):
            return False

        events = []
        async for event in executor.execute_plan(plan, approval_callback=deny_approval):
            events.append(event)

        # Step should be skipped
        assert plan.steps[0].status == "skipped"

    @pytest.mark.asyncio
    async def test_build_tool_input(self, executor, mock_llm, mock_tool):
        """Building tool input uses LLM to generate appropriate input."""
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"file_path": "data.csv", "mode": "read"}'
        )

        step = PlanStep(
            step_number=1,
            description="Read the data file",
            tool_name="test_tool",
        )

        tool_input = await executor._build_tool_input(step, context=None)

        assert tool_input == {"file_path": "data.csv", "mode": "read"}

    @pytest.mark.asyncio
    async def test_build_tool_input_fallback(self, executor, mock_llm):
        """Building tool input falls back to simple input on parse error."""
        mock_llm.ainvoke.return_value = MagicMock(content="Not valid JSON")

        step = PlanStep(
            step_number=1,
            description="Do something",
            tool_name="test_tool",
        )

        tool_input = await executor._build_tool_input(step, context=None)

        assert "input" in tool_input
        assert tool_input["input"] == "Do something"
