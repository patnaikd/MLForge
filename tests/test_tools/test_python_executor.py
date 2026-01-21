"""Tests for the Python executor tool."""

import pytest
from pathlib import Path

from src.tools.python_executor import PythonExecutorTool


@pytest.fixture
def project_dir(temp_dir: Path) -> Path:
    """Create a project directory for testing."""
    project = temp_dir / "test_project"
    project.mkdir(parents=True)
    (project / "code").mkdir()
    (project / "data").mkdir()
    return project


@pytest.fixture
def python_tool(project_dir: Path) -> PythonExecutorTool:
    """Create a Python executor tool for testing."""
    return PythonExecutorTool(
        project_path=project_dir,
        project_id="test-project-id",
    )


class TestPythonExecutorBasic:
    """Basic execution tests."""

    def test_simple_print(self, python_tool: PythonExecutorTool):
        """Test executing a simple print statement."""
        result = python_tool._run(code="print('hello world')")
        assert "hello world" in result

    def test_expression_output(self, python_tool: PythonExecutorTool):
        """Test executing an expression."""
        result = python_tool._run(code="x = 2 + 2\nprint(x)")
        assert "4" in result

    def test_multiline_code(self, python_tool: PythonExecutorTool):
        """Test executing multiline code."""
        code = """
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
"""
        result = python_tool._run(code=code)
        assert "Hello, World!" in result

    def test_import_standard_library(self, python_tool: PythonExecutorTool):
        """Test importing standard library modules."""
        result = python_tool._run(code="import os\nprint(os.getcwd())")
        assert "/" in result or "\\" in result  # Path separator

    def test_syntax_error(self, python_tool: PythonExecutorTool):
        """Test that syntax errors are reported."""
        result = python_tool._run(code="print('unclosed")
        assert "Error" in result or "SyntaxError" in result

    def test_runtime_error(self, python_tool: PythonExecutorTool):
        """Test that runtime errors are reported."""
        result = python_tool._run(code="1/0")
        assert "Error" in result or "ZeroDivisionError" in result


class TestPythonExecutorDataScience:
    """Tests for data science package execution."""

    def test_import_numpy(self, python_tool: PythonExecutorTool):
        """Test importing numpy."""
        code = """
import numpy as np
arr = np.array([1, 2, 3, 4, 5])
print(f"Mean: {arr.mean()}")
"""
        result = python_tool._run(code=code)
        # If numpy is installed
        if "ModuleNotFoundError" not in result:
            assert "Mean: 3.0" in result

    def test_import_pandas(self, python_tool: PythonExecutorTool):
        """Test importing pandas."""
        code = """
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]})
print(df.shape)
"""
        result = python_tool._run(code=code)
        if "ModuleNotFoundError" not in result:
            assert "(3, 2)" in result


class TestPythonExecutorFileOperations:
    """Tests for file operations from Python code."""

    def test_read_file(self, python_tool: PythonExecutorTool, project_dir: Path):
        """Test reading a file from Python."""
        (project_dir / "data" / "test.txt").write_text("test content")

        code = """
with open('data/test.txt') as f:
    print(f.read())
"""
        result = python_tool._run(code=code)
        assert "test content" in result

    def test_write_file(self, python_tool: PythonExecutorTool, project_dir: Path):
        """Test writing a file from Python."""
        code = """
with open('data/output.txt', 'w') as f:
    f.write('written from python')
print('File written')
"""
        result = python_tool._run(code=code)
        assert "File written" in result
        assert (project_dir / "data" / "output.txt").read_text() == "written from python"

    def test_uses_project_path(self, python_tool: PythonExecutorTool, project_dir: Path):
        """Test that code runs in project directory."""
        code = """
import os
print(os.getcwd())
"""
        result = python_tool._run(code=code)
        assert str(project_dir.name) in result


class TestPythonExecutorScriptSaving:
    """Tests for script saving functionality."""

    def test_save_script(self, python_tool: PythonExecutorTool, project_dir: Path):
        """Test saving script to file."""
        code = "print('saved script')"
        result = python_tool._run(code=code, save_script=True, script_name="test_script.py")

        assert "saved script" in result
        assert (project_dir / "code" / "test_script.py").exists()
        assert (project_dir / "code" / "test_script.py").read_text() == code

    def test_save_script_auto_name(self, python_tool: PythonExecutorTool, project_dir: Path):
        """Test saving script with auto-generated name."""
        code = "print('auto name')"
        result = python_tool._run(code=code, save_script=True)

        assert "auto name" in result
        # Should have created a file in code/
        py_files = list((project_dir / "code").glob("*.py"))
        assert len(py_files) >= 1

    def test_save_script_adds_extension(self, python_tool: PythonExecutorTool, project_dir: Path):
        """Test that .py extension is added if missing."""
        code = "print('test')"
        python_tool._run(code=code, save_script=True, script_name="no_extension")

        assert (project_dir / "code" / "no_extension.py").exists()


class TestPythonExecutorTimeout:
    """Tests for timeout handling."""

    def test_timeout_setting_used(self, python_tool: PythonExecutorTool):
        """Test that custom timeout is used."""
        result = python_tool._run(code="print('quick')", timeout=10)
        assert "quick" in result

    def test_code_timeout(self, python_tool: PythonExecutorTool):
        """Test that long-running code times out."""
        result = python_tool._run(code="import time; time.sleep(10)", timeout=1)
        assert "timeout" in result.lower()


class TestPythonExecutorEnvironment:
    """Tests for environment variable handling."""

    def test_project_path_in_env(self, python_tool: PythonExecutorTool, project_dir: Path):
        """Test that PROJECT_PATH is available."""
        code = """
import os
print(os.environ.get('PROJECT_PATH', 'not set'))
"""
        result = python_tool._run(code=code)
        assert str(project_dir) in result

    def test_unbuffered_output(self, python_tool: PythonExecutorTool):
        """Test that output is unbuffered."""
        code = """
import sys
print('line1')
sys.stdout.flush()
print('line2')
"""
        result = python_tool._run(code=code)
        assert "line1" in result
        assert "line2" in result


class TestPythonExecutorAsync:
    """Tests for async execution."""

    @pytest.mark.asyncio
    async def test_async_simple(self, python_tool: PythonExecutorTool):
        """Test async execution of simple code."""
        result = await python_tool._arun(code="print('async python')")
        assert "async python" in result

    @pytest.mark.asyncio
    async def test_async_with_save(self, python_tool: PythonExecutorTool, project_dir: Path):
        """Test async execution with script saving."""
        result = await python_tool._arun(
            code="print('saved async')",
            save_script=True,
            script_name="async_script.py",
        )
        assert "saved async" in result
        assert (project_dir / "code" / "async_script.py").exists()


class TestPythonExecutorEdgeCases:
    """Tests for edge cases."""

    def test_empty_code(self, python_tool: PythonExecutorTool):
        """Test executing empty code."""
        result = python_tool._run(code="")
        assert "no output" in result.lower() or result.strip() == ""

    def test_whitespace_only(self, python_tool: PythonExecutorTool):
        """Test executing whitespace-only code."""
        result = python_tool._run(code="   \n\n   ")
        assert "no output" in result.lower() or result.strip() == ""

    def test_unicode_output(self, python_tool: PythonExecutorTool):
        """Test code with unicode output."""
        result = python_tool._run(code="print('Hello 世界 🌍')")
        assert "Hello" in result

    def test_large_output(self, python_tool: PythonExecutorTool):
        """Test code with large output."""
        code = "print('x' * 10000)"
        result = python_tool._run(code=code)
        assert "x" in result

    def test_stderr_capture(self, python_tool: PythonExecutorTool):
        """Test that stderr is captured."""
        code = """
import sys
print('stdout', file=sys.stdout)
print('stderr', file=sys.stderr)
"""
        result = python_tool._run(code=code)
        assert "stdout" in result
        assert "stderr" in result
