"""Configuration constants for the Truth Social data ingestion pipeline."""

from pathlib import Path
from datetime import date

# Archive URLs (CNN's publicly hosted Trump Truth Social archive)
ARCHIVE_URL_PARQUET = "https://ix.cnn.io/data/truth-social/truth_archive.parquet"
ARCHIVE_URL_JSON = "https://ix.cnn.io/data/truth-social/truth_archive.json"

# Directory paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
DIFFS_DIR = DATA_DIR / "diffs"

# Retention
SNAPSHOT_RETENTION_DAYS = 7


def snapshot_path(d: date) -> Path:
    """Return path to the snapshot Parquet file for a given date."""
    return SNAPSHOTS_DIR / f"{d.isoformat()}.parquet"


def latest_snapshot_path() -> Path:
    """Return path to the latest snapshot symlink/copy."""
    return SNAPSHOTS_DIR / "latest.parquet"


def diff_path(d: date) -> Path:
    """Return path to the diff JSON file for a given date."""
    return DIFFS_DIR / f"{d.isoformat()}.json"
