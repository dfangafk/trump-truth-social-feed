"""Configuration constants and settings loader for the Truth Social data pipeline."""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# --- Directory paths ---

BASE_DIR = Path(__file__).resolve().parent.parent  # repo root

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
    models: list[str] = ["gemini/gemini-3-flash-preview", "gemini/gemini-2.5-flash"]
    api_kwargs: dict[str, Any] = {"num_retries": 3}


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

    template: str = """
    You are analyzing Trump's Truth Social posts for a daily briefing.

    Substantive posts ({n} total):
    {numbered_posts}

    Assign each post exactly one category from this list. Use "Other" if no specific category fits:
    {categories}

    Respond with valid JSON only, no markdown:
    {{"summary": "<2-3 sentence daily overview>", "posts": [{{"id": "<post id>", "categories": ["<category names>"]}}]}}
    """

    categories: str = """
    - Elections & Campaigns: Elections, voting, polling, endorsements, rallies, and campaign competition.
    - Tariffs & Trade: Tariffs, trade deficits/surpluses, trade deals, and import/export policy.
    - Economy, Jobs & Inflation: Economic growth, labor market conditions, wages, inflation, and business activity.
    - Taxes & Regulation: Tax policy, regulatory burden, deregulation, permits, and compliance.
    - Border & Immigration: Border enforcement, migration, asylum, deportation, and entry policy.
    - Crime & Public Safety: Crime trends, policing, drugs/fentanyl, gangs, and local public safety.
    - Courts & Legal Proceedings: Courts, judges, trials, indictments, rulings, constitutional and legal claims.
    - Foreign Affairs & Defense: International conflicts, geopolitics, military posture, alliances, and national security.
    - Media & Public Narrative: Media coverage, press criticism, narrative framing, speech and culture debates.
    - Other: Fallback when no topical category is a clear fit.
    """


class PathSettings(BaseModel):
    """Filesystem output paths for the pipeline."""

    raw_output_dir: Path = BASE_DIR / "data" / "raw"
    enriched_output_dir: Path = BASE_DIR / "data" / "enriched"
    logs_output_dir: Path = BASE_DIR / "data" / "logs"
    templates_dir: Path = BASE_DIR / "ttsfeed" / "templates"


class Settings(BaseSettings):
    """All tunable settings for ttsfeed, loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    fetch: FetchSettings = FetchSettings()
    notify: NotifySettings = NotifySettings()
    pipeline: PipelineSettings = PipelineSettings()
    llm: LLMSettings = LLMSettings()
    prompt: PromptSettings = PromptSettings()
    paths: PathSettings = PathSettings()

    # Secrets from .env
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    sender_gmail: str = ""
    gmail_app_password: str = ""
    receiver_email: str = ""


settings = Settings()

if settings.sender_gmail and not settings.sender_gmail.endswith("@gmail.com"):
    logger.warning(
        "sender_gmail=%r does not end with @gmail.com; SMTP login will likely fail",
        settings.sender_gmail,
    )
