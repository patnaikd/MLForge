"""Tests for the bash executor tool."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.tools.bash_executor import BashExecutorTool


@pytest.fixture
def project_dir(temp_dir: Path) -> Path:
    """Create a project directory for testing."""
    project = temp_dir / "test_project"
    project.mkdir(parents=True)
    return project


@pytest.fixture
def bash_tool(project_dir: Path) -> BashExecutorTool:
    """Create a bash executor tool for testing."""
    return BashExecutorTool(
        project_path=project_dir,
        project_id="test-project-id",
    )


class TestBashExecutorBasic:
    """Basic execution tests."""

    def test_simple_command(self, bash_tool: BashExecutorTool):
        """Test executing a simple command."""
        result = bash_tool._run(command="echo hello")
        assert "hello" in result

    def test_command_with_args(self, bash_tool: BashExecutorTool):
        """Test command with arguments."""
        result = bash_tool._run(command="echo 'hello world'")
        assert "hello world" in result

    def test_command_failure(self, bash_tool: BashExecutorTool):
        """Test that command failures are reported."""
        result = bash_tool._run(command="exit 1")
        assert "Error" in result or "code 1" in result

    def test_stderr_capture(self, bash_tool: BashExecutorTool):
        """Test that stderr is captured."""
        result = bash_tool._run(command="echo error >&2")
        assert "error" in result

    def test_multiline_output(self, bash_tool: BashExecutorTool):
        """Test multiline command output."""
        result = bash_tool._run(command="echo 'line1'; echo 'line2'; echo 'line3'")
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result


class TestBashExecutorWorkingDirectory:
    """Tests for working directory handling."""

    def test_default_working_dir(self, bash_tool: BashExecutorTool, project_dir: Path):
        """Test that default working directory is project root."""
        result = bash_tool._run(command="pwd")
        assert str(project_dir) in result

    def test_custom_working_dir(self, bash_tool: BashExecutorTool, project_dir: Path):
        """Test executing in a custom working directory."""
        subdir = project_dir / "subdir"
        subdir.mkdir()

        result = bash_tool._run(command="pwd", working_dir="subdir")
        assert "subdir" in result

    def test_invalid_working_dir(self, bash_tool: BashExecutorTool):
        """Test that invalid working directory fails."""
        result = bash_tool._run(command="pwd", working_dir="nonexistent")
        assert "Error" in result or "not found" in result.lower() or "does not exist" in result.lower()


class TestBashExecutorEnvironment:
    """Tests for environment variable handling."""

    def test_inherits_environment(self, bash_tool: BashExecutorTool):
        """Test that system environment is inherited."""
        with patch.dict("os.environ", {"TEST_VAR": "test_value"}):
            result = bash_tool._run(command="echo $TEST_VAR")
            assert "test_value" in result

    def test_custom_environment(self, bash_tool: BashExecutorTool):
        """Test passing custom environment variables."""
        result = bash_tool._run(
            command="echo $CUSTOM_VAR",
            env={"CUSTOM_VAR": "custom_value"},
        )
        assert "custom_value" in result

    def test_project_path_in_env(self, bash_tool: BashExecutorTool, project_dir: Path):
        """Test that PROJECT_PATH is set in environment."""
        result = bash_tool._run(command="echo $PROJECT_PATH")
        assert str(project_dir) in result


class TestBashExecutorTimeout:
    """Tests for timeout handling."""

    def test_timeout_setting_used(self, bash_tool: BashExecutorTool):
        """Test that custom timeout is used."""
        # Quick command should complete
        result = bash_tool._run(command="echo quick", timeout=10)
        assert "quick" in result

    def test_command_timeout(self, bash_tool: BashExecutorTool):
        """Test that long commands timeout."""
        result = bash_tool._run(command="sleep 10", timeout=1)
        assert "timeout" in result.lower()


class TestBashExecutorSafety:
    """Tests for command safety checks."""

    def test_blocks_dangerous_rm(self, bash_tool: BashExecutorTool):
        """Test that dangerous rm commands are blocked."""
        result = bash_tool._run(command="rm -rf /")
        assert "blocked" in result.lower() or "Error" in result

    def test_blocks_fork_bomb(self, bash_tool: BashExecutorTool):
        """Test that fork bomb is blocked."""
        result = bash_tool._run(command=":(){ :|:& };:")
        assert "blocked" in result.lower() or "Error" in result

    def test_warns_about_sudo(self, bash_tool: BashExecutorTool):
        """Test that sudo commands show warning."""
        # We test the safety check, not actual execution
        is_safe, warning = bash_tool._check_command_safety("sudo apt install something")
        assert is_safe is True  # Allowed but warned
        assert warning is not None
        assert "sudo" in warning.lower()

    def test_allows_safe_commands(self, bash_tool: BashExecutorTool):
        """Test that safe commands are allowed."""
        is_safe, warning = bash_tool._check_command_safety("ls -la")
        assert is_safe is True
        assert warning is None


class TestBashExecutorFileOperations:
    """Tests for file operations via bash."""

    def test_create_file(self, bash_tool: BashExecutorTool, project_dir: Path):
        """Test creating a file with echo."""
        bash_tool._run(command="echo 'test content' > test.txt")
        assert (project_dir / "test.txt").exists()

    def test_list_files(self, bash_tool: BashExecutorTool, project_dir: Path):
        """Test listing files."""
        (project_dir / "file1.txt").write_text("content")
        (project_dir / "file2.txt").write_text("content")

        result = bash_tool._run(command="ls")
        assert "file1.txt" in result
        assert "file2.txt" in result

    def test_cat_file(self, bash_tool: BashExecutorTool, project_dir: Path):
        """Test reading file with cat."""
        (project_dir / "readable.txt").write_text("file contents here")

        result = bash_tool._run(command="cat readable.txt")
        assert "file contents here" in result


class TestBashExecutorPipedCommands:
    """Tests for piped and complex commands."""

    def test_piped_command(self, bash_tool: BashExecutorTool, project_dir: Path):
        """Test command with pipes."""
        result = bash_tool._run(command="echo 'hello world' | tr 'a-z' 'A-Z'")
        assert "HELLO WORLD" in result

    def test_chained_commands(self, bash_tool: BashExecutorTool):
        """Test chained commands with &&."""
        result = bash_tool._run(command="echo 'first' && echo 'second'")
        assert "first" in result
        assert "second" in result

    def test_subshell(self, bash_tool: BashExecutorTool):
        """Test subshell execution."""
        result = bash_tool._run(command="echo $(echo nested)")
        assert "nested" in result


class TestBashExecutorAsync:
    """Tests for async execution."""

    @pytest.mark.asyncio
    async def test_async_simple_command(self, bash_tool: BashExecutorTool):
        """Test async execution of simple command."""
        result = await bash_tool._arun(command="echo async")
        assert "async" in result

    @pytest.mark.asyncio
    async def test_async_streams_output(self, bash_tool: BashExecutorTool):
        """Test that async execution supports streaming."""
        result = await bash_tool._arun(
            command="echo 'line1'; sleep 0.1; echo 'line2'"
        )
        assert "line1" in result
        assert "line2" in result
