"""Download, parse, and filter the Truth Social archive."""

import io
import logging

import pandas as pd
import requests

from ttsfeed.config import settings

logger = logging.getLogger(__name__)


def download_archive() -> bytes:
    """Download the JSON archive. Returns raw bytes."""
    url = settings.fetch.archive_url
    headers = {"User-Agent": settings.fetch.user_agent}
    logger.info("Downloading archive from %s", url)
    resp = requests.get(url, timeout=settings.fetch.timeout, headers=headers)
    resp.raise_for_status()
    logger.info("Downloaded %.2f MB", len(resp.content) / 1_000_000)
    return resp.content


def bytes_to_dataframe(raw_bytes: bytes) -> pd.DataFrame:
    """Parse raw JSON bytes into a DataFrame. Normalize id to string, sort by id."""
    df = pd.read_json(io.BytesIO(raw_bytes))

    if "id" in df.columns:
        df["id"] = df["id"].astype(str)

    df = df.sort_values("id").reset_index(drop=True)
    logger.info("Parsed %d posts", len(df))
    return df


def filter_recent_posts(
    df: pd.DataFrame,
    reference_time: pd.Timestamp | None = None,
    hours: int = 24,
) -> pd.DataFrame:
    """Return posts where created_at is within the last `hours` hours.

    Args:
        df: Archive DataFrame with a ``created_at`` column.
        reference_time: The "current" time to measure from. Defaults to now (UTC).
        hours: Size of the look-back window.
    """
    if reference_time is None:
        reference_time = pd.Timestamp.now("UTC")
    created = pd.to_datetime(df["created_at"], utc=True)
    cutoff = reference_time - pd.Timedelta(hours=hours)
    return df[created >= cutoff].copy()
