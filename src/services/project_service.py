"""Project management service."""

import shutil
from datetime import datetime
from pathlib import Path

from src.config.settings import Settings
from src.database.connection import Database
from src.database.models import Conversation, Project
from src.utils.logging import get_logger
from src.utils.validators import is_safe_path, is_valid_project_name

logger = get_logger(__name__)


class ProjectService:
    """Service for managing projects."""

    def __init__(self, db: Database, settings: Settings):
        """Initialize project service.

        Args:
            db: Database instance
            settings: Application settings
        """
        self.db = db
        self.settings = settings

    def create_project(self, name: str, created_by: str) -> Project:
        """Create a new project with folder structure.

        Args:
            name: Project name
            created_by: Username of creator

        Returns:
            Created project

        Raises:
            ValueError: If project name is invalid
        """
        if not is_valid_project_name(name):
            raise ValueError(f"Invalid project name: {name}")

        # Generate folder name with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        folder_name = f"{self.settings.project_prefix}-{timestamp}"
        folder_path = self.settings.workspace_path / folder_name

        # Create folder structure
        folder_path.mkdir(parents=True, exist_ok=True)
        (folder_path / "data").mkdir(exist_ok=True)
        (folder_path / "images").mkdir(exist_ok=True)
        (folder_path / "code").mkdir(exist_ok=True)
        (folder_path / "outputs").mkdir(exist_ok=True)

        logger.info(f"Created project folder: {folder_path}")

        # Create project record
        project = Project(
            name=name,
            folder_path=str(folder_path),
            created_by=created_by,
        )

        return self.db.create_project(project)

    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID.

        Args:
            project_id: Project ID

        Returns:
            Project or None if not found
        """
        return self.db.get_project(project_id)

    def list_projects(self) -> list[Project]:
        """List all projects.

        Returns:
            List of projects ordered by last update
        """
        return self.db.list_projects()

    def delete_project(self, project_id: str, delete_files: bool = True) -> bool:
        """Delete a project.

        Args:
            project_id: Project ID
            delete_files: Whether to delete project files

        Returns:
            True if deleted, False if not found
        """
        project = self.db.get_project(project_id)
        if not project:
            return False

        if delete_files:
            folder_path = Path(project.folder_path)
            if folder_path.exists():
                shutil.rmtree(folder_path)
                logger.info(f"Deleted project folder: {folder_path}")

        return self.db.delete_project(project_id)

    def get_project_path(self, project: Project) -> Path:
        """Get the filesystem path for a project.

        Args:
            project: Project instance

        Returns:
            Path to project folder
        """
        return Path(project.folder_path)

    def calculate_disk_usage(self, project: Project) -> int:
        """Calculate disk usage for a project.

        Args:
            project: Project instance

        Returns:
            Disk usage in bytes
        """
        folder_path = Path(project.folder_path)
        if not folder_path.exists():
            return 0

        total_size = 0
        for file_path in folder_path.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        # Update project with new disk usage
        project.disk_usage_bytes = total_size
        self.db.update_project(project)

        return total_size

    def get_total_workspace_usage(self) -> int:
        """Calculate total workspace disk usage.

        Returns:
            Total disk usage in bytes
        """
        total = 0
        for project in self.list_projects():
            total += self.calculate_disk_usage(project)
        return total

    def upload_file(
        self, project: Project, file_content: bytes, filename: str, subfolder: str = "data"
    ) -> Path:
        """Upload a file to a project.

        Args:
            project: Project instance
            file_content: File content as bytes
            filename: Name for the file
            subfolder: Subfolder to upload to (default: "data")

        Returns:
            Path to uploaded file

        Raises:
            ValueError: If path is invalid or unsafe
        """
        project_path = Path(project.folder_path)
        target_dir = project_path / subfolder
        target_path = target_dir / filename

        # Security check
        if not is_safe_path(project_path, target_path):
            raise ValueError("Invalid file path")

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(file_content)

        logger.info(f"Uploaded file: {target_path}")
        return target_path

    def list_files(self, project: Project, subfolder: str | None = None) -> list[dict]:
        """List files in a project.

        Args:
            project: Project instance
            subfolder: Optional subfolder to list

        Returns:
            List of file info dicts with name, path, size, is_dir
        """
        project_path = Path(project.folder_path)
        if subfolder:
            target_path = project_path / subfolder
        else:
            target_path = project_path

        if not target_path.exists():
            return []

        files = []
        for item in sorted(target_path.iterdir()):
            file_info = {
                "name": item.name,
                "path": str(item.relative_to(project_path)),
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0,
            }
            files.append(file_info)

        return files

    def create_conversation(self, project: Project, user_name: str) -> Conversation:
        """Create a new conversation for a project.

        Args:
            project: Project instance
            user_name: Username

        Returns:
            Created conversation
        """
        conversation = Conversation(
            project_id=project.id,
            user_name=user_name,
        )
        return self.db.create_conversation(conversation)

    def get_conversations(self, project: Project) -> list[Conversation]:
        """Get all conversations for a project.

        Args:
            project: Project instance

        Returns:
            List of conversations
        """
        return self.db.list_conversations(project.id)

    def format_disk_usage(self, bytes_size: int) -> str:
        """Format disk usage in human-readable form.

        Args:
            bytes_size: Size in bytes

        Returns:
            Formatted string (e.g., "1.5 GB")
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} PB"
