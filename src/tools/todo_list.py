"""Todo list tool for agent task tracking."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.database.models import AgentTodo
from src.tools.base import BaseAgentTool, ToolResult


class TodoInput(BaseModel):
    """Input schema for todo list operations."""

    action: Literal["add", "list", "update", "complete", "delete", "clear"] = Field(
        description="Action to perform on the todo list"
    )
    task: str | None = Field(
        default=None,
        description="Task description (required for 'add' action)",
    )
    todo_id: str | None = Field(
        default=None,
        description="Todo ID (required for 'update', 'complete', 'delete' actions)",
    )
    status: Literal["pending", "in_progress", "completed"] | None = Field(
        default=None,
        description="New status (for 'update' action)",
    )
    filter_status: Literal["pending", "in_progress", "completed", "all"] | None = Field(
        default="all",
        description="Filter todos by status (for 'list' action)",
    )


class TodoListTool(BaseAgentTool):
    """Tool for managing agent task tracking with a todo list.

    Allows the agent to:
    - Track tasks it needs to complete
    - Update progress on tasks
    - Mark tasks as complete
    - View pending work

    Todo items are persisted in the database and associated with the
    current project and conversation.
    """

    name: str = "todo_list"
    description: str = """Manage a task list to track work items.

Actions:
- add: Add a new task to the list
- list: View current tasks (optionally filtered by status)
- update: Update task status (pending, in_progress, completed)
- complete: Mark a task as completed
- delete: Remove a task from the list
- clear: Remove all completed tasks

Example usage:
- Add task: {"action": "add", "task": "Load and explore dataset"}
- List pending: {"action": "list", "filter_status": "pending"}
- Start task: {"action": "update", "todo_id": "abc123", "status": "in_progress"}
- Complete task: {"action": "complete", "todo_id": "abc123"}

Use this tool to:
1. Break down complex tasks into smaller steps
2. Track progress through multi-step workflows
3. Ensure all required steps are completed
4. Communicate progress to the user
"""
    args_schema: type[BaseModel] = TodoInput

    def _run(
        self,
        action: str,
        task: str | None = None,
        todo_id: str | None = None,
        status: str | None = None,
        filter_status: str | None = "all",
    ) -> str:
        """Execute a todo list operation.

        Args:
            action: Action to perform
            task: Task description for add
            todo_id: Todo ID for update/complete/delete
            status: New status for update
            filter_status: Status filter for list

        Returns:
            Operation result
        """
        self.logger.info(f"Todo list action: {action}")

        if self.project_id is None:
            return str(ToolResult(False, "", "Project ID not set - cannot manage todos"))

        try:
            if action == "add":
                return self._add_task(task)
            elif action == "list":
                return self._list_tasks(filter_status)
            elif action == "update":
                return self._update_task(todo_id, status)
            elif action == "complete":
                return self._complete_task(todo_id)
            elif action == "delete":
                return self._delete_task(todo_id)
            elif action == "clear":
                return self._clear_completed()
            else:
                return str(ToolResult(False, "", f"Unknown action: {action}"))
        except Exception as e:
            self.logger.error(f"Todo operation error: {e}")
            return str(ToolResult(False, "", f"Operation failed: {str(e)}"))

    def _add_task(self, task: str | None) -> str:
        """Add a new task to the todo list."""
        if not task:
            return str(ToolResult(False, "", "Task description is required"))

        todo = AgentTodo(
            project_id=self.project_id,
            conversation_id=self.conversation_id,
            task=task,
            status="pending",
        )

        created = self.db.create_todo(todo)

        return str(
            ToolResult(
                True,
                f"Added task: {task}",
                data={
                    "todo_id": created.id,
                    "task": task,
                    "status": "pending",
                },
            )
        )

    def _list_tasks(self, filter_status: str | None) -> str:
        """List tasks in the todo list."""
        todos = self.db.list_todos(self.project_id)

        # Filter by status if specified
        if filter_status and filter_status != "all":
            todos = [t for t in todos if t.status == filter_status]

        if not todos:
            status_msg = f" with status '{filter_status}'" if filter_status != "all" else ""
            return str(
                ToolResult(
                    True,
                    f"No tasks found{status_msg}",
                    data={"todos": [], "count": 0},
                )
            )

        # Group by status
        pending = [t for t in todos if t.status == "pending"]
        in_progress = [t for t in todos if t.status == "in_progress"]
        completed = [t for t in todos if t.status == "completed"]

        output_lines = ["=== TODO LIST ===", ""]

        if in_progress:
            output_lines.append("🔄 IN PROGRESS:")
            for todo in in_progress:
                output_lines.append(f"  [{todo.id[:8]}] {todo.task}")
            output_lines.append("")

        if pending:
            output_lines.append("⏳ PENDING:")
            for todo in pending:
                output_lines.append(f"  [{todo.id[:8]}] {todo.task}")
            output_lines.append("")

        if completed:
            output_lines.append("✅ COMPLETED:")
            for todo in completed:
                completed_time = ""
                if todo.completed_at:
                    completed_time = f" (completed: {todo.completed_at.strftime('%Y-%m-%d %H:%M')})"
                output_lines.append(f"  [{todo.id[:8]}] {todo.task}{completed_time}")
            output_lines.append("")

        # Summary
        output_lines.append(f"Total: {len(todos)} tasks ({len(pending)} pending, {len(in_progress)} in progress, {len(completed)} completed)")

        return str(
            ToolResult(
                True,
                "\n".join(output_lines),
                data={
                    "todos": [
                        {
                            "id": t.id,
                            "task": t.task,
                            "status": t.status,
                            "created_at": t.created_at.isoformat(),
                            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                        }
                        for t in todos
                    ],
                    "count": len(todos),
                    "pending": len(pending),
                    "in_progress": len(in_progress),
                    "completed": len(completed),
                },
            )
        )

    def _update_task(self, todo_id: str | None, status: str | None) -> str:
        """Update a task's status."""
        if not todo_id:
            return str(ToolResult(False, "", "Todo ID is required"))
        if not status:
            return str(ToolResult(False, "", "New status is required"))

        # Find the todo (may need to search by prefix)
        todos = self.db.list_todos(self.project_id)
        matching = [t for t in todos if t.id == todo_id or t.id.startswith(todo_id)]

        if not matching:
            return str(ToolResult(False, "", f"Todo not found: {todo_id}"))
        if len(matching) > 1:
            return str(
                ToolResult(
                    False,
                    "",
                    f"Ambiguous todo ID. Matches: {[t.id[:8] for t in matching]}",
                )
            )

        todo = matching[0]
        old_status = todo.status
        todo.status = status

        if status == "completed" and not todo.completed_at:
            todo.completed_at = datetime.now()

        self.db.update_todo(todo)

        return str(
            ToolResult(
                True,
                f"Updated task status: {old_status} → {status}",
                data={
                    "todo_id": todo.id,
                    "task": todo.task,
                    "old_status": old_status,
                    "new_status": status,
                },
            )
        )

    def _complete_task(self, todo_id: str | None) -> str:
        """Mark a task as completed."""
        return self._update_task(todo_id, "completed")

    def _delete_task(self, todo_id: str | None) -> str:
        """Delete a task from the list."""
        if not todo_id:
            return str(ToolResult(False, "", "Todo ID is required"))

        # Find the todo
        todos = self.db.list_todos(self.project_id)
        matching = [t for t in todos if t.id == todo_id or t.id.startswith(todo_id)]

        if not matching:
            return str(ToolResult(False, "", f"Todo not found: {todo_id}"))
        if len(matching) > 1:
            return str(
                ToolResult(
                    False,
                    "",
                    f"Ambiguous todo ID. Matches: {[t.id[:8] for t in matching]}",
                )
            )

        todo = matching[0]

        # Delete from database
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM agent_todos WHERE id = ?", (todo.id,))

        return str(
            ToolResult(
                True,
                f"Deleted task: {todo.task}",
                data={"todo_id": todo.id, "task": todo.task},
            )
        )

    def _clear_completed(self) -> str:
        """Remove all completed tasks."""
        todos = self.db.list_todos(self.project_id)
        completed = [t for t in todos if t.status == "completed"]

        if not completed:
            return str(ToolResult(True, "No completed tasks to clear"))

        # Delete completed todos
        with self.db.get_connection() as conn:
            for todo in completed:
                conn.execute("DELETE FROM agent_todos WHERE id = ?", (todo.id,))

        return str(
            ToolResult(
                True,
                f"Cleared {len(completed)} completed tasks",
                data={"cleared_count": len(completed)},
            )
        )

    async def _arun(
        self,
        action: str,
        task: str | None = None,
        todo_id: str | None = None,
        status: str | None = None,
        filter_status: str | None = "all",
    ) -> str:
        """Async version of todo list operations."""
        # Database operations are synchronous, so just call sync version
        return self._run(
            action=action,
            task=task,
            todo_id=todo_id,
            status=status,
            filter_status=filter_status,
        )


class TaskPlannerTool(BaseAgentTool):
    """Tool for creating structured task plans.

    Higher-level tool that creates multiple todos from a plan description.
    """

    name: str = "task_planner"
    description: str = """Create a structured plan with multiple tasks.

Use this to break down a complex request into discrete steps that can be tracked.

Example usage:
{"plan_description": "Perform EDA on dataset", "steps": ["Load data", "Check data types", "Handle missing values", "Generate summary statistics", "Create visualizations"]}
"""

    def _run(
        self,
        plan_description: str,
        steps: list[str],
    ) -> str:
        """Create a task plan with multiple todos.

        Args:
            plan_description: Overall plan description
            steps: List of step descriptions

        Returns:
            Plan creation result
        """
        self.logger.info(f"Creating task plan: {plan_description}")

        if self.project_id is None:
            return str(ToolResult(False, "", "Project ID not set"))

        if not steps:
            return str(ToolResult(False, "", "No steps provided"))

        created_todos = []

        try:
            for i, step in enumerate(steps, 1):
                todo = AgentTodo(
                    project_id=self.project_id,
                    conversation_id=self.conversation_id,
                    task=f"Step {i}: {step}",
                    status="pending",
                )
                created = self.db.create_todo(todo)
                created_todos.append({
                    "id": created.id,
                    "step": i,
                    "task": step,
                })

            output_lines = [
                f"Created plan: {plan_description}",
                "",
                "Steps:",
            ]

            for todo in created_todos:
                output_lines.append(f"  {todo['step']}. [{todo['id'][:8]}] {todo['task']}")

            return str(
                ToolResult(
                    True,
                    "\n".join(output_lines),
                    data={
                        "plan": plan_description,
                        "steps": created_todos,
                        "count": len(created_todos),
                    },
                )
            )

        except Exception as e:
            self.logger.error(f"Plan creation error: {e}")
            return str(ToolResult(False, "", f"Failed to create plan: {str(e)}"))

    async def _arun(
        self,
        plan_description: str,
        steps: list[str],
    ) -> str:
        """Async version."""
        return self._run(plan_description, steps)
