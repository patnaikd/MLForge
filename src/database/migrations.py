"""Database schema migrations."""

import sqlite3
from pathlib import Path


def run_migrations(db_path: Path) -> None:
    """Run database migrations.

    This is a simple migration system that checks version and applies updates.
    For a production system, consider using Alembic or similar.

    Args:
        db_path: Path to SQLite database
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get current version
    try:
        version = conn.execute(
            "SELECT value FROM settings WHERE key = 'schema_version'"
        ).fetchone()
        current_version = int(version["value"]) if version else 0
    except sqlite3.OperationalError:
        current_version = 0

    migrations = [
        # Migration 1: Initial schema (handled by connection.py _init_schema)
        None,
        # Future migrations go here as functions
    ]

    for i, migration in enumerate(migrations[current_version:], start=current_version):
        if migration:
            migration(conn)

        # Update version
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES ('schema_version', ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = datetime('now')
            """,
            (str(i + 1), str(i + 1)),
        )
        conn.commit()

    conn.close()
