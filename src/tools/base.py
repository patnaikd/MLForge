"""Base tool class with common functionality for all agent tools."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool as LangChainBaseTool
from pydantic import Field

from src.config.settings import Settings, get_settings
from src.database.connection import Database, get_database
from src.utils.logging import get_logger
from src.utils.validators import is_safe_path


class BaseAgentTool(LangChainBaseTool, ABC):
    """Base class for all agent tools with common functionality.

    Provides:
    - Project path validation and safety checks
    - Database access for persistence
    - Settings access for configuration
    - Logging
    """

    project_path: Path | None = Field(default=None, exclude=True)
    project_id: str | None = Field(default=None, exclude=True)
    conversation_id: str | None = Field(default=None, exclude=True)
    _db: Database | None = None
    _settings: Settings | None = None
    _logger: Any = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(
        self,
        project_path: Path | None = None,
        project_id: str | None = None,
        conversation_id: str | None = None,
        **kwargs: Any,
    ):
        """Initialize the tool with project context.

        Args:
            project_path: Path to the project directory
            project_id: Project ID for database operations
            conversation_id: Conversation ID for context
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(**kwargs)
        self.project_path = project_path
        self.project_id = project_id
        self.conversation_id = conversation_id

    @property
    def db(self) -> Database:
        """Get database instance (lazy loaded)."""
        if self._db is None:
            self._db = get_database()
        return self._db

    @property
    def settings(self) -> Settings:
        """Get settings instance (lazy loaded)."""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

    @property
    def logger(self) -> Any:
        """Get logger instance (lazy loaded)."""
        if self._logger is None:
            self._logger = get_logger(f"tool.{self.name}")
        return self._logger

    def validate_path(self, path: str | Path) -> Path:
        """Validate and resolve a path within the project directory.

        Args:
            path: Path to validate (can be relative or absolute)

        Returns:
            Resolved absolute path

        Raises:
            ValueError: If path is outside project directory or project_path not set
        """
        if self.project_path is None:
            raise ValueError("Project path not set - cannot validate paths")

        # Convert to Path object
        target_path = Path(path)

        # If relative, make it relative to project path
        if not target_path.is_absolute():
            target_path = self.project_path / target_path

        # Resolve to absolute path
        target_path = target_path.resolve()

        # Check if within project directory
        if not is_safe_path(self.project_path, target_path):
            raise ValueError(
                f"Path '{path}' is outside project directory. "
                f"All file operations must be within: {self.project_path}"
            )

        return target_path

    def get_relative_path(self, absolute_path: Path) -> str:
        """Get path relative to project directory.

        Args:
            absolute_path: Absolute path to convert

        Returns:
            Path relative to project directory
        """
        if self.project_path is None:
            return str(absolute_path)

        try:
            return str(absolute_path.relative_to(self.project_path))
        except ValueError:
            return str(absolute_path)

    @abstractmethod
    def _run(self, *args: Any, **kwargs: Any) -> str:
        """Synchronous tool execution (required by LangChain).

        Should be implemented by subclasses.
        """

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        """Async tool execution.

        Default implementation calls sync _run. Override for true async.
        """
        return self._run(*args, **kwargs)


class ToolResult:
    """Standard result format for tool outputs."""

    def __init__(
        self,
        success: bool,
        output: str,
        error: str | None = None,
        data: dict[str, Any] | None = None,
    ):
        """Initialize tool result.

        Args:
            success: Whether the operation succeeded
            output: Human-readable output message
            error: Error message if failed
            data: Additional structured data
        """
        self.success = success
        self.output = output
        self.error = error
        self.data = data or {}

    def __str__(self) -> str:
        """Convert to string for tool output."""
        if self.success:
            return self.output
        return f"Error: {self.error or self.output}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "data": self.data,
        }


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
