"""Tests for the file operations tool."""

import pytest
from pathlib import Path

from src.tools.file_operations import FileOperationsTool


@pytest.fixture
def project_dir(temp_dir: Path) -> Path:
    """Create a project directory with test files."""
    project = temp_dir / "test_project"
    project.mkdir(parents=True)

    # Create subdirectories
    (project / "data").mkdir()
    (project / "code").mkdir()
    (project / "outputs").mkdir()

    # Create test files
    (project / "data" / "input.csv").write_text("col1,col2\n1,2\n3,4\n")
    (project / "data" / "config.json").write_text('{"key": "value"}')
    (project / "code" / "script.py").write_text("print('hello')")

    return project


@pytest.fixture
def file_tool(project_dir: Path) -> FileOperationsTool:
    """Create a file operations tool for testing."""
    return FileOperationsTool(
        project_path=project_dir,
        project_id="test-project-id",
    )


class TestFileOperationsRead:
    """Tests for file read operations."""

    def test_read_existing_file(self, file_tool: FileOperationsTool):
        """Test reading an existing file."""
        result = file_tool._run(operation="read", path="data/input.csv")
        assert "col1,col2" in result
        assert "1,2" in result

    def test_read_nonexistent_file(self, file_tool: FileOperationsTool):
        """Test reading a file that doesn't exist."""
        result = file_tool._run(operation="read", path="nonexistent.txt")
        assert "Error" in result or "not found" in result.lower()

    def test_read_with_max_lines(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test reading with line limit."""
        # Create file with many lines
        lines = "\n".join(f"line {i}" for i in range(100))
        (project_dir / "multiline.txt").write_text(lines)

        result = file_tool._run(operation="read", path="multiline.txt", max_lines=5)
        assert "line 0" in result
        assert "line 4" in result
        assert "truncated" in result.lower()

    def test_read_directory_fails(self, file_tool: FileOperationsTool):
        """Test that reading a directory fails."""
        result = file_tool._run(operation="read", path="data")
        assert "Error" in result or "not a file" in result.lower()


class TestFileOperationsWrite:
    """Tests for file write operations."""

    def test_write_new_file(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test writing a new file."""
        result = file_tool._run(
            operation="write",
            path="outputs/result.txt",
            content="test content",
        )
        assert "Wrote" in result
        assert (project_dir / "outputs" / "result.txt").read_text() == "test content"

    def test_write_creates_directories(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test that write creates parent directories."""
        result = file_tool._run(
            operation="write",
            path="new/nested/dir/file.txt",
            content="nested content",
        )
        assert "Wrote" in result
        assert (project_dir / "new" / "nested" / "dir" / "file.txt").read_text() == "nested content"

    def test_write_append(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test appending to a file."""
        file_tool._run(operation="write", path="outputs/append.txt", content="line1\n")
        file_tool._run(operation="write", path="outputs/append.txt", content="line2\n", append=True)

        content = (project_dir / "outputs" / "append.txt").read_text()
        assert "line1" in content
        assert "line2" in content

    def test_write_overwrites(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test that write overwrites existing content."""
        file_tool._run(operation="write", path="outputs/overwrite.txt", content="original")
        file_tool._run(operation="write", path="outputs/overwrite.txt", content="new content")

        content = (project_dir / "outputs" / "overwrite.txt").read_text()
        assert content == "new content"


class TestFileOperationsList:
    """Tests for directory listing operations."""

    def test_list_directory(self, file_tool: FileOperationsTool):
        """Test listing a directory."""
        result = file_tool._run(operation="list", path="data")
        assert "input.csv" in result
        assert "config.json" in result

    def test_list_recursive(self, file_tool: FileOperationsTool):
        """Test recursive directory listing."""
        result = file_tool._run(operation="list", path=".", recursive=True)
        assert "data" in result
        assert "code" in result
        assert "input.csv" in result
        assert "script.py" in result

    def test_list_with_pattern(self, file_tool: FileOperationsTool):
        """Test listing with glob pattern."""
        result = file_tool._run(operation="list", path=".", pattern="*.csv", recursive=True)
        assert "input.csv" in result
        assert "config.json" not in result

    def test_list_nonexistent_directory(self, file_tool: FileOperationsTool):
        """Test listing a nonexistent directory."""
        result = file_tool._run(operation="list", path="nonexistent")
        assert "Error" in result or "not found" in result.lower()


class TestFileOperationsDelete:
    """Tests for file deletion operations."""

    def test_delete_file(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test deleting a file."""
        test_file = project_dir / "to_delete.txt"
        test_file.write_text("delete me")

        result = file_tool._run(operation="delete", path="to_delete.txt")
        assert "Deleted" in result
        assert not test_file.exists()

    def test_delete_empty_directory(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test deleting an empty directory."""
        empty_dir = project_dir / "empty"
        empty_dir.mkdir()

        result = file_tool._run(operation="delete", path="empty")
        assert "Deleted" in result
        assert not empty_dir.exists()

    def test_delete_nonempty_directory_fails(self, file_tool: FileOperationsTool):
        """Test that deleting non-empty directory fails without recursive."""
        result = file_tool._run(operation="delete", path="data")
        assert "Error" in result or "not empty" in result.lower()

    def test_delete_recursive(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test recursive directory deletion."""
        result = file_tool._run(operation="delete", path="data", recursive=True)
        assert "Deleted" in result
        assert not (project_dir / "data").exists()


class TestFileOperationsMove:
    """Tests for file move operations."""

    def test_move_file(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test moving a file."""
        result = file_tool._run(
            operation="move",
            path="code/script.py",
            destination="outputs/moved_script.py",
        )
        assert "Moved" in result
        assert not (project_dir / "code" / "script.py").exists()
        assert (project_dir / "outputs" / "moved_script.py").exists()

    def test_move_rename(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test renaming a file."""
        result = file_tool._run(
            operation="move",
            path="data/input.csv",
            destination="data/renamed.csv",
        )
        assert "Moved" in result
        assert (project_dir / "data" / "renamed.csv").exists()

    def test_move_creates_destination_directory(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test that move creates destination directory."""
        (project_dir / "moveme.txt").write_text("move me")

        result = file_tool._run(
            operation="move",
            path="moveme.txt",
            destination="newdir/moved.txt",
        )
        assert "Moved" in result
        assert (project_dir / "newdir" / "moved.txt").exists()


class TestFileOperationsCopy:
    """Tests for file copy operations."""

    def test_copy_file(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test copying a file."""
        result = file_tool._run(
            operation="copy",
            path="data/input.csv",
            destination="outputs/copied.csv",
        )
        assert "Copied" in result
        assert (project_dir / "data" / "input.csv").exists()  # Original still exists
        assert (project_dir / "outputs" / "copied.csv").exists()

    def test_copy_preserves_content(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test that copy preserves file content."""
        file_tool._run(
            operation="copy",
            path="data/input.csv",
            destination="outputs/copied.csv",
        )

        original = (project_dir / "data" / "input.csv").read_text()
        copied = (project_dir / "outputs" / "copied.csv").read_text()
        assert original == copied


class TestFileOperationsExists:
    """Tests for path existence checks."""

    def test_exists_file(self, file_tool: FileOperationsTool):
        """Test checking if file exists."""
        result = file_tool._run(operation="exists", path="data/input.csv")
        assert "exists" in result.lower()
        assert "file" in result.lower()

    def test_exists_directory(self, file_tool: FileOperationsTool):
        """Test checking if directory exists."""
        result = file_tool._run(operation="exists", path="data")
        assert "exists" in result.lower()
        assert "directory" in result.lower()

    def test_not_exists(self, file_tool: FileOperationsTool):
        """Test checking nonexistent path."""
        result = file_tool._run(operation="exists", path="nonexistent")
        assert "does not exist" in result.lower()


class TestFileOperationsInfo:
    """Tests for file info operations."""

    def test_info_file(self, file_tool: FileOperationsTool):
        """Test getting file info."""
        result = file_tool._run(operation="info", path="data/input.csv")
        assert "file" in result.lower()
        assert "size" in result.lower()

    def test_info_directory(self, file_tool: FileOperationsTool):
        """Test getting directory info."""
        result = file_tool._run(operation="info", path="data")
        assert "directory" in result.lower()
        assert "files" in result.lower() or "items" in result.lower()


class TestFileOperationsPathSecurity:
    """Tests for path security (preventing directory traversal)."""

    def test_rejects_parent_traversal(self, file_tool: FileOperationsTool):
        """Test that parent directory traversal is rejected."""
        result = file_tool._run(operation="read", path="../../../etc/passwd")
        assert "Error" in result or "outside" in result.lower()

    def test_rejects_absolute_path_outside_project(self, file_tool: FileOperationsTool):
        """Test that absolute paths outside project are rejected."""
        result = file_tool._run(operation="read", path="/etc/passwd")
        assert "Error" in result or "outside" in result.lower()

    def test_allows_absolute_path_inside_project(self, file_tool: FileOperationsTool, project_dir: Path):
        """Test that absolute paths inside project work."""
        absolute_path = str(project_dir / "data" / "input.csv")
        result = file_tool._run(operation="read", path=absolute_path)
        # This should work - it's inside the project
        assert "col1,col2" in result
