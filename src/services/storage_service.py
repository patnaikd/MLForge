"""Storage and disk usage tracking service."""

from pathlib import Path

from src.config.settings import Settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    """Service for managing storage and disk usage."""

    def __init__(self, settings: Settings):
        """Initialize storage service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.workspace_path = settings.workspace_path

    def get_workspace_usage(self) -> dict:
        """Get workspace disk usage summary.

        Returns:
            Dict with total, used, and breakdown by project
        """
        total_used = 0
        projects_usage = []

        if not self.workspace_path.exists():
            return {"total_used": 0, "projects": []}

        for item in self.workspace_path.iterdir():
            if item.is_dir() and item.name != ".venv":
                size = self._get_dir_size(item)
                total_used += size
                projects_usage.append({
                    "name": item.name,
                    "path": str(item),
                    "size_bytes": size,
                    "size_formatted": self._format_size(size),
                })

        return {
            "total_used": total_used,
            "total_formatted": self._format_size(total_used),
            "projects": sorted(projects_usage, key=lambda x: x["size_bytes"], reverse=True),
        }

    def _get_dir_size(self, path: Path) -> int:
        """Calculate total size of a directory.

        Args:
            path: Directory path

        Returns:
            Size in bytes
        """
        total = 0
        try:
            for item in path.rglob("*"):
                if item.is_file():
                    total += item.stat().st_size
        except (OSError, PermissionError) as e:
            logger.warning(f"Error calculating size for {path}: {e}")
        return total

    def _format_size(self, bytes_size: int) -> str:
        """Format size in human-readable form.

        Args:
            bytes_size: Size in bytes

        Returns:
            Formatted string
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_size < 1024:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024
        return f"{bytes_size:.1f} PB"

    def cleanup_empty_projects(self) -> list[str]:
        """Remove empty project directories.

        Returns:
            List of removed directory names
        """
        removed = []
        if not self.workspace_path.exists():
            return removed

        for item in self.workspace_path.iterdir():
            if item.is_dir() and item.name != ".venv":
                # Check if directory is empty (no files, only empty subdirs)
                has_files = any(f.is_file() for f in item.rglob("*"))
                if not has_files:
                    try:
                        import shutil
                        shutil.rmtree(item)
                        removed.append(item.name)
                        logger.info(f"Removed empty project directory: {item}")
                    except OSError as e:
                        logger.error(f"Failed to remove {item}: {e}")

        return removed
