"""Configuration constants for the Truth Social data pipeline."""

from datetime import date
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()  # Load .env from project root when present.

# Archive URL (CNN's publicly hosted Trump Truth Social archive)
ARCHIVE_URL_JSON = "https://ix.cnn.io/data/truth-social/truth_archive.json"

# Truth Social profile
TRUTH_SOCIAL_PROFILE_URL = "https://truthsocial.com/@realDonaldTrump"

# Directory paths
BASE_DIR = Path(__file__).resolve().parent.parent  # repo root
DATA_DIR = BASE_DIR / "data"
RAW_OUTPUT_DIR = DATA_DIR / "raw"
ENRICHED_OUTPUT_DIR = DATA_DIR / "enriched"

# LLM configuration — override via .env or environment variables.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
# JSON array of models to try in order (e.g. '["openai/gpt-4o","gemini/gemini-2.5-flash"]').
LLM_MODELS: list[str] = json.loads(os.getenv("LLM_MODELS", "[]"))


POST_TAGS: dict[str, str] = {
    "Elections & Campaigns": "Elections, voting, polling, endorsements, rallies, and campaign competition.",
    "Tariffs & Trade": "Tariffs, trade deficits/surpluses, trade deals, and import/export policy.",
    "Economy, Jobs & Inflation": "Economic growth, labor market conditions, wages, inflation, and business activity.",
    "Taxes & Regulation": "Tax policy, regulatory burden, deregulation, permits, and compliance.",
    "Border & Immigration": "Border enforcement, migration, asylum, deportation, and entry policy.",
    "Crime & Public Safety": "Crime trends, policing, drugs/fentanyl, gangs, and local public safety.",
    "Courts & Legal Proceedings": "Courts, judges, trials, indictments, rulings, constitutional and legal claims.",
    "Foreign Affairs & Defense": "International conflicts, geopolitics, military posture, alliances, and national security.",
    "Media & Public Narrative": "Media coverage, press criticism, narrative framing, speech and culture debates.",
    "Other": "Fallback when no topical category is a clear fit.",
}

MAX_TAGS_PER_POST: int = 3


# Email notification — override via .env or environment variables.
SENDER_GMAIL = os.getenv("SENDER_GMAIL", "")          # sender address (must be @gmail.com)
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")  # 16-char App Password
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "")      # recipient address

if SENDER_GMAIL and not SENDER_GMAIL.endswith("@gmail.com"):
    logger.warning(
        "SENDER_GMAIL=%r does not end with @gmail.com; SMTP login will likely fail",
        SENDER_GMAIL,
    )


def raw_output_path(d: date) -> Path:
    """Return path to the raw output JSON file for a given date."""
    return RAW_OUTPUT_DIR / f"{d.isoformat()}.json"


def enriched_output_path(d: date) -> Path:
    """Return path to the enriched output JSON file for a given date."""
    return ENRICHED_OUTPUT_DIR / f"{d.isoformat()}.json"
