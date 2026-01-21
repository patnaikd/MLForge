"""Tests for the base tool class."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.tools.base import BaseAgentTool, ToolResult, format_file_size


class ConcreteTestTool(BaseAgentTool):
    """Concrete implementation of BaseAgentTool for testing."""

    name: str = "test_tool"
    description: str = "A test tool"

    def _run(self, **kwargs) -> str:
        return "test result"


@pytest.fixture
def project_dir(temp_dir: Path) -> Path:
    """Create a project directory for testing."""
    project = temp_dir / "test_project"
    project.mkdir(parents=True)
    (project / "subdir").mkdir()
    (project / "file.txt").write_text("content")
    return project


@pytest.fixture
def test_tool(project_dir: Path) -> ConcreteTestTool:
    """Create a test tool instance."""
    return ConcreteTestTool(
        project_path=project_dir,
        project_id="test-project-id",
        conversation_id="test-conversation-id",
    )


class TestBaseAgentTool:
    """Tests for BaseAgentTool class."""

    def test_initialization(self, test_tool: ConcreteTestTool, project_dir: Path):
        """Test tool initialization."""
        assert test_tool.project_path == project_dir
        assert test_tool.project_id == "test-project-id"
        assert test_tool.conversation_id == "test-conversation-id"

    def test_validate_path_relative(self, test_tool: ConcreteTestTool, project_dir: Path):
        """Test validating a relative path."""
        validated = test_tool.validate_path("subdir")
        assert validated == project_dir / "subdir"
        assert validated.is_dir()

    def test_validate_path_absolute_inside(self, test_tool: ConcreteTestTool, project_dir: Path):
        """Test validating an absolute path inside project."""
        absolute = project_dir / "file.txt"
        validated = test_tool.validate_path(str(absolute))
        assert validated == absolute.resolve()

    def test_validate_path_rejects_traversal(self, test_tool: ConcreteTestTool):
        """Test that parent directory traversal is rejected."""
        with pytest.raises(ValueError, match="outside project"):
            test_tool.validate_path("../../../etc/passwd")

    def test_validate_path_rejects_outside(self, test_tool: ConcreteTestTool, temp_dir: Path):
        """Test that paths outside project are rejected."""
        outside_file = temp_dir / "outside.txt"
        outside_file.write_text("outside")

        with pytest.raises(ValueError, match="outside project"):
            test_tool.validate_path(str(outside_file))

    def test_validate_path_no_project_path(self, project_dir: Path):
        """Test that validation fails without project path."""
        tool = ConcreteTestTool()  # No project_path set
        with pytest.raises(ValueError, match="Project path not set"):
            tool.validate_path("file.txt")

    def test_get_relative_path(self, test_tool: ConcreteTestTool, project_dir: Path):
        """Test getting relative path from absolute."""
        absolute = project_dir / "subdir" / "file.txt"
        relative = test_tool.get_relative_path(absolute)
        assert relative == "subdir/file.txt"

    def test_get_relative_path_no_project(self, project_dir: Path):
        """Test get_relative_path without project path set."""
        tool = ConcreteTestTool()
        absolute = project_dir / "file.txt"
        result = tool.get_relative_path(absolute)
        # Should return the absolute path as string
        assert result == str(absolute)

    def test_lazy_db_loading(self, test_tool: ConcreteTestTool):
        """Test that database is lazily loaded."""
        assert test_tool._db is None
        # Access db property
        db = test_tool.db
        assert db is not None
        assert test_tool._db is db  # Same instance

    def test_lazy_settings_loading(self, test_tool: ConcreteTestTool):
        """Test that settings are lazily loaded."""
        assert test_tool._settings is None
        settings = test_tool.settings
        assert settings is not None
        assert test_tool._settings is settings

    def test_lazy_logger_loading(self, test_tool: ConcreteTestTool):
        """Test that logger is lazily loaded."""
        assert test_tool._logger is None
        logger = test_tool.logger
        assert logger is not None
        assert test_tool._logger is logger


class TestToolResult:
    """Tests for ToolResult class."""

    def test_success_result(self):
        """Test creating a success result."""
        result = ToolResult(success=True, output="Operation completed")
        assert result.success is True
        assert result.output == "Operation completed"
        assert result.error is None

    def test_error_result(self):
        """Test creating an error result."""
        result = ToolResult(success=False, output="", error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_result_with_data(self):
        """Test result with additional data."""
        result = ToolResult(
            success=True,
            output="Done",
            data={"count": 5, "items": ["a", "b"]},
        )
        assert result.data["count"] == 5
        assert result.data["items"] == ["a", "b"]

    def test_str_success(self):
        """Test string representation of success result."""
        result = ToolResult(success=True, output="Success message")
        assert str(result) == "Success message"

    def test_str_error(self):
        """Test string representation of error result."""
        result = ToolResult(success=False, output="", error="Error message")
        assert "Error: Error message" in str(result)

    def test_to_dict(self):
        """Test converting result to dictionary."""
        result = ToolResult(
            success=True,
            output="Output",
            error=None,
            data={"key": "value"},
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["output"] == "Output"
        assert d["error"] is None
        assert d["data"] == {"key": "value"}


class TestFormatFileSize:
    """Tests for format_file_size utility."""

    def test_bytes(self):
        """Test formatting bytes."""
        assert format_file_size(0) == "0.0 B"
        assert format_file_size(100) == "100.0 B"
        assert format_file_size(1023) == "1023.0 B"

    def test_kilobytes(self):
        """Test formatting kilobytes."""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(2048) == "2.0 KB"
        assert format_file_size(1536) == "1.5 KB"

    def test_megabytes(self):
        """Test formatting megabytes."""
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(1024 * 1024 * 5) == "5.0 MB"

    def test_gigabytes(self):
        """Test formatting gigabytes."""
        assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_file_size(1024 * 1024 * 1024 * 2.5) == "2.5 GB"

    def test_terabytes(self):
        """Test formatting terabytes."""
        assert format_file_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"


class TestBaseToolAsync:
    """Tests for async methods."""

    @pytest.mark.asyncio
    async def test_default_arun(self, test_tool: ConcreteTestTool):
        """Test that default _arun calls _run."""
        result = await test_tool._arun()
        assert result == "test result"
