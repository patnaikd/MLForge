"""Database models using Pydantic."""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid4())


class Project(BaseModel):
    """Project model."""

    id: str = Field(default_factory=generate_id)
    name: str
    folder_path: str
    created_by: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    disk_usage_bytes: int = 0


class Conversation(BaseModel):
    """Conversation model."""

    id: str = Field(default_factory=generate_id)
    project_id: str
    user_name: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    messages: list[dict] = Field(default_factory=list)


class Job(BaseModel):
    """Job model for long-running tasks."""

    id: str = Field(default_factory=generate_id)
    project_id: str
    conversation_id: str | None = None
    job_type: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    command: str
    output: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class DocumentBlock(BaseModel):
    """Document block model."""

    id: str = Field(default_factory=generate_id)
    project_id: str
    block_type: Literal["text", "code", "image", "table", "latex"]
    content: dict
    position: int
    created_at: datetime = Field(default_factory=datetime.now)


class AgentTodo(BaseModel):
    """Agent todo item model."""

    id: str = Field(default_factory=generate_id)
    project_id: str
    conversation_id: str | None = None
    task: str
    status: Literal["pending", "in_progress", "completed"] = "pending"
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None


class GlobalSetting(BaseModel):
    """Global setting model."""

    key: str
    value: str
    updated_at: datetime = Field(default_factory=datetime.now)
