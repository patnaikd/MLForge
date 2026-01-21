"""Agent tools module.

This module provides all the tools available to the agent for executing tasks.
Tools are designed to work within project boundaries and support streaming output.

Available Tools:
- FileOperationsTool: Read, write, list, delete, move, copy files
- BashExecutorTool: Execute bash commands with timeout handling
- PythonExecutorTool: Execute Python code with streaming output
- WebSearchTool: Search web for documentation, datasets, code
- WebFetchTool: Fetch and extract content from web pages
- TodoListTool: Track agent tasks and progress
- TaskPlannerTool: Create structured task plans
"""

from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool

from src.tools.base import BaseAgentTool, ToolResult, format_file_size
from src.tools.bash_executor import BashExecutorTool, BashExecutorStreamingTool
from src.tools.file_operations import FileOperationsTool
from src.tools.python_executor import PythonExecutorTool
from src.tools.todo_list import TaskPlannerTool, TodoListTool
from src.tools.web_search import WebFetchTool, WebSearchTool

__all__ = [
    # Base classes
    "BaseAgentTool",
    "ToolResult",
    "format_file_size",
    # File operations
    "FileOperationsTool",
    # Code execution
    "BashExecutorTool",
    "BashExecutorStreamingTool",
    "PythonExecutorTool",
    # Web tools
    "WebSearchTool",
    "WebFetchTool",
    # Task tracking
    "TodoListTool",
    "TaskPlannerTool",
    # Factory function
    "create_tools",
    "get_tool_by_name",
    "TOOL_REGISTRY",
]


# Registry of available tools with their configurations
TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "file_operations": {
        "class": FileOperationsTool,
        "requires_approval": False,
        "description": "File system operations (read, write, list, delete, move)",
        "category": "file",
    },
    "bash_executor": {
        "class": BashExecutorTool,
        "requires_approval": True,
        "description": "Execute bash commands with timeout handling",
        "category": "execution",
    },
    "python_executor": {
        "class": PythonExecutorTool,
        "requires_approval": True,
        "description": "Execute Python code with streaming output",
        "category": "execution",
    },
    "web_search": {
        "class": WebSearchTool,
        "requires_approval": False,
        "description": "Search web for documentation, datasets, code",
        "category": "web",
    },
    "web_fetch": {
        "class": WebFetchTool,
        "requires_approval": False,
        "description": "Fetch and extract content from web pages",
        "category": "web",
    },
    "todo_list": {
        "class": TodoListTool,
        "requires_approval": False,
        "description": "Track agent tasks and progress",
        "category": "planning",
    },
    "task_planner": {
        "class": TaskPlannerTool,
        "requires_approval": False,
        "description": "Create structured task plans",
        "category": "planning",
    },
}


def create_tools(
    project_path: Path | None = None,
    project_id: str | None = None,
    conversation_id: str | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[BaseTool]:
    """Create tool instances for the agent.

    Args:
        project_path: Path to the project directory
        project_id: Project ID for database operations
        conversation_id: Conversation ID for context
        include: List of tool names to include (if None, include all)
        exclude: List of tool names to exclude

    Returns:
        List of tool instances
    """
    tools = []
    exclude = exclude or []

    for name, config in TOOL_REGISTRY.items():
        # Check include/exclude
        if include is not None and name not in include:
            continue
        if name in exclude:
            continue

        # Create tool instance
        tool_class = config["class"]
        tool = tool_class(
            project_path=project_path,
            project_id=project_id,
            conversation_id=conversation_id,
        )
        tools.append(tool)

    return tools


def get_tool_by_name(
    name: str,
    project_path: Path | None = None,
    project_id: str | None = None,
    conversation_id: str | None = None,
) -> BaseTool | None:
    """Get a single tool instance by name.

    Args:
        name: Tool name
        project_path: Path to the project directory
        project_id: Project ID for database operations
        conversation_id: Conversation ID for context

    Returns:
        Tool instance or None if not found
    """
    if name not in TOOL_REGISTRY:
        return None

    config = TOOL_REGISTRY[name]
    tool_class = config["class"]

    return tool_class(
        project_path=project_path,
        project_id=project_id,
        conversation_id=conversation_id,
    )


def get_tools_requiring_approval() -> list[str]:
    """Get list of tool names that require user approval.

    Returns:
        List of tool names
    """
    return [name for name, config in TOOL_REGISTRY.items() if config["requires_approval"]]


def get_tools_by_category(category: str) -> list[str]:
    """Get list of tool names in a category.

    Args:
        category: Tool category (file, execution, web, planning)

    Returns:
        List of tool names
    """
    return [name for name, config in TOOL_REGISTRY.items() if config["category"] == category]
