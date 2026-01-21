"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest

from src.config.settings import Settings
from src.database.connection import Database


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temporary paths."""
    return Settings(
        workspace_path=temp_dir / "workspace",
        database_path=temp_dir / "workspace" / "agent.db",
        llm_provider="anthropic",
        anthropic_api_key="test-key",
    )


@pytest.fixture
def test_db(test_settings: Settings) -> Database:
    """Create a test database."""
    test_settings.ensure_workspace_exists()
    return Database(test_settings.database_path)
