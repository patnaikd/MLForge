"""Tests for the todo list tool."""

import pytest
from pathlib import Path

from src.database.connection import Database
from src.tools.todo_list import TodoListTool, TaskPlannerTool


@pytest.fixture
def project_dir(temp_dir: Path) -> Path:
    """Create a project directory for testing."""
    project = temp_dir / "test_project"
    project.mkdir(parents=True)
    return project


@pytest.fixture
def test_database(temp_dir: Path) -> Database:
    """Create a test database."""
    db_path = temp_dir / "test.db"
    return Database(db_path)


@pytest.fixture
def todo_tool(project_dir: Path, test_database: Database) -> TodoListTool:
    """Create a todo list tool for testing."""
    # Patch the database getter
    tool = TodoListTool(
        project_path=project_dir,
        project_id="test-project-id",
        conversation_id="test-conversation-id",
    )
    tool._db = test_database
    return tool


@pytest.fixture
def planner_tool(project_dir: Path, test_database: Database) -> TaskPlannerTool:
    """Create a task planner tool for testing."""
    tool = TaskPlannerTool(
        project_path=project_dir,
        project_id="test-project-id",
        conversation_id="test-conversation-id",
    )
    tool._db = test_database
    return tool


class TestTodoListAdd:
    """Tests for adding todos."""

    def test_add_task(self, todo_tool: TodoListTool):
        """Test adding a new task."""
        result = todo_tool._run(action="add", task="Test task")
        assert "Added task" in result
        assert "Test task" in result

    def test_add_task_without_description_fails(self, todo_tool: TodoListTool):
        """Test that adding without description fails."""
        result = todo_tool._run(action="add")
        assert "Error" in result or "required" in result.lower()

    def test_add_multiple_tasks(self, todo_tool: TodoListTool):
        """Test adding multiple tasks."""
        todo_tool._run(action="add", task="Task 1")
        todo_tool._run(action="add", task="Task 2")
        todo_tool._run(action="add", task="Task 3")

        result = todo_tool._run(action="list")
        assert "Task 1" in result
        assert "Task 2" in result
        assert "Task 3" in result


class TestTodoListList:
    """Tests for listing todos."""

    def test_list_empty(self, todo_tool: TodoListTool):
        """Test listing when empty."""
        result = todo_tool._run(action="list")
        assert "No tasks found" in result or "0" in result

    def test_list_all(self, todo_tool: TodoListTool):
        """Test listing all tasks."""
        todo_tool._run(action="add", task="Task A")
        todo_tool._run(action="add", task="Task B")

        result = todo_tool._run(action="list")
        assert "Task A" in result
        assert "Task B" in result

    def test_list_filter_pending(self, todo_tool: TodoListTool):
        """Test filtering by pending status."""
        todo_tool._run(action="add", task="Pending task")
        result_add = todo_tool._run(action="add", task="To complete")

        # Extract the todo_id from the result
        import re
        match = re.search(r'"todo_id":\s*"([^"]+)"', result_add)
        if match:
            todo_id = match.group(1)
            todo_tool._run(action="complete", todo_id=todo_id)

        result = todo_tool._run(action="list", filter_status="pending")
        assert "Pending task" in result
        # Completed task should not appear
        assert "To complete" not in result or "completed" in result.lower()

    def test_list_shows_status_counts(self, todo_tool: TodoListTool):
        """Test that list shows status counts."""
        todo_tool._run(action="add", task="Task 1")
        todo_tool._run(action="add", task="Task 2")

        result = todo_tool._run(action="list")
        assert "pending" in result.lower()


class TestTodoListUpdate:
    """Tests for updating todos."""

    def test_update_status(self, todo_tool: TodoListTool):
        """Test updating task status."""
        add_result = todo_tool._run(action="add", task="Update me")

        # Extract todo_id
        import re
        match = re.search(r'"todo_id":\s*"([^"]+)"', add_result)
        assert match, "Could not find todo_id in result"
        todo_id = match.group(1)

        result = todo_tool._run(action="update", todo_id=todo_id, status="in_progress")
        assert "in_progress" in result.lower()

    def test_update_to_completed(self, todo_tool: TodoListTool):
        """Test updating status to completed."""
        add_result = todo_tool._run(action="add", task="Complete me")

        import re
        match = re.search(r'"todo_id":\s*"([^"]+)"', add_result)
        todo_id = match.group(1)

        result = todo_tool._run(action="update", todo_id=todo_id, status="completed")
        assert "completed" in result.lower()

    def test_update_with_prefix(self, todo_tool: TodoListTool):
        """Test updating using ID prefix."""
        add_result = todo_tool._run(action="add", task="Prefix test")

        import re
        match = re.search(r'"todo_id":\s*"([^"]+)"', add_result)
        full_id = match.group(1)
        prefix = full_id[:8]

        result = todo_tool._run(action="update", todo_id=prefix, status="in_progress")
        assert "in_progress" in result.lower()

    def test_update_nonexistent_fails(self, todo_tool: TodoListTool):
        """Test updating nonexistent todo fails."""
        result = todo_tool._run(action="update", todo_id="nonexistent", status="completed")
        assert "Error" in result or "not found" in result.lower()


class TestTodoListComplete:
    """Tests for completing todos."""

    def test_complete_task(self, todo_tool: TodoListTool):
        """Test marking task as complete."""
        add_result = todo_tool._run(action="add", task="Complete this")

        import re
        match = re.search(r'"todo_id":\s*"([^"]+)"', add_result)
        todo_id = match.group(1)

        result = todo_tool._run(action="complete", todo_id=todo_id)
        assert "completed" in result.lower()

    def test_complete_sets_timestamp(self, todo_tool: TodoListTool, test_database: Database):
        """Test that completing sets completed_at timestamp."""
        add_result = todo_tool._run(action="add", task="Timestamp test")

        import re
        match = re.search(r'"todo_id":\s*"([^"]+)"', add_result)
        todo_id = match.group(1)

        todo_tool._run(action="complete", todo_id=todo_id)

        # Check database
        todos = test_database.list_todos("test-project-id")
        completed_todo = next((t for t in todos if t.id == todo_id), None)
        assert completed_todo is not None
        assert completed_todo.completed_at is not None


class TestTodoListDelete:
    """Tests for deleting todos."""

    def test_delete_task(self, todo_tool: TodoListTool):
        """Test deleting a task."""
        add_result = todo_tool._run(action="add", task="Delete me")

        import re
        match = re.search(r'"todo_id":\s*"([^"]+)"', add_result)
        todo_id = match.group(1)

        result = todo_tool._run(action="delete", todo_id=todo_id)
        assert "Deleted" in result

        # Verify deleted
        list_result = todo_tool._run(action="list")
        assert "Delete me" not in list_result

    def test_delete_nonexistent_fails(self, todo_tool: TodoListTool):
        """Test deleting nonexistent todo fails."""
        result = todo_tool._run(action="delete", todo_id="nonexistent")
        assert "Error" in result or "not found" in result.lower()


class TestTodoListClear:
    """Tests for clearing completed todos."""

    def test_clear_completed(self, todo_tool: TodoListTool):
        """Test clearing completed tasks."""
        # Add and complete a task
        add_result = todo_tool._run(action="add", task="To clear")
        import re
        match = re.search(r'"todo_id":\s*"([^"]+)"', add_result)
        todo_id = match.group(1)
        todo_tool._run(action="complete", todo_id=todo_id)

        # Add a pending task
        todo_tool._run(action="add", task="Keep this")

        # Clear completed
        result = todo_tool._run(action="clear")
        assert "Cleared" in result

        # Verify only pending remains
        list_result = todo_tool._run(action="list")
        assert "Keep this" in list_result
        assert "To clear" not in list_result

    def test_clear_empty(self, todo_tool: TodoListTool):
        """Test clearing when no completed tasks."""
        result = todo_tool._run(action="clear")
        assert "No completed" in result or "0" in result


class TestTaskPlanner:
    """Tests for the task planner tool."""

    def test_create_plan(self, planner_tool: TaskPlannerTool):
        """Test creating a plan with steps."""
        result = planner_tool._run(
            plan_description="Test plan",
            steps=["Step 1", "Step 2", "Step 3"],
        )
        assert "Created plan" in result
        assert "Step 1" in result
        assert "Step 2" in result
        assert "Step 3" in result

    def test_plan_creates_todos(self, planner_tool: TaskPlannerTool, test_database: Database):
        """Test that plan creates todo entries."""
        planner_tool._run(
            plan_description="Database plan",
            steps=["First step", "Second step"],
        )

        todos = test_database.list_todos("test-project-id")
        assert len(todos) == 2
        assert any("First step" in t.task for t in todos)
        assert any("Second step" in t.task for t in todos)

    def test_plan_empty_steps_fails(self, planner_tool: TaskPlannerTool):
        """Test that empty steps list fails."""
        result = planner_tool._run(
            plan_description="Empty plan",
            steps=[],
        )
        assert "Error" in result or "No steps" in result


class TestTodoListAsync:
    """Tests for async execution."""

    @pytest.mark.asyncio
    async def test_async_add(self, todo_tool: TodoListTool):
        """Test async add operation."""
        result = await todo_tool._arun(action="add", task="Async task")
        assert "Added task" in result

    @pytest.mark.asyncio
    async def test_async_list(self, todo_tool: TodoListTool):
        """Test async list operation."""
        await todo_tool._arun(action="add", task="Async list test")
        result = await todo_tool._arun(action="list")
        assert "Async list test" in result
