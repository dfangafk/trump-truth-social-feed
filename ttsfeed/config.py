"""Configuration constants for the Truth Social data pipeline."""

from pathlib import Path
from datetime import date

# Archive URLs (CNN's publicly hosted Trump Truth Social archive)
ARCHIVE_URL_PARQUET = "https://ix.cnn.io/data/truth-social/truth_archive.parquet"
ARCHIVE_URL_JSON = "https://ix.cnn.io/data/truth-social/truth_archive.json"

# Truth Social profile
TRUTH_SOCIAL_PROFILE_URL = "https://truthsocial.com/@realDonaldTrump"

# Directory paths
BASE_DIR = Path(__file__).resolve().parent.parent  # repo root
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output"


POST_CATEGORIES: list[str] = [
    "immigration",
    "election integrity",
    "media criticism",
    "economy / trade",
    "foreign policy",
    "legal / courts",
    "endorsements",
    "personal attacks",
    "MAGA / rallies",
]


def output_path(d: date) -> Path:
    """Return path to the output JSON file for a given date."""
    return OUTPUT_DIR / f"{d.isoformat()}.json"
