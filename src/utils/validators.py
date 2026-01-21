"""Input validation utilities."""

import re
from pathlib import Path


def is_valid_project_name(name: str) -> bool:
    """Check if a project name is valid.

    Args:
        name: Project name to validate

    Returns:
        True if valid, False otherwise
    """
    if not name or len(name) > 100:
        return False
    # Allow alphanumeric, spaces, hyphens, underscores
    return bool(re.match(r"^[\w\s\-]+$", name))


def is_safe_path(base_path: Path, target_path: Path) -> bool:
    """Check if a path is safely within a base directory.

    Prevents directory traversal attacks.

    Args:
        base_path: Base directory that should contain the target
        target_path: Path to validate

    Returns:
        True if target is within base, False otherwise
    """
    try:
        base_resolved = base_path.resolve()
        target_resolved = target_path.resolve()
        return target_resolved.is_relative_to(base_resolved)
    except (ValueError, OSError):
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to be safe for filesystem use.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove or replace unsafe characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(" .")
    # Limit length
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    return sanitized or "unnamed"
