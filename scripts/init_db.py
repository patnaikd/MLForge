#!/usr/bin/env python3
"""Initialize database schema."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings
from src.database.connection import Database


def main() -> None:
    """Initialize database."""
    settings = get_settings()

    print(f"Initializing database at: {settings.database_path}")

    # Ensure workspace exists
    settings.ensure_workspace_exists()

    # Create database (this will run _init_schema)
    db = Database(settings.database_path)

    print("Database initialized with tables:")
    print("  - projects")
    print("  - conversations")
    print("  - jobs")
    print("  - document_blocks")
    print("  - agent_todos")
    print("  - settings")

    # Set default settings
    db.set_setting("activity_timeout", str(settings.activity_timeout))
    db.set_setting("overall_timeout", str(settings.overall_timeout))
    db.set_setting("default_llm_provider", settings.llm_provider)

    print("\nDefault settings configured.")
    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    main()
