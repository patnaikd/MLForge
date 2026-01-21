"""SQLite database connection and operations."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Generator

from src.database.models import (
    AgentTodo,
    Conversation,
    DocumentBlock,
    GlobalSetting,
    Job,
    Project,
)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: Path):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_exists()
        self._init_schema()

    def _ensure_db_exists(self) -> None:
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self.get_connection() as conn:
            conn.executescript(
                """
                -- Projects table
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    folder_path TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    disk_usage_bytes INTEGER DEFAULT 0
                );

                -- Conversations table
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    messages JSON NOT NULL DEFAULT '[]',
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );

                -- Jobs table
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    conversation_id TEXT,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    command TEXT NOT NULL,
                    output TEXT,
                    error TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE SET NULL
                );

                -- Document blocks table
                CREATE TABLE IF NOT EXISTS document_blocks (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    block_type TEXT NOT NULL,
                    content JSON NOT NULL,
                    position INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );

                -- Agent todo list
                CREATE TABLE IF NOT EXISTS agent_todos (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    conversation_id TEXT,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );

                -- Global settings
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_conversations_project
                    ON conversations(project_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_project
                    ON jobs(project_id);
                CREATE INDEX IF NOT EXISTS idx_jobs_status
                    ON jobs(status);
                CREATE INDEX IF NOT EXISTS idx_document_blocks_project
                    ON document_blocks(project_id);
                CREATE INDEX IF NOT EXISTS idx_agent_todos_project
                    ON agent_todos(project_id);
                """
            )

    # Project operations
    def create_project(self, project: Project) -> Project:
        """Create a new project."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, folder_path, created_by, created_at, updated_at, disk_usage_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    project.name,
                    project.folder_path,
                    project.created_by,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                    project.disk_usage_bytes,
                ),
            )
        return project

    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if row:
                return self._row_to_project(row)
        return None

    def list_projects(self) -> list[Project]:
        """List all projects."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY updated_at DESC"
            ).fetchall()
            return [self._row_to_project(row) for row in rows]

    def update_project(self, project: Project) -> Project:
        """Update an existing project."""
        project.updated_at = datetime.now()
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE projects
                SET name = ?, folder_path = ?, updated_at = ?, disk_usage_bytes = ?
                WHERE id = ?
                """,
                (
                    project.name,
                    project.folder_path,
                    project.updated_at.isoformat(),
                    project.disk_usage_bytes,
                    project.id,
                ),
            )
        return project

    def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return cursor.rowcount > 0

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        """Convert database row to Project model."""
        return Project(
            id=row["id"],
            name=row["name"],
            folder_path=row["folder_path"],
            created_by=row["created_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            disk_usage_bytes=row["disk_usage_bytes"],
        )

    # Conversation operations
    def create_conversation(self, conversation: Conversation) -> Conversation:
        """Create a new conversation."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, project_id, user_name, created_at, updated_at, messages)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation.id,
                    conversation.project_id,
                    conversation.user_name,
                    conversation.created_at.isoformat(),
                    conversation.updated_at.isoformat(),
                    json.dumps(conversation.messages),
                ),
            )
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Get a conversation by ID."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if row:
                return self._row_to_conversation(row)
        return None

    def list_conversations(self, project_id: str) -> list[Conversation]:
        """List conversations for a project."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM conversations WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            ).fetchall()
            return [self._row_to_conversation(row) for row in rows]

    def update_conversation(self, conversation: Conversation) -> Conversation:
        """Update a conversation."""
        conversation.updated_at = datetime.now()
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET messages = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(conversation.messages),
                    conversation.updated_at.isoformat(),
                    conversation.id,
                ),
            )
        return conversation

    def _row_to_conversation(self, row: sqlite3.Row) -> Conversation:
        """Convert database row to Conversation model."""
        return Conversation(
            id=row["id"],
            project_id=row["project_id"],
            user_name=row["user_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            messages=json.loads(row["messages"]),
        )

    # Job operations
    def create_job(self, job: Job) -> Job:
        """Create a new job."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, project_id, conversation_id, job_type, status, command, output, error, started_at, completed_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.project_id,
                    job.conversation_id,
                    job.job_type,
                    job.status,
                    job.command,
                    job.output,
                    job.error,
                    job.started_at.isoformat() if job.started_at else None,
                    job.completed_at.isoformat() if job.completed_at else None,
                    job.created_at.isoformat(),
                ),
            )
        return job

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row:
                return self._row_to_job(row)
        return None

    def list_jobs(self, project_id: str) -> list[Job]:
        """List jobs for a project."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
            return [self._row_to_job(row) for row in rows]

    def update_job(self, job: Job) -> Job:
        """Update a job."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, output = ?, error = ?, started_at = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    job.status,
                    job.output,
                    job.error,
                    job.started_at.isoformat() if job.started_at else None,
                    job.completed_at.isoformat() if job.completed_at else None,
                    job.id,
                ),
            )
        return job

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert database row to Job model."""
        return Job(
            id=row["id"],
            project_id=row["project_id"],
            conversation_id=row["conversation_id"],
            job_type=row["job_type"],
            status=row["status"],
            command=row["command"],
            output=row["output"],
            error=row["error"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # Document block operations
    def create_document_block(self, block: DocumentBlock) -> DocumentBlock:
        """Create a new document block."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO document_blocks (id, project_id, block_type, content, position, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    block.id,
                    block.project_id,
                    block.block_type,
                    json.dumps(block.content),
                    block.position,
                    block.created_at.isoformat(),
                ),
            )
        return block

    def list_document_blocks(self, project_id: str) -> list[DocumentBlock]:
        """List document blocks for a project."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM document_blocks WHERE project_id = ? ORDER BY position",
                (project_id,),
            ).fetchall()
            return [self._row_to_document_block(row) for row in rows]

    def delete_document_blocks(self, project_id: str) -> int:
        """Delete all document blocks for a project."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM document_blocks WHERE project_id = ?", (project_id,)
            )
            return cursor.rowcount

    def _row_to_document_block(self, row: sqlite3.Row) -> DocumentBlock:
        """Convert database row to DocumentBlock model."""
        return DocumentBlock(
            id=row["id"],
            project_id=row["project_id"],
            block_type=row["block_type"],
            content=json.loads(row["content"]),
            position=row["position"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # Agent todo operations
    def create_todo(self, todo: AgentTodo) -> AgentTodo:
        """Create a new agent todo."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_todos (id, project_id, conversation_id, task, status, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    todo.id,
                    todo.project_id,
                    todo.conversation_id,
                    todo.task,
                    todo.status,
                    todo.created_at.isoformat(),
                    todo.completed_at.isoformat() if todo.completed_at else None,
                ),
            )
        return todo

    def list_todos(self, project_id: str) -> list[AgentTodo]:
        """List todos for a project."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_todos WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
            return [self._row_to_todo(row) for row in rows]

    def update_todo(self, todo: AgentTodo) -> AgentTodo:
        """Update a todo."""
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE agent_todos
                SET status = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    todo.status,
                    todo.completed_at.isoformat() if todo.completed_at else None,
                    todo.id,
                ),
            )
        return todo

    def _row_to_todo(self, row: sqlite3.Row) -> AgentTodo:
        """Convert database row to AgentTodo model."""
        return AgentTodo(
            id=row["id"],
            project_id=row["project_id"],
            conversation_id=row["conversation_id"],
            task=row["task"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )

    # Settings operations
    def get_setting(self, key: str) -> GlobalSetting | None:
        """Get a global setting."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM settings WHERE key = ?", (key,)
            ).fetchone()
            if row:
                return GlobalSetting(
                    key=row["key"],
                    value=row["value"],
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
        return None

    def set_setting(self, key: str, value: str) -> GlobalSetting:
        """Set a global setting."""
        setting = GlobalSetting(key=key, value=value)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
                """,
                (
                    key,
                    value,
                    setting.updated_at.isoformat(),
                    value,
                    setting.updated_at.isoformat(),
                ),
            )
        return setting

    def list_settings(self) -> list[GlobalSetting]:
        """List all global settings."""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM settings").fetchall()
            return [
                GlobalSetting(
                    key=row["key"],
                    value=row["value"],
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in rows
            ]


@lru_cache
def get_database() -> Database:
    """Get cached database instance."""
    from src.config.settings import get_settings

    settings = get_settings()
    return Database(settings.database_path)
