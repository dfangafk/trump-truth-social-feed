"""Configuration constants and settings loader for the Truth Social data pipeline."""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import tomllib
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()  # Load .env before reading env vars in load_settings().

# --- Directory paths ---

BASE_DIR = Path(__file__).resolve().parent.parent  # repo root
DATA_DIR = BASE_DIR / "data"
RAW_OUTPUT_DIR = DATA_DIR / "raw"
ENRICHED_OUTPUT_DIR = DATA_DIR / "enriched"
LOGS_OUTPUT_DIR = DATA_DIR / "logs"

# --- URL constants ---

ARCHIVE_URL_JSON = "https://ix.cnn.io/data/truth-social/truth_archive.json"
TRUTH_SOCIAL_PROFILE_URL = "https://truthsocial.com/@realDonaldTrump"

# --- Settings dataclasses ---


@dataclass
class LLMSettings:
    """LLM provider and model configuration."""

    provider: str
    models: list[str]
    api_kwargs: dict[str, Any]


@dataclass
class PipelineSettings:
    """Pipeline run configuration."""

    hours: int
    log_level: str
    schedule: str


@dataclass
class PromptSettings:
    """LLM prompt and category configuration."""

    template: str
    categories: str


@dataclass
class Settings:
    """All tunable settings for ttsfeed, loaded from ttsfeed.toml."""

    pipeline: PipelineSettings
    llm: LLMSettings
    prompt: PromptSettings


def load_settings(toml_path: Path | None = None) -> Settings:
    """Load settings from ttsfeed.toml.

    Args:
        toml_path: Path to config file. Defaults to ``ttsfeed.toml`` in the repo root.

    Returns:
        Populated :class:`Settings` dataclass.

    Raises:
        FileNotFoundError: If the TOML file does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
        KeyError: If a required key is missing from the file.
    """
    if toml_path is None:
        toml_path = BASE_DIR / "ttsfeed.toml"

    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)

    pipeline_raw = raw["pipeline"]
    pipeline = PipelineSettings(
        hours=int(pipeline_raw["hours"]),
        log_level=pipeline_raw["log_level"],
        schedule=pipeline_raw.get("schedule", "0 23 * * *"),
    )

    llm_raw = raw["llm"]
    llm = LLMSettings(
        provider=llm_raw["provider"],
        models=list(llm_raw["models"]),
        api_kwargs=dict(llm_raw.get("api_kwargs", {})),
    )

    prompt_raw = raw["prompt"]
    prompt = PromptSettings(
        template=prompt_raw["template"],
        categories=prompt_raw["categories"],
    )

    return Settings(pipeline=pipeline, llm=llm, prompt=prompt)


settings = load_settings()

# --- Email notification (secrets from .env) ---

SENDER_GMAIL = os.getenv("SENDER_GMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")

if SENDER_GMAIL and not SENDER_GMAIL.endswith("@gmail.com"):
    logger.warning(
        "SENDER_GMAIL=%r does not end with @gmail.com; SMTP login will likely fail",
        SENDER_GMAIL,
    )
