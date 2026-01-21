"""File operations tool for reading, writing, listing, deleting, and moving files."""

import os
import shutil
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.tools.base import BaseAgentTool, ToolResult, format_file_size


class FileReadInput(BaseModel):
    """Input schema for reading a file."""

    path: str = Field(description="Path to the file to read (relative to project directory)")
    encoding: str = Field(default="utf-8", description="File encoding (default: utf-8)")
    max_lines: int | None = Field(
        default=None,
        description="Maximum number of lines to read (None for all)",
    )


class FileWriteInput(BaseModel):
    """Input schema for writing a file."""

    path: str = Field(description="Path to the file to write (relative to project directory)")
    content: str = Field(description="Content to write to the file")
    encoding: str = Field(default="utf-8", description="File encoding (default: utf-8)")
    append: bool = Field(default=False, description="Append to file instead of overwriting")


class FileListInput(BaseModel):
    """Input schema for listing directory contents."""

    path: str = Field(
        default=".",
        description="Path to directory to list (relative to project directory)",
    )
    recursive: bool = Field(default=False, description="List contents recursively")
    pattern: str | None = Field(
        default=None,
        description="Glob pattern to filter files (e.g., '*.py', '**/*.csv')",
    )


class FileDeleteInput(BaseModel):
    """Input schema for deleting a file or directory."""

    path: str = Field(description="Path to file or directory to delete")
    recursive: bool = Field(
        default=False,
        description="Delete directories recursively (required for non-empty dirs)",
    )


class FileMoveInput(BaseModel):
    """Input schema for moving/renaming a file or directory."""

    source: str = Field(description="Source path (relative to project directory)")
    destination: str = Field(description="Destination path (relative to project directory)")


class FileCopyInput(BaseModel):
    """Input schema for copying a file or directory."""

    source: str = Field(description="Source path (relative to project directory)")
    destination: str = Field(description="Destination path (relative to project directory)")


class FileOperationInput(BaseModel):
    """Unified input schema for file operations."""

    operation: Literal["read", "write", "list", "delete", "move", "copy", "exists", "info"] = Field(
        description="The file operation to perform"
    )
    path: str = Field(description="Primary path for the operation")
    content: str | None = Field(default=None, description="Content for write operations")
    destination: str | None = Field(default=None, description="Destination path for move/copy")
    encoding: str = Field(default="utf-8", description="File encoding")
    recursive: bool = Field(default=False, description="Recursive operation flag")
    append: bool = Field(default=False, description="Append mode for write")
    pattern: str | None = Field(default=None, description="Glob pattern for list")
    max_lines: int | None = Field(default=None, description="Max lines for read")


class FileOperationsTool(BaseAgentTool):
    """Tool for performing file system operations within the project directory.

    Supports: read, write, list, delete, move, copy, exists, info operations.
    All paths are validated to ensure they stay within the project directory.
    """

    name: str = "file_operations"
    description: str = """Perform file operations within the project directory.

Operations:
- read: Read contents of a file
- write: Write content to a file (creates directories as needed)
- list: List contents of a directory
- delete: Delete a file or directory
- move: Move/rename a file or directory
- copy: Copy a file or directory
- exists: Check if a path exists
- info: Get information about a file/directory

All paths are relative to the project directory. Attempting to access files
outside the project directory will fail.

Example usage:
- Read a file: {"operation": "read", "path": "data/input.csv"}
- Write a file: {"operation": "write", "path": "code/analysis.py", "content": "..."}
- List directory: {"operation": "list", "path": "data", "pattern": "*.csv"}
- Delete file: {"operation": "delete", "path": "outputs/old_results.json"}
- Move file: {"operation": "move", "path": "temp.txt", "destination": "data/temp.txt"}
"""
    args_schema: type[BaseModel] = FileOperationInput

    def _run(
        self,
        operation: str,
        path: str,
        content: str | None = None,
        destination: str | None = None,
        encoding: str = "utf-8",
        recursive: bool = False,
        append: bool = False,
        pattern: str | None = None,
        max_lines: int | None = None,
    ) -> str:
        """Execute a file operation.

        Args:
            operation: Operation to perform
            path: Primary path for the operation
            content: Content for write operations
            destination: Destination for move/copy
            encoding: File encoding
            recursive: Recursive flag for list/delete
            append: Append mode for write
            pattern: Glob pattern for list
            max_lines: Maximum lines to read

        Returns:
            Result message
        """
        self.logger.info(f"File operation: {operation} on {path}")

        try:
            if operation == "read":
                return self._read_file(path, encoding, max_lines)
            elif operation == "write":
                if content is None:
                    return str(ToolResult(False, "", "Content required for write operation"))
                return self._write_file(path, content, encoding, append)
            elif operation == "list":
                return self._list_directory(path, recursive, pattern)
            elif operation == "delete":
                return self._delete_path(path, recursive)
            elif operation == "move":
                if destination is None:
                    return str(ToolResult(False, "", "Destination required for move operation"))
                return self._move_path(path, destination)
            elif operation == "copy":
                if destination is None:
                    return str(ToolResult(False, "", "Destination required for copy operation"))
                return self._copy_path(path, destination)
            elif operation == "exists":
                return self._check_exists(path)
            elif operation == "info":
                return self._get_info(path)
            else:
                return str(ToolResult(False, "", f"Unknown operation: {operation}"))
        except ValueError as e:
            self.logger.error(f"Path validation error: {e}")
            return str(ToolResult(False, "", str(e)))
        except Exception as e:
            self.logger.error(f"File operation error: {e}")
            return str(ToolResult(False, "", f"Operation failed: {str(e)}"))

    def _read_file(self, path: str, encoding: str, max_lines: int | None) -> str:
        """Read contents of a file."""
        validated_path = self.validate_path(path)

        if not validated_path.exists():
            return str(ToolResult(False, "", f"File not found: {path}"))

        if not validated_path.is_file():
            return str(ToolResult(False, "", f"Path is not a file: {path}"))

        try:
            with open(validated_path, encoding=encoding) as f:
                if max_lines is not None:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    content = "".join(lines)
                    if i >= max_lines:
                        content += f"\n... (truncated at {max_lines} lines)"
                else:
                    content = f.read()

            size = validated_path.stat().st_size
            return str(
                ToolResult(
                    True,
                    content,
                    data={
                        "path": path,
                        "size": size,
                        "size_formatted": format_file_size(size),
                    },
                )
            )
        except UnicodeDecodeError as e:
            return str(ToolResult(False, "", f"Encoding error reading {path}: {e}"))

    def _write_file(self, path: str, content: str, encoding: str, append: bool) -> str:
        """Write content to a file."""
        validated_path = self.validate_path(path)

        # Create parent directories if needed
        validated_path.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        action = "Appended to" if append else "Wrote"

        try:
            with open(validated_path, mode=mode, encoding=encoding) as f:
                f.write(content)

            size = validated_path.stat().st_size
            return str(
                ToolResult(
                    True,
                    f"{action} {len(content)} characters to {path}",
                    data={
                        "path": path,
                        "characters_written": len(content),
                        "size": size,
                        "size_formatted": format_file_size(size),
                    },
                )
            )
        except Exception as e:
            return str(ToolResult(False, "", f"Failed to write file: {e}"))

    def _list_directory(self, path: str, recursive: bool, pattern: str | None) -> str:
        """List contents of a directory."""
        validated_path = self.validate_path(path)

        if not validated_path.exists():
            return str(ToolResult(False, "", f"Directory not found: {path}"))

        if not validated_path.is_dir():
            return str(ToolResult(False, "", f"Path is not a directory: {path}"))

        try:
            entries: list[dict[str, Any]] = []

            if pattern:
                # Use glob pattern
                if recursive:
                    files = validated_path.rglob(pattern)
                else:
                    files = validated_path.glob(pattern)
            else:
                # List all contents
                if recursive:
                    files = validated_path.rglob("*")
                else:
                    files = validated_path.iterdir()

            for item in sorted(files):
                rel_path = self.get_relative_path(item)
                is_dir = item.is_dir()

                entry = {
                    "name": item.name,
                    "path": rel_path,
                    "type": "directory" if is_dir else "file",
                }

                if not is_dir:
                    try:
                        stat = item.stat()
                        entry["size"] = stat.st_size
                        entry["size_formatted"] = format_file_size(stat.st_size)
                    except OSError:
                        entry["size"] = 0

                entries.append(entry)

            # Format output
            output_lines = [f"Contents of {path}:", ""]
            for entry in entries:
                prefix = "[DIR] " if entry["type"] == "directory" else "      "
                size_str = entry.get("size_formatted", "")
                output_lines.append(f"{prefix}{entry['path']:<50} {size_str}")

            output_lines.append("")
            output_lines.append(f"Total: {len(entries)} items")

            return str(
                ToolResult(
                    True,
                    "\n".join(output_lines),
                    data={"path": path, "count": len(entries), "entries": entries},
                )
            )
        except Exception as e:
            return str(ToolResult(False, "", f"Failed to list directory: {e}"))

    def _delete_path(self, path: str, recursive: bool) -> str:
        """Delete a file or directory."""
        validated_path = self.validate_path(path)

        if not validated_path.exists():
            return str(ToolResult(False, "", f"Path not found: {path}"))

        try:
            if validated_path.is_file():
                validated_path.unlink()
                return str(ToolResult(True, f"Deleted file: {path}"))
            elif validated_path.is_dir():
                if recursive:
                    shutil.rmtree(validated_path)
                    return str(ToolResult(True, f"Deleted directory and contents: {path}"))
                else:
                    # Try to remove empty directory
                    try:
                        validated_path.rmdir()
                        return str(ToolResult(True, f"Deleted empty directory: {path}"))
                    except OSError:
                        return str(
                            ToolResult(
                                False,
                                "",
                                f"Directory not empty. Use recursive=true to delete: {path}",
                            )
                        )
            else:
                return str(ToolResult(False, "", f"Unknown path type: {path}"))
        except Exception as e:
            return str(ToolResult(False, "", f"Failed to delete: {e}"))

    def _move_path(self, source: str, destination: str) -> str:
        """Move or rename a file/directory."""
        src_path = self.validate_path(source)
        dst_path = self.validate_path(destination)

        if not src_path.exists():
            return str(ToolResult(False, "", f"Source not found: {source}"))

        try:
            # Create destination parent directories
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(src_path), str(dst_path))
            return str(
                ToolResult(
                    True,
                    f"Moved {source} to {destination}",
                    data={"source": source, "destination": destination},
                )
            )
        except Exception as e:
            return str(ToolResult(False, "", f"Failed to move: {e}"))

    def _copy_path(self, source: str, destination: str) -> str:
        """Copy a file or directory."""
        src_path = self.validate_path(source)
        dst_path = self.validate_path(destination)

        if not src_path.exists():
            return str(ToolResult(False, "", f"Source not found: {source}"))

        try:
            # Create destination parent directories
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if src_path.is_file():
                shutil.copy2(str(src_path), str(dst_path))
                return str(
                    ToolResult(
                        True,
                        f"Copied file {source} to {destination}",
                        data={"source": source, "destination": destination},
                    )
                )
            elif src_path.is_dir():
                shutil.copytree(str(src_path), str(dst_path))
                return str(
                    ToolResult(
                        True,
                        f"Copied directory {source} to {destination}",
                        data={"source": source, "destination": destination},
                    )
                )
            else:
                return str(ToolResult(False, "", f"Unknown path type: {source}"))
        except Exception as e:
            return str(ToolResult(False, "", f"Failed to copy: {e}"))

    def _check_exists(self, path: str) -> str:
        """Check if a path exists."""
        try:
            validated_path = self.validate_path(path)
            exists = validated_path.exists()
            path_type = None
            if exists:
                if validated_path.is_file():
                    path_type = "file"
                elif validated_path.is_dir():
                    path_type = "directory"
                else:
                    path_type = "other"

            return str(
                ToolResult(
                    True,
                    f"Path '{path}' {'exists' if exists else 'does not exist'}"
                    + (f" (type: {path_type})" if path_type else ""),
                    data={"path": path, "exists": exists, "type": path_type},
                )
            )
        except ValueError:
            # Path outside project directory
            return str(
                ToolResult(
                    True,
                    f"Path '{path}' is outside project directory",
                    data={"path": path, "exists": False, "error": "outside_project"},
                )
            )

    def _get_info(self, path: str) -> str:
        """Get detailed information about a path."""
        validated_path = self.validate_path(path)

        if not validated_path.exists():
            return str(ToolResult(False, "", f"Path not found: {path}"))

        try:
            stat = validated_path.stat()
            is_dir = validated_path.is_dir()

            info = {
                "path": path,
                "absolute_path": str(validated_path),
                "type": "directory" if is_dir else "file",
                "size": stat.st_size,
                "size_formatted": format_file_size(stat.st_size),
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "accessed": stat.st_atime,
            }

            if not is_dir:
                info["extension"] = validated_path.suffix

            # Count contents if directory
            if is_dir:
                files = list(validated_path.iterdir())
                info["num_items"] = len(files)
                info["num_files"] = sum(1 for f in files if f.is_file())
                info["num_dirs"] = sum(1 for f in files if f.is_dir())

            output_lines = [
                f"Information for: {path}",
                f"  Type: {info['type']}",
                f"  Size: {info['size_formatted']}",
            ]

            if is_dir:
                output_lines.append(f"  Contents: {info['num_files']} files, {info['num_dirs']} directories")
            else:
                output_lines.append(f"  Extension: {info.get('extension', 'none')}")

            return str(ToolResult(True, "\n".join(output_lines), data=info))
        except Exception as e:
            return str(ToolResult(False, "", f"Failed to get info: {e}"))

    async def _arun(
        self,
        operation: str,
        path: str,
        content: str | None = None,
        destination: str | None = None,
        encoding: str = "utf-8",
        recursive: bool = False,
        append: bool = False,
        pattern: str | None = None,
        max_lines: int | None = None,
    ) -> str:
        """Async version of file operations."""
        # File operations are generally fast enough to run synchronously
        return self._run(
            operation=operation,
            path=path,
            content=content,
            destination=destination,
            encoding=encoding,
            recursive=recursive,
            append=append,
            pattern=pattern,
            max_lines=max_lines,
        )
