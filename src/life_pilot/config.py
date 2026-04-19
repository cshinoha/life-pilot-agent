"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = Field(description="Telegram Bot API token")
    groq_api_key: str = Field(
        default="",
        description="Groq API key for Whisper transcription",
    )
    deepgram_api_key: str = Field(
        default="",
        description="Deprecated: Deepgram API key (use groq_api_key)",
    )
    vault_path: Path = Field(
        default=Path("./vault"),
        description="Path to Obsidian vault directory",
    )
    tasknotes_dir: Path = Field(
        default=Path("TaskNotes/Tasks"),
        description="Relative path inside the vault for TaskNotes task files",
    )
    google_token_path: Path = Field(
        default=Path("~/life-pilot/token.json"),
        description="Path to Google OAuth token JSON file",
    )
    allowed_user_ids: list[int] = Field(
        default_factory=list,
        description="List of Telegram user IDs allowed to use the bot",
    )
    allow_all_users: bool = Field(
        default=False,
        description="Whether to allow access to all users (security risk!)",
    )
    transcription_language: str = Field(
        default="ru",
        description="Transcription language (e.g. ru, en, multi)",
    )
    claude_timeout: int = Field(
        default=1200,
        description="LLM CLI subprocess timeout in seconds",
    )
    llm_cli: str = Field(
        default="codex",
        description="LLM CLI binary to use (codex or claude)",
    )
    llm_model: str = Field(
        default="",
        description="Default model passed to LLM CLI. Empty = CLI default.",
    )
    coach_model: str = Field(
        default="",
        description="Model override for coach mode. Empty = default model.",
    )
    timezone: str = Field(
        default="Europe/Kyiv",
        description="Timezone for scheduler and date calculations (e.g. Europe/Kyiv)",
    )

    @field_validator("vault_path", "google_token_path", "tasknotes_dir", mode="before")
    @classmethod
    def expand_home(cls, v: object) -> Path:
        """Expand ~ in paths (not done automatically in systemd environment)."""
        return Path(str(v)).expanduser()

    @property
    def tasknotes_path(self) -> Path:
        """Path to the directory that stores TaskNotes files."""
        if self.tasknotes_dir.is_absolute():
            return self.tasknotes_dir
        return self.vault_path / self.tasknotes_dir

    @property
    def daily_path(self) -> Path:
        """Path to daily notes directory."""
        return self.vault_path / "daily"

    @property
    def attachments_path(self) -> Path:
        """Path to attachments directory."""
        return self.vault_path / "attachments"

    @property
    def thoughts_path(self) -> Path:
        """Path to thoughts directory."""
        return self.vault_path / "thoughts"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get application settings instance (cached singleton)."""
    return Settings()  # type: ignore[call-arg]
