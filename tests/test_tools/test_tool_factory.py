"""Tests for tool factory functions."""

import pytest
from pathlib import Path

from src.tools import (
    TOOL_REGISTRY,
    create_tools,
    get_tool_by_name,
    get_tools_requiring_approval,
    get_tools_by_category,
    FileOperationsTool,
    BashExecutorTool,
    PythonExecutorTool,
    WebSearchTool,
    WebFetchTool,
    TodoListTool,
    TaskPlannerTool,
)


@pytest.fixture
def project_dir(temp_dir: Path) -> Path:
    """Create a project directory for testing."""
    project = temp_dir / "test_project"
    project.mkdir(parents=True)
    return project


class TestToolRegistry:
    """Tests for the tool registry."""

    def test_registry_has_all_tools(self):
        """Test that registry contains all expected tools."""
        expected_tools = [
            "file_operations",
            "bash_executor",
            "python_executor",
            "web_search",
            "web_fetch",
            "todo_list",
            "task_planner",
        ]
        for tool_name in expected_tools:
            assert tool_name in TOOL_REGISTRY

    def test_registry_structure(self):
        """Test that registry entries have required fields."""
        for name, config in TOOL_REGISTRY.items():
            assert "class" in config
            assert "requires_approval" in config
            assert "description" in config
            assert "category" in config

    def test_execution_tools_require_approval(self):
        """Test that execution tools require approval."""
        assert TOOL_REGISTRY["bash_executor"]["requires_approval"] is True
        assert TOOL_REGISTRY["python_executor"]["requires_approval"] is True

    def test_safe_tools_dont_require_approval(self):
        """Test that safe tools don't require approval."""
        assert TOOL_REGISTRY["file_operations"]["requires_approval"] is False
        assert TOOL_REGISTRY["todo_list"]["requires_approval"] is False
        assert TOOL_REGISTRY["web_search"]["requires_approval"] is False


class TestCreateTools:
    """Tests for create_tools function."""

    def test_create_all_tools(self, project_dir: Path):
        """Test creating all tools."""
        tools = create_tools(project_path=project_dir, project_id="test-id")
        assert len(tools) == len(TOOL_REGISTRY)

    def test_create_with_include(self, project_dir: Path):
        """Test creating specific tools with include."""
        tools = create_tools(
            project_path=project_dir,
            include=["file_operations", "todo_list"],
        )
        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "file_operations" in tool_names
        assert "todo_list" in tool_names

    def test_create_with_exclude(self, project_dir: Path):
        """Test creating tools with exclusions."""
        tools = create_tools(
            project_path=project_dir,
            exclude=["web_search", "web_fetch"],
        )
        tool_names = [t.name for t in tools]
        assert "web_search" not in tool_names
        assert "web_fetch" not in tool_names
        assert len(tools) == len(TOOL_REGISTRY) - 2

    def test_tools_have_project_context(self, project_dir: Path):
        """Test that created tools have project context."""
        tools = create_tools(
            project_path=project_dir,
            project_id="test-project-id",
            conversation_id="test-conversation-id",
        )
        for tool in tools:
            assert tool.project_path == project_dir
            assert tool.project_id == "test-project-id"
            assert tool.conversation_id == "test-conversation-id"

    def test_tools_without_project_path(self):
        """Test creating tools without project path."""
        tools = create_tools()
        assert len(tools) == len(TOOL_REGISTRY)
        for tool in tools:
            assert tool.project_path is None


class TestGetToolByName:
    """Tests for get_tool_by_name function."""

    def test_get_existing_tool(self, project_dir: Path):
        """Test getting an existing tool."""
        tool = get_tool_by_name(
            "file_operations",
            project_path=project_dir,
        )
        assert tool is not None
        assert isinstance(tool, FileOperationsTool)
        assert tool.name == "file_operations"

    def test_get_nonexistent_tool(self):
        """Test getting a nonexistent tool returns None."""
        tool = get_tool_by_name("nonexistent_tool")
        assert tool is None

    def test_get_tool_with_context(self, project_dir: Path):
        """Test getting tool with project context."""
        tool = get_tool_by_name(
            "bash_executor",
            project_path=project_dir,
            project_id="test-id",
            conversation_id="conv-id",
        )
        assert tool.project_path == project_dir
        assert tool.project_id == "test-id"
        assert tool.conversation_id == "conv-id"


class TestGetToolsRequiringApproval:
    """Tests for get_tools_requiring_approval function."""

    def test_returns_approval_tools(self):
        """Test that function returns tools requiring approval."""
        approval_tools = get_tools_requiring_approval()
        assert "bash_executor" in approval_tools
        assert "python_executor" in approval_tools

    def test_excludes_safe_tools(self):
        """Test that function excludes safe tools."""
        approval_tools = get_tools_requiring_approval()
        assert "file_operations" not in approval_tools
        assert "todo_list" not in approval_tools

    def test_returns_list(self):
        """Test that function returns a list."""
        result = get_tools_requiring_approval()
        assert isinstance(result, list)


class TestGetToolsByCategory:
    """Tests for get_tools_by_category function."""

    def test_get_file_tools(self):
        """Test getting file category tools."""
        file_tools = get_tools_by_category("file")
        assert "file_operations" in file_tools

    def test_get_execution_tools(self):
        """Test getting execution category tools."""
        exec_tools = get_tools_by_category("execution")
        assert "bash_executor" in exec_tools
        assert "python_executor" in exec_tools

    def test_get_web_tools(self):
        """Test getting web category tools."""
        web_tools = get_tools_by_category("web")
        assert "web_search" in web_tools
        assert "web_fetch" in web_tools

    def test_get_planning_tools(self):
        """Test getting planning category tools."""
        planning_tools = get_tools_by_category("planning")
        assert "todo_list" in planning_tools
        assert "task_planner" in planning_tools

    def test_empty_category(self):
        """Test getting tools from nonexistent category."""
        tools = get_tools_by_category("nonexistent")
        assert tools == []


class TestToolTypes:
    """Tests for tool type correctness."""

    def test_file_operations_type(self, project_dir: Path):
        """Test FileOperationsTool type."""
        tool = get_tool_by_name("file_operations", project_path=project_dir)
        assert isinstance(tool, FileOperationsTool)

    def test_bash_executor_type(self, project_dir: Path):
        """Test BashExecutorTool type."""
        tool = get_tool_by_name("bash_executor", project_path=project_dir)
        assert isinstance(tool, BashExecutorTool)

    def test_python_executor_type(self, project_dir: Path):
        """Test PythonExecutorTool type."""
        tool = get_tool_by_name("python_executor", project_path=project_dir)
        assert isinstance(tool, PythonExecutorTool)

    def test_web_search_type(self, project_dir: Path):
        """Test WebSearchTool type."""
        tool = get_tool_by_name("web_search", project_path=project_dir)
        assert isinstance(tool, WebSearchTool)

    def test_web_fetch_type(self, project_dir: Path):
        """Test WebFetchTool type."""
        tool = get_tool_by_name("web_fetch", project_path=project_dir)
        assert isinstance(tool, WebFetchTool)

    def test_todo_list_type(self, project_dir: Path):
        """Test TodoListTool type."""
        tool = get_tool_by_name("todo_list", project_path=project_dir)
        assert isinstance(tool, TodoListTool)

    def test_task_planner_type(self, project_dir: Path):
        """Test TaskPlannerTool type."""
        tool = get_tool_by_name("task_planner", project_path=project_dir)
        assert isinstance(tool, TaskPlannerTool)
