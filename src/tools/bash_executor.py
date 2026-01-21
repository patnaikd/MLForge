"""Bash command execution tool with timeout handling and streaming output."""

import asyncio
import os
import signal
import subprocess
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.tools.base import BaseAgentTool, ToolResult
from src.utils.timeout import ActivityTimeoutError, OverallTimeoutError


class BashExecuteInput(BaseModel):
    """Input schema for bash command execution."""

    command: str = Field(description="The bash command to execute")
    timeout: int | None = Field(
        default=None,
        description="Overall timeout in seconds (default: from settings)",
    )
    activity_timeout: int | None = Field(
        default=None,
        description="Activity timeout - max seconds without output (default: from settings)",
    )
    working_dir: str | None = Field(
        default=None,
        description="Working directory for command (relative to project, default: project root)",
    )
    env: dict[str, str] | None = Field(
        default=None,
        description="Additional environment variables to set",
    )


class BashExecutorTool(BaseAgentTool):
    """Tool for executing bash commands with timeout handling.

    Features:
    - Activity timeout: cancels if no output for specified time
    - Overall timeout: cancels if total execution exceeds limit
    - Output streaming: yields output as it becomes available
    - Working directory: runs in project context
    - Environment variables: supports custom env vars
    """

    name: str = "bash_executor"
    description: str = """Execute bash commands in the project directory.

Features:
- Commands run in the project directory by default
- Activity timeout: stops if no output for too long (default: 5 minutes)
- Overall timeout: stops if total time exceeds limit (default: 60 minutes)
- Captures both stdout and stderr

Security:
- Commands run in the project directory context
- Environment variables from the system are inherited
- Additional env vars can be specified

Example usage:
- List files: {"command": "ls -la"}
- Run script: {"command": "python scripts/analyze.py", "timeout": 600}
- Install package: {"command": "pip install pandas", "working_dir": "."}

Note: This tool requires user approval for execution as it can modify system state.
"""
    args_schema: type[BaseModel] = BashExecuteInput

    # Dangerous commands that should be blocked or warned
    BLOCKED_PATTERNS: list[str] = [
        "rm -rf /",
        "rm -rf /*",
        ":(){ :|:& };:",  # Fork bomb
        "> /dev/sda",
        "mkfs.",
        "dd if=",
    ]

    WARNING_PATTERNS: list[str] = [
        "sudo",
        "chmod 777",
        "curl | bash",
        "wget | bash",
        "eval",
    ]

    def _check_command_safety(self, command: str) -> tuple[bool, str | None]:
        """Check if a command is safe to execute.

        Args:
            command: Command to check

        Returns:
            Tuple of (is_safe, warning_message)
        """
        command_lower = command.lower()

        # Check blocked patterns
        for pattern in self.BLOCKED_PATTERNS:
            if pattern.lower() in command_lower:
                return False, f"Command contains blocked pattern: {pattern}"

        # Check warning patterns
        warnings = []
        for pattern in self.WARNING_PATTERNS:
            if pattern.lower() in command_lower:
                warnings.append(pattern)

        if warnings:
            return True, f"Warning: Command uses potentially dangerous patterns: {', '.join(warnings)}"

        return True, None

    def _run(
        self,
        command: str,
        timeout: int | None = None,
        activity_timeout: int | None = None,
        working_dir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        """Execute a bash command synchronously.

        Args:
            command: Bash command to execute
            timeout: Overall timeout in seconds
            activity_timeout: Activity timeout in seconds
            working_dir: Working directory (relative to project)
            env: Additional environment variables

        Returns:
            Command output or error message
        """
        self.logger.info(f"Executing bash command: {command}")

        # Check command safety
        is_safe, warning = self._check_command_safety(command)
        if not is_safe:
            return str(ToolResult(False, "", warning))

        # Resolve working directory
        if working_dir:
            cwd = self.validate_path(working_dir)
        elif self.project_path:
            cwd = self.project_path
        else:
            cwd = Path.cwd()

        if not cwd.is_dir():
            return str(ToolResult(False, "", f"Working directory does not exist: {cwd}"))

        # Get timeout values
        overall_timeout = timeout or self.settings.overall_timeout
        act_timeout = activity_timeout or self.settings.activity_timeout

        # Prepare environment
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        # Add project path to environment
        if self.project_path:
            process_env["PROJECT_PATH"] = str(self.project_path)

        try:
            # Run the command
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(cwd),
                env=process_env,
                capture_output=True,
                text=True,
                timeout=overall_timeout,
            )

            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"

            if result.returncode == 0:
                return str(
                    ToolResult(
                        True,
                        output if output else "(no output)",
                        data={
                            "command": command,
                            "return_code": result.returncode,
                            "working_dir": str(cwd),
                        },
                    )
                )
            else:
                return str(
                    ToolResult(
                        False,
                        output if output else "(no output)",
                        error=f"Command exited with code {result.returncode}",
                        data={
                            "command": command,
                            "return_code": result.returncode,
                            "working_dir": str(cwd),
                        },
                    )
                )

        except subprocess.TimeoutExpired:
            return str(
                ToolResult(
                    False,
                    "",
                    error=f"Command timed out after {overall_timeout} seconds",
                    data={"command": command, "timeout": overall_timeout},
                )
            )
        except Exception as e:
            self.logger.error(f"Bash execution error: {e}")
            return str(ToolResult(False, "", error=f"Execution failed: {str(e)}"))

    async def _arun(
        self,
        command: str,
        timeout: int | None = None,
        activity_timeout: int | None = None,
        working_dir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        """Execute a bash command asynchronously with streaming output.

        Args:
            command: Bash command to execute
            timeout: Overall timeout in seconds
            activity_timeout: Activity timeout in seconds
            working_dir: Working directory (relative to project)
            env: Additional environment variables

        Returns:
            Command output or error message
        """
        self.logger.info(f"Executing bash command (async): {command}")

        # Check command safety
        is_safe, warning = self._check_command_safety(command)
        if not is_safe:
            return str(ToolResult(False, "", warning))

        # Resolve working directory
        if working_dir:
            cwd = self.validate_path(working_dir)
        elif self.project_path:
            cwd = self.project_path
        else:
            cwd = Path.cwd()

        if not cwd.is_dir():
            return str(ToolResult(False, "", f"Working directory does not exist: {cwd}"))

        # Get timeout values
        overall_timeout = timeout or self.settings.overall_timeout
        act_timeout = activity_timeout or self.settings.activity_timeout

        # Prepare environment
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        if self.project_path:
            process_env["PROJECT_PATH"] = str(self.project_path)

        # Collect output from streaming
        output_parts: list[str] = []

        try:
            async for chunk in self.execute_streaming(
                command=command,
                cwd=cwd,
                env=process_env,
                overall_timeout=overall_timeout,
                activity_timeout=act_timeout,
            ):
                output_parts.append(chunk)

            output = "".join(output_parts)
            return str(
                ToolResult(
                    True,
                    output if output else "(no output)",
                    data={
                        "command": command,
                        "return_code": 0,
                        "working_dir": str(cwd),
                    },
                )
            )

        except ActivityTimeoutError:
            output = "".join(output_parts)
            return str(
                ToolResult(
                    False,
                    output,
                    error=f"Activity timeout: no output for {act_timeout} seconds",
                    data={"command": command, "partial_output": True},
                )
            )
        except OverallTimeoutError:
            output = "".join(output_parts)
            return str(
                ToolResult(
                    False,
                    output,
                    error=f"Overall timeout after {overall_timeout} seconds",
                    data={"command": command, "partial_output": True},
                )
            )
        except Exception as e:
            self.logger.error(f"Async bash execution error: {e}")
            return str(ToolResult(False, "", error=f"Execution failed: {str(e)}"))

    async def execute_streaming(
        self,
        command: str,
        cwd: Path,
        env: dict[str, str],
        overall_timeout: int,
        activity_timeout: int,
    ) -> AsyncGenerator[str, None]:
        """Execute command with streaming output.

        Args:
            command: Command to execute
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
        process = await asyncio.create_subprocess_shell(
            command,
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
                        f"Command exceeded overall timeout of {overall_timeout}s"
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


class BashExecutorStreamingTool(BashExecutorTool):
    """Bash executor that returns a generator for streaming output.

    Use this variant when you need real-time output updates.
    """

    name: str = "bash_executor_streaming"
    description: str = """Execute bash commands with real-time streaming output.

Same as bash_executor but provides output in real-time chunks.
Useful for long-running commands where you need progress updates.
"""

    async def execute_with_callbacks(
        self,
        command: str,
        on_output: Any,
        timeout: int | None = None,
        activity_timeout: int | None = None,
        working_dir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> ToolResult:
        """Execute command and call back with each output chunk.

        Args:
            command: Command to execute
            on_output: Callback function(chunk: str) -> None
            timeout: Overall timeout
            activity_timeout: Activity timeout
            working_dir: Working directory
            env: Environment variables

        Returns:
            Final result
        """
        # Resolve working directory
        if working_dir:
            cwd = self.validate_path(working_dir)
        elif self.project_path:
            cwd = self.project_path
        else:
            cwd = Path.cwd()

        overall_timeout = timeout or self.settings.overall_timeout
        act_timeout = activity_timeout or self.settings.activity_timeout

        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        if self.project_path:
            process_env["PROJECT_PATH"] = str(self.project_path)

        output_parts: list[str] = []

        try:
            async for chunk in self.execute_streaming(
                command=command,
                cwd=cwd,
                env=process_env,
                overall_timeout=overall_timeout,
                activity_timeout=act_timeout,
            ):
                output_parts.append(chunk)
                if on_output:
                    on_output(chunk)

            return ToolResult(
                True,
                "".join(output_parts) or "(no output)",
                data={"command": command, "return_code": 0},
            )

        except (ActivityTimeoutError, OverallTimeoutError) as e:
            return ToolResult(
                False,
                "".join(output_parts),
                error=str(e),
                data={"command": command, "partial_output": True},
            )
        except Exception as e:
            return ToolResult(
                False,
                "".join(output_parts),
                error=str(e),
            )
