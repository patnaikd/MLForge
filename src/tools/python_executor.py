"""Python code execution tool with streaming output and timeout handling."""

import asyncio
import os
import sys
import tempfile
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.tools.base import BaseAgentTool, ToolResult
from src.utils.timeout import ActivityTimeoutError, OverallTimeoutError


class PythonExecuteInput(BaseModel):
    """Input schema for Python code execution."""

    code: str = Field(description="Python code to execute")
    timeout: int | None = Field(
        default=None,
        description="Overall timeout in seconds (default: from settings)",
    )
    activity_timeout: int | None = Field(
        default=None,
        description="Activity timeout - max seconds without output (default: from settings)",
    )
    save_script: bool = Field(
        default=False,
        description="Save the code to a file in the code/ directory",
    )
    script_name: str | None = Field(
        default=None,
        description="Name for saved script (default: auto-generated)",
    )


class PythonExecutorTool(BaseAgentTool):
    """Tool for executing Python code with streaming output.

    Features:
    - Executes Python code in the project's virtual environment
    - Activity timeout: cancels if no output for specified time
    - Overall timeout: cancels if total execution exceeds limit
    - Output streaming: yields output as it becomes available
    - Script saving: optionally saves code to project's code/ directory
    - Working directory: runs in project context
    """

    name: str = "python_executor"
    description: str = """Execute Python code in the project environment.

Features:
- Code runs in the project directory context
- Uses the project's Python environment (if available)
- Activity timeout: stops if no output for too long (default: 5 minutes)
- Overall timeout: stops if total time exceeds limit (default: 60 minutes)
- Can save scripts to the code/ directory for later use

Common data science packages are pre-installed:
- numpy, pandas, scipy
- scikit-learn, xgboost, lightgbm
- matplotlib, seaborn, plotly
- statsmodels, and more

Example usage:
- Run analysis: {"code": "import pandas as pd\\ndf = pd.read_csv('data/input.csv')\\nprint(df.describe())"}
- Save and run: {"code": "...", "save_script": true, "script_name": "analysis.py"}
- With timeout: {"code": "...", "timeout": 300}

Note: This tool requires user approval for execution.
"""
    args_schema: type[BaseModel] = PythonExecuteInput

    def _get_python_executable(self) -> str:
        """Get the Python executable to use.

        Returns the path to the project's venv Python if available,
        otherwise returns the current Python executable.
        """
        if self.project_path:
            # Check for workspace venv
            workspace_venv = self.settings.workspace_path / ".venv"
            if workspace_venv.exists():
                if sys.platform == "win32":
                    python_path = workspace_venv / "Scripts" / "python.exe"
                else:
                    python_path = workspace_venv / "bin" / "python"
                if python_path.exists():
                    return str(python_path)

        # Fall back to current Python
        return sys.executable

    def _save_script(self, code: str, script_name: str | None) -> Path:
        """Save code to the code/ directory.

        Args:
            code: Python code to save
            script_name: Name for the script file

        Returns:
            Path to saved script
        """
        if self.project_path is None:
            raise ValueError("Project path not set - cannot save script")

        code_dir = self.project_path / "code"
        code_dir.mkdir(parents=True, exist_ok=True)

        if script_name is None:
            # Generate unique name
            import uuid
            script_name = f"script_{uuid.uuid4().hex[:8]}.py"
        elif not script_name.endswith(".py"):
            script_name += ".py"

        script_path = code_dir / script_name
        script_path.write_text(code, encoding="utf-8")

        return script_path

    def _run(
        self,
        code: str,
        timeout: int | None = None,
        activity_timeout: int | None = None,
        save_script: bool = False,
        script_name: str | None = None,
    ) -> str:
        """Execute Python code synchronously.

        Args:
            code: Python code to execute
            timeout: Overall timeout in seconds
            activity_timeout: Activity timeout in seconds
            save_script: Whether to save the script
            script_name: Name for saved script

        Returns:
            Execution output or error message
        """
        self.logger.info("Executing Python code")

        # Get working directory
        cwd = self.project_path or Path.cwd()

        # Get timeout values
        overall_timeout = timeout or self.settings.overall_timeout

        # Get Python executable
        python_exe = self._get_python_executable()

        # Optionally save script
        saved_path = None
        if save_script:
            try:
                saved_path = self._save_script(code, script_name)
                self.logger.info(f"Saved script to {saved_path}")
            except Exception as e:
                self.logger.warning(f"Failed to save script: {e}")

        # Write code to temporary file for execution
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            temp_script = f.name

        try:
            import subprocess

            # Prepare environment
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            if self.project_path:
                env["PROJECT_PATH"] = str(self.project_path)
                # Add project path to PYTHONPATH
                python_path = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = f"{self.project_path}:{python_path}" if python_path else str(self.project_path)

            result = subprocess.run(
                [python_exe, temp_script],
                cwd=str(cwd),
                env=env,
                capture_output=True,
                text=True,
                timeout=overall_timeout,
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            data = {
                "return_code": result.returncode,
                "working_dir": str(cwd),
                "python": python_exe,
            }
            if saved_path:
                data["saved_script"] = str(saved_path.relative_to(self.project_path))

            if result.returncode == 0:
                return str(
                    ToolResult(
                        True,
                        output if output else "(no output)",
                        data=data,
                    )
                )
            else:
                return str(
                    ToolResult(
                        False,
                        output if output else "(no output)",
                        error=f"Script exited with code {result.returncode}",
                        data=data,
                    )
                )

        except subprocess.TimeoutExpired:
            return str(
                ToolResult(
                    False,
                    "",
                    error=f"Execution timed out after {overall_timeout} seconds",
                    data={"timeout": overall_timeout},
                )
            )
        except Exception as e:
            self.logger.error(f"Python execution error: {e}")
            return str(ToolResult(False, "", error=f"Execution failed: {str(e)}"))
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_script)
            except OSError:
                pass

    async def _arun(
        self,
        code: str,
        timeout: int | None = None,
        activity_timeout: int | None = None,
        save_script: bool = False,
        script_name: str | None = None,
    ) -> str:
        """Execute Python code asynchronously with streaming output.

        Args:
            code: Python code to execute
            timeout: Overall timeout in seconds
            activity_timeout: Activity timeout in seconds
            save_script: Whether to save the script
            script_name: Name for saved script

        Returns:
            Execution output or error message
        """
        self.logger.info("Executing Python code (async)")

        # Get working directory
        cwd = self.project_path or Path.cwd()

        # Get timeout values
        overall_timeout = timeout or self.settings.overall_timeout
        act_timeout = activity_timeout or self.settings.activity_timeout

        # Get Python executable
        python_exe = self._get_python_executable()

        # Optionally save script
        saved_path = None
        if save_script:
            try:
                saved_path = self._save_script(code, script_name)
            except Exception as e:
                self.logger.warning(f"Failed to save script: {e}")

        # Write code to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            temp_script = f.name

        try:
            # Prepare environment
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            if self.project_path:
                env["PROJECT_PATH"] = str(self.project_path)
                python_path = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = f"{self.project_path}:{python_path}" if python_path else str(self.project_path)

            # Collect output from streaming
            output_parts: list[str] = []

            async for chunk in self._execute_streaming(
                python_exe=python_exe,
                script_path=temp_script,
                cwd=cwd,
                env=env,
                overall_timeout=overall_timeout,
                activity_timeout=act_timeout,
            ):
                output_parts.append(chunk)

            output = "".join(output_parts)

            data = {
                "return_code": 0,
                "working_dir": str(cwd),
                "python": python_exe,
            }
            if saved_path:
                data["saved_script"] = str(saved_path.relative_to(self.project_path))

            return str(
                ToolResult(
                    True,
                    output if output else "(no output)",
                    data=data,
                )
            )

        except ActivityTimeoutError:
            output = "".join(output_parts) if "output_parts" in locals() else ""
            return str(
                ToolResult(
                    False,
                    output,
                    error=f"Activity timeout: no output for {act_timeout} seconds",
                    data={"partial_output": True},
                )
            )
        except OverallTimeoutError:
            output = "".join(output_parts) if "output_parts" in locals() else ""
            return str(
                ToolResult(
                    False,
                    output,
                    error=f"Overall timeout after {overall_timeout} seconds",
                    data={"partial_output": True},
                )
            )
        except Exception as e:
            self.logger.error(f"Async Python execution error: {e}")
            return str(ToolResult(False, "", error=f"Execution failed: {str(e)}"))
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_script)
            except OSError:
                pass

    async def _execute_streaming(
        self,
        python_exe: str,
        script_path: str,
        cwd: Path,
        env: dict[str, str],
        overall_timeout: int,
        activity_timeout: int,
    ) -> AsyncGenerator[str, None]:
        """Execute Python script with streaming output.

        Args:
            python_exe: Path to Python executable
            script_path: Path to script file
            cwd: Working directory
            env: Environment variables
            overall_timeout: Overall timeout in seconds
            activity_timeout: Activity timeout in seconds

        Yields:
            Output chunks as they become available

        Raises:
            ActivityTimeoutError: If no output for too long
            OverallTimeoutError: If total execution exceeds limit
        """
        start_time = time.monotonic()
        last_activity = start_time

        # Create the subprocess
        process = await asyncio.create_subprocess_exec(
            python_exe,
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(cwd),
            env=env,
        )

        try:
            while True:
                current_time = time.monotonic()

                # Check overall timeout
                if current_time - start_time > overall_timeout:
                    raise OverallTimeoutError(
                        f"Execution exceeded overall timeout of {overall_timeout}s"
                    )

                # Check activity timeout
                if current_time - last_activity > activity_timeout:
                    raise ActivityTimeoutError(
                        f"No output for {activity_timeout}s"
                    )

                # Try to read some output with a small timeout
                try:
                    chunk = await asyncio.wait_for(
                        process.stdout.read(4096),
                        timeout=min(1.0, activity_timeout / 2),
                    )

                    if chunk:
                        last_activity = time.monotonic()
                        yield chunk.decode("utf-8", errors="replace")
                    else:
                        # EOF - process has ended
                        break

                except asyncio.TimeoutError:
                    # No data available, but process still running
                    if process.returncode is not None:
                        break
                    continue

        finally:
            # Ensure process is terminated
            if process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

    async def execute_with_callbacks(
        self,
        code: str,
        on_output: Any,
        timeout: int | None = None,
        activity_timeout: int | None = None,
        save_script: bool = False,
        script_name: str | None = None,
    ) -> ToolResult:
        """Execute code and call back with each output chunk.

        Args:
            code: Python code to execute
            on_output: Callback function(chunk: str) -> None
            timeout: Overall timeout
            activity_timeout: Activity timeout
            save_script: Whether to save script
            script_name: Name for saved script

        Returns:
            Final result
        """
        cwd = self.project_path or Path.cwd()
        overall_timeout = timeout or self.settings.overall_timeout
        act_timeout = activity_timeout or self.settings.activity_timeout
        python_exe = self._get_python_executable()

        # Optionally save script
        saved_path = None
        if save_script:
            try:
                saved_path = self._save_script(code, script_name)
            except Exception as e:
                self.logger.warning(f"Failed to save script: {e}")

        # Write code to temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            temp_script = f.name

        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            if self.project_path:
                env["PROJECT_PATH"] = str(self.project_path)
                python_path = env.get("PYTHONPATH", "")
                env["PYTHONPATH"] = f"{self.project_path}:{python_path}" if python_path else str(self.project_path)

            output_parts: list[str] = []

            async for chunk in self._execute_streaming(
                python_exe=python_exe,
                script_path=temp_script,
                cwd=cwd,
                env=env,
                overall_timeout=overall_timeout,
                activity_timeout=act_timeout,
            ):
                output_parts.append(chunk)
                if on_output:
                    on_output(chunk)

            data = {
                "return_code": 0,
                "working_dir": str(cwd),
                "python": python_exe,
            }
            if saved_path:
                data["saved_script"] = str(saved_path.relative_to(self.project_path))

            return ToolResult(
                True,
                "".join(output_parts) or "(no output)",
                data=data,
            )

        except (ActivityTimeoutError, OverallTimeoutError) as e:
            return ToolResult(
                False,
                "".join(output_parts) if "output_parts" in locals() else "",
                error=str(e),
                data={"partial_output": True},
            )
        except Exception as e:
            return ToolResult(
                False,
                "".join(output_parts) if "output_parts" in locals() else "",
                error=str(e),
            )
        finally:
            try:
                os.unlink(temp_script)
            except OSError:
                pass
