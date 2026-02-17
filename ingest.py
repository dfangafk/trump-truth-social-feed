"""Download the Truth Social archive and save daily Parquet snapshots."""

import io
import logging
import shutil
from datetime import date, timedelta

import pandas as pd
import requests

from config import (
    ARCHIVE_URL_JSON,
    ARCHIVE_URL_PARQUET,
    DIFFS_DIR,
    SNAPSHOT_RETENTION_DAYS,
    SNAPSHOTS_DIR,
    latest_snapshot_path,
    snapshot_path,
)

logger = logging.getLogger(__name__)


def download_archive(url: str = ARCHIVE_URL_PARQUET) -> tuple[bytes, str]:
    """Download the archive file. Returns (raw_bytes, format).

    Tries Parquet first; falls back to JSON on failure.
    """
    logger.info("Downloading archive from %s", url)
    try:
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        logger.info("Downloaded %.2f MB", len(resp.content) / 1_000_000)
        return resp.content, "parquet"
    except requests.RequestException as exc:
        if url == ARCHIVE_URL_PARQUET:
            logger.warning("Parquet download failed (%s), falling back to JSON", exc)
            return download_archive(ARCHIVE_URL_JSON)
        raise


def bytes_to_dataframe(raw_bytes: bytes, fmt: str = "parquet") -> pd.DataFrame:
    """Parse raw bytes into a DataFrame. Normalize id to string, sort by id."""
    if fmt == "parquet":
        df = pd.read_parquet(io.BytesIO(raw_bytes))
    else:
        df = pd.read_json(io.BytesIO(raw_bytes))

    if "id" in df.columns:
        df["id"] = df["id"].astype(str)

    df = df.sort_values("id").reset_index(drop=True)
    logger.info("Parsed %d posts", len(df))
    return df


def save_snapshot(df: pd.DataFrame, d: date) -> None:
    """Write DataFrame to dated snapshot and copy to latest.parquet."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    path = snapshot_path(d)
    df.to_parquet(path, index=False)
    logger.info("Saved snapshot: %s (%d posts)", path.name, len(df))

    shutil.copy2(path, latest_snapshot_path())


def cleanup_old_snapshots(d: date) -> None:
    """Remove snapshots older than SNAPSHOT_RETENTION_DAYS."""
    cutoff = d - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    for f in SNAPSHOTS_DIR.glob("????-??-??.parquet"):
        try:
            file_date = date.fromisoformat(f.stem)
        except ValueError:
            continue
        if file_date < cutoff:
            f.unlink()
            logger.info("Removed old snapshot: %s", f.name)


def ingest(d: date | None = None) -> pd.DataFrame:
    """Orchestrate: download, parse, save snapshot, cleanup. Returns DataFrame."""
    if d is None:
        d = date.today()

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    DIFFS_DIR.mkdir(parents=True, exist_ok=True)

    raw_bytes, fmt = download_archive()
    df = bytes_to_dataframe(raw_bytes, fmt)
    save_snapshot(df, d)
    cleanup_old_snapshots(d)

    return df
