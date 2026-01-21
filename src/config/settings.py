"""Global configuration settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Configuration
    llm_provider: Literal["anthropic", "openai", "ollama"] = Field(
        default="anthropic",
        alias="LLM_PROVIDER",
    )
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")

    # Model Selection
    anthropic_model: str = Field(
        default="claude-sonnet-4-20250514",
        alias="ANTHROPIC_MODEL",
    )
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")

    # Workspace
    workspace_path: Path = Field(default=Path("./workspace"), alias="WORKSPACE_PATH")

    # Timeouts (seconds)
    activity_timeout: int = Field(default=300, alias="ACTIVITY_TIMEOUT")
    overall_timeout: int = Field(default=3600, alias="OVERALL_TIMEOUT")

    # Database
    database_path: Path = Field(
        default=Path("./workspace/agent.db"),
        alias="DATABASE_PATH",
    )

    # Streamlit
    streamlit_server_port: int = Field(default=8501, alias="STREAMLIT_SERVER_PORT")

    # Project settings
    project_prefix: str = Field(default="mlforge", alias="PROJECT_PREFIX")

    def ensure_workspace_exists(self) -> None:
        """Create workspace directory if it doesn't exist."""
        self.workspace_path.mkdir(parents=True, exist_ok=True)

    @property
    def database_url(self) -> str:
        """Get SQLite database URL."""
        return f"sqlite:///{self.database_path}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_workspace_exists()
    return settings
