#!/usr/bin/env python3
"""Initialize workspace directory structure."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings


def main() -> None:
    """Initialize workspace directory."""
    settings = get_settings()

    print(f"Setting up workspace at: {settings.workspace_path}")

    # Create workspace directory
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    print(f"  Created: {settings.workspace_path}")

    # Create .gitkeep to preserve directory in git
    gitkeep = settings.workspace_path / ".gitkeep"
    gitkeep.touch()
    print(f"  Created: {gitkeep}")

    print("\nWorkspace setup complete!")
    print(f"\nNext steps:")
    print(f"  1. Copy .env.example to .env and configure your API keys")
    print(f"  2. Run: uv sync")
    print(f"  3. Run: streamlit run src/main.py")


if __name__ == "__main__":
    main()
