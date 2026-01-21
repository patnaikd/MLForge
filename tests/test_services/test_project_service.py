"""Tests for project service."""

from pathlib import Path

import pytest

from src.config.settings import Settings
from src.database.connection import Database
from src.services.project_service import ProjectService


class TestProjectService:
    """Test cases for ProjectService."""

    def test_create_project(self, test_db: Database, test_settings: Settings):
        """Test creating a new project."""
        service = ProjectService(test_db, test_settings)

        project = service.create_project(
            name="Test Project",
            created_by="testuser",
        )

        assert project.name == "Test Project"
        assert project.created_by == "testuser"
        assert project.id is not None

        # Check folder was created
        folder_path = Path(project.folder_path)
        assert folder_path.exists()
        assert (folder_path / "data").exists()
        assert (folder_path / "images").exists()
        assert (folder_path / "code").exists()
        assert (folder_path / "outputs").exists()

    def test_create_project_invalid_name(self, test_db: Database, test_settings: Settings):
        """Test that invalid project names are rejected."""
        service = ProjectService(test_db, test_settings)

        with pytest.raises(ValueError):
            service.create_project(name="", created_by="testuser")

        with pytest.raises(ValueError):
            service.create_project(name="a" * 200, created_by="testuser")

    def test_get_project(self, test_db: Database, test_settings: Settings):
        """Test retrieving a project by ID."""
        service = ProjectService(test_db, test_settings)

        created = service.create_project(name="Test", created_by="user")
        retrieved = service.get_project(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test"

    def test_list_projects(self, test_db: Database, test_settings: Settings):
        """Test listing all projects."""
        service = ProjectService(test_db, test_settings)

        service.create_project(name="Project 1", created_by="user")
        service.create_project(name="Project 2", created_by="user")

        projects = service.list_projects()

        assert len(projects) == 2

    def test_delete_project(self, test_db: Database, test_settings: Settings):
        """Test deleting a project."""
        service = ProjectService(test_db, test_settings)

        project = service.create_project(name="To Delete", created_by="user")
        folder_path = Path(project.folder_path)

        assert folder_path.exists()

        result = service.delete_project(project.id, delete_files=True)

        assert result is True
        assert not folder_path.exists()
        assert service.get_project(project.id) is None

    def test_upload_file(self, test_db: Database, test_settings: Settings):
        """Test uploading a file to a project."""
        service = ProjectService(test_db, test_settings)
        project = service.create_project(name="Upload Test", created_by="user")

        content = b"test,data\n1,2\n3,4"
        path = service.upload_file(project, content, "test.csv")

        assert path.exists()
        assert path.read_bytes() == content

    def test_list_files(self, test_db: Database, test_settings: Settings):
        """Test listing files in a project."""
        service = ProjectService(test_db, test_settings)
        project = service.create_project(name="Files Test", created_by="user")

        # Upload a file
        service.upload_file(project, b"content", "test.txt", subfolder="data")

        files = service.list_files(project, "data")

        assert len(files) == 1
        assert files[0]["name"] == "test.txt"
        assert not files[0]["is_dir"]

    def test_calculate_disk_usage(self, test_db: Database, test_settings: Settings):
        """Test calculating disk usage."""
        service = ProjectService(test_db, test_settings)
        project = service.create_project(name="Disk Test", created_by="user")

        # Upload some data
        service.upload_file(project, b"x" * 1000, "data.bin")

        usage = service.calculate_disk_usage(project)

        assert usage >= 1000

    def test_format_disk_usage(self, test_db: Database, test_settings: Settings):
        """Test formatting disk usage."""
        service = ProjectService(test_db, test_settings)

        assert "B" in service.format_disk_usage(100)
        assert "KB" in service.format_disk_usage(1024)
        assert "MB" in service.format_disk_usage(1024 * 1024)
        assert "GB" in service.format_disk_usage(1024 * 1024 * 1024)
