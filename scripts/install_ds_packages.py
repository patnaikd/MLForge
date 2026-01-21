#!/usr/bin/env python3
"""Install data science packages in the workspace virtual environment."""

import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings


def main() -> None:
    """Install data science packages."""
    settings = get_settings()
    workspace_path = settings.workspace_path

    venv_path = workspace_path / ".venv"

    print(f"Setting up virtual environment at: {venv_path}")

    # Create virtual environment with uv
    if not venv_path.exists():
        print("Creating virtual environment...")
        subprocess.run(["uv", "venv", str(venv_path)], check=True)
        print(f"  Created: {venv_path}")

    # Data science packages to install
    packages = [
        "numpy>=1.26",
        "pandas>=2.2",
        "scipy>=1.13",
        "scikit-learn>=1.5",
        "xgboost>=2.0",
        "lightgbm>=4.4",
        "catboost>=1.2",
        "matplotlib>=3.9",
        "seaborn>=0.13",
        "plotly>=5.22",
        "polars>=1.0",
        "pyarrow>=16.0",
        "openpyxl>=3.1",
        "statsmodels>=0.14",
        "tqdm>=4.66",
        "joblib>=1.4",
    ]

    print("\nInstalling data science packages...")
    print("This may take a few minutes...\n")

    # Install packages using uv
    for package in packages:
        print(f"  Installing: {package}")
        subprocess.run(
            ["uv", "pip", "install", "--python", str(venv_path / "bin" / "python"), package],
            check=True,
            capture_output=True,
        )

    print("\nData science packages installed!")
    print(f"\nTo activate the environment:")
    print(f"  source {venv_path}/bin/activate")


if __name__ == "__main__":
    main()
