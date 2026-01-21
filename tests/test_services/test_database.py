"""Tests for database operations."""

from datetime import datetime

import pytest

from src.database.connection import Database
from src.database.models import (
    AgentTodo,
    Conversation,
    DocumentBlock,
    Job,
    Project,
)


class TestDatabase:
    """Test cases for Database operations."""

    def test_create_and_get_project(self, test_db: Database):
        """Test creating and retrieving a project."""
        project = Project(
            name="Test Project",
            folder_path="/tmp/test",
            created_by="user",
        )

        created = test_db.create_project(project)
        retrieved = test_db.get_project(created.id)

        assert retrieved is not None
        assert retrieved.name == "Test Project"
        assert retrieved.folder_path == "/tmp/test"
        assert retrieved.created_by == "user"

    def test_list_projects(self, test_db: Database):
        """Test listing projects."""
        test_db.create_project(
            Project(name="Project 1", folder_path="/tmp/1", created_by="user")
        )
        test_db.create_project(
            Project(name="Project 2", folder_path="/tmp/2", created_by="user")
        )

        projects = test_db.list_projects()
        assert len(projects) == 2

    def test_update_project(self, test_db: Database):
        """Test updating a project."""
        project = test_db.create_project(
            Project(name="Original", folder_path="/tmp/test", created_by="user")
        )

        project.name = "Updated"
        test_db.update_project(project)

        retrieved = test_db.get_project(project.id)
        assert retrieved.name == "Updated"

    def test_delete_project(self, test_db: Database):
        """Test deleting a project."""
        project = test_db.create_project(
            Project(name="To Delete", folder_path="/tmp/test", created_by="user")
        )

        result = test_db.delete_project(project.id)
        assert result is True

        retrieved = test_db.get_project(project.id)
        assert retrieved is None

    def test_conversation_operations(self, test_db: Database):
        """Test conversation CRUD operations."""
        # Create project first
        project = test_db.create_project(
            Project(name="Conv Test", folder_path="/tmp/test", created_by="user")
        )

        # Create conversation
        conv = Conversation(
            project_id=project.id,
            user_name="testuser",
            messages=[{"role": "user", "content": "Hello"}],
        )
        created = test_db.create_conversation(conv)

        # Get conversation
        retrieved = test_db.get_conversation(created.id)
        assert retrieved is not None
        assert retrieved.user_name == "testuser"
        assert len(retrieved.messages) == 1

        # Update conversation
        retrieved.messages.append({"role": "assistant", "content": "Hi!"})
        test_db.update_conversation(retrieved)

        updated = test_db.get_conversation(retrieved.id)
        assert len(updated.messages) == 2

        # List conversations
        convs = test_db.list_conversations(project.id)
        assert len(convs) == 1

    def test_job_operations(self, test_db: Database):
        """Test job CRUD operations."""
        project = test_db.create_project(
            Project(name="Job Test", folder_path="/tmp/test", created_by="user")
        )

        job = Job(
            project_id=project.id,
            job_type="python",
            command="print('hello')",
        )
        created = test_db.create_job(job)

        retrieved = test_db.get_job(created.id)
        assert retrieved is not None
        assert retrieved.status == "pending"

        # Update job
        retrieved.status = "running"
        retrieved.started_at = datetime.now()
        test_db.update_job(retrieved)

        updated = test_db.get_job(retrieved.id)
        assert updated.status == "running"
        assert updated.started_at is not None

    def test_document_block_operations(self, test_db: Database):
        """Test document block operations."""
        project = test_db.create_project(
            Project(name="Doc Test", folder_path="/tmp/test", created_by="user")
        )

        block = DocumentBlock(
            project_id=project.id,
            block_type="text",
            content={"text": "Hello World"},
            position=0,
        )
        test_db.create_document_block(block)

        blocks = test_db.list_document_blocks(project.id)
        assert len(blocks) == 1
        assert blocks[0].content["text"] == "Hello World"

        # Delete blocks
        count = test_db.delete_document_blocks(project.id)
        assert count == 1

    def test_todo_operations(self, test_db: Database):
        """Test agent todo operations."""
        project = test_db.create_project(
            Project(name="Todo Test", folder_path="/tmp/test", created_by="user")
        )

        todo = AgentTodo(
            project_id=project.id,
            task="Analyze data",
        )
        created = test_db.create_todo(todo)

        todos = test_db.list_todos(project.id)
        assert len(todos) == 1
        assert todos[0].task == "Analyze data"

        # Update todo
        created.status = "completed"
        created.completed_at = datetime.now()
        test_db.update_todo(created)

        updated_todos = test_db.list_todos(project.id)
        assert updated_todos[0].status == "completed"

    def test_settings_operations(self, test_db: Database):
        """Test settings operations."""
        test_db.set_setting("test_key", "test_value")

        setting = test_db.get_setting("test_key")
        assert setting is not None
        assert setting.value == "test_value"

        # Update setting
        test_db.set_setting("test_key", "new_value")
        updated = test_db.get_setting("test_key")
        assert updated.value == "new_value"

        # List settings
        settings = test_db.list_settings()
        assert len(settings) >= 1
