"""Configuration constants and settings loader for the Truth Social data pipeline."""

import logging
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource
)

logger = logging.getLogger(__name__)

# --- Directory paths ---

BASE_DIR = Path(__file__).resolve().parent.parent  # repo root
DATA_DIR = BASE_DIR / "data"

# --- URL constants ---

TRUTH_SOCIAL_PROFILE_URL = "https://truthsocial.com/@realDonaldTrump"

# --- Settings models ---


class FetchSettings(BaseModel):
    """HTTP fetch configuration for the archive download."""

    archive_url: str = "https://ix.cnn.io/data/truth-social/truth_archive.json"
    timeout: int = 120
    user_agent: str = "ttsfeed/0.1 (Truth Social archive tracker)"


class NotifySettings(BaseModel):
    """Email notification configuration."""

    timezone: str = "America/New_York"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    subject_template: str = "Trump Truth Social Feed — {date} ({count} new posts)"


class LLMSettings(BaseModel):
    """LLM provider and model configuration."""

    provider: str = "auto"
    models: list[str] = []
    api_kwargs: dict[str, Any] = {}


class PipelineSettings(BaseModel):
    """Pipeline run configuration."""

    hours: int = 24
    log_level: str = "INFO"
    schedule: str = "0 23 * * *"
    save_raw: bool = False       # write data/raw/YYYY-MM-DD.json
    save_enriched: bool = False  # write data/enriched/YYYY-MM-DD.json
    save_logs: bool = False      # write data/logs/YYYY-MM-DD.log


class PromptSettings(BaseModel):
    """LLM prompt and category configuration."""

    template: str
    categories: str


class PathSettings(BaseModel):
    """Filesystem output paths for the pipeline."""

    raw_output_dir: Path = BASE_DIR / "data" / "raw"
    enriched_output_dir: Path = BASE_DIR / "data" / "enriched"
    logs_output_dir: Path = BASE_DIR / "data" / "logs"
    templates_dir: Path = BASE_DIR / "ttsfeed" / "templates"


class Settings(BaseSettings):
    """All tunable settings for ttsfeed, loaded from settings.toml and .env."""

    model_config = SettingsConfigDict(
        toml_file=BASE_DIR / "settings.toml",
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    fetch: FetchSettings = FetchSettings()
    notify: NotifySettings = NotifySettings()
    pipeline: PipelineSettings = PipelineSettings()
    llm: LLMSettings = LLMSettings()
    prompt: PromptSettings
    paths: PathSettings = PathSettings()

    # Secrets from .env
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    sender_gmail: str = ""
    gmail_app_password: str = ""
    receiver_email: str = ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, dotenv_settings, TomlConfigSettingsSource(settings_cls), file_secret_settings)


try:
    settings = Settings()
except (ValidationError, FileNotFoundError, Exception) as exc:
    logger.error(
        "Failed to load settings — check settings.toml and .env at %s: %s",
        BASE_DIR,
        exc,
    )
    sys.exit(1)

if settings.sender_gmail and not settings.sender_gmail.endswith("@gmail.com"):
    logger.warning(
        "sender_gmail=%r does not end with @gmail.com; SMTP login will likely fail",
        settings.sender_gmail,
    )
