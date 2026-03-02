"""Configuration constants and settings loader for the Truth Social data pipeline."""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel
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

ARCHIVE_URL_JSON = "https://ix.cnn.io/data/truth-social/truth_archive.json"
TRUTH_SOCIAL_PROFILE_URL = "https://truthsocial.com/@realDonaldTrump"

# --- Settings models ---


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


class PromptSettings(BaseModel):
    """LLM prompt and category configuration."""

    template: str
    categories: str


class PathSettings(BaseModel):
    """Filesystem output paths for the pipeline."""

    raw_output_dir: Path = BASE_DIR / "data" / "raw"
    enriched_output_dir: Path = BASE_DIR / "data" / "enriched"
    logs_output_dir: Path = BASE_DIR / "data" / "logs"


class Settings(BaseSettings):
    """All tunable settings for ttsfeed, loaded from ttsfeed.toml and .env."""

    model_config = SettingsConfigDict(
        toml_file=BASE_DIR / "ttsfeed.toml",
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )

    pipeline: PipelineSettings = PipelineSettings()
    llm: LLMSettings = LLMSettings()
    prompt: PromptSettings
    paths: PathSettings = PathSettings()

    # Secrets from .env
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


settings = Settings()

if settings.sender_gmail and not settings.sender_gmail.endswith("@gmail.com"):
    logger.warning(
        "sender_gmail=%r does not end with @gmail.com; SMTP login will likely fail",
        settings.sender_gmail,
    )
