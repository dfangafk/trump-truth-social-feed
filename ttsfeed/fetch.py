"""Download the Truth Social archive and parse into a DataFrame."""

import io
import logging

import pandas as pd
import requests

from ttsfeed.config import ARCHIVE_URL_JSON, ARCHIVE_URL_PARQUET

logger = logging.getLogger(__name__)

HTTP_HEADERS = {"User-Agent": "ttsfeed/0.1 (Truth Social archive tracker)"}


def download_archive(url: str = ARCHIVE_URL_PARQUET) -> tuple[bytes, str]:
    """Download the archive file. Returns (raw_bytes, format).

    Tries Parquet first; falls back to JSON on failure.
    """
    logger.info("Downloading archive from %s", url)
    fmt = "parquet" if url == ARCHIVE_URL_PARQUET else "json"
    try:
        resp = requests.get(url, timeout=120, headers=HTTP_HEADERS)
        resp.raise_for_status()
        logger.info("Downloaded %.2f MB", len(resp.content) / 1_000_000)
        return resp.content, fmt
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
