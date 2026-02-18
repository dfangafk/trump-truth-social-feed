"""Filter recent posts and write JSON output."""

import json
import logging

import pandas as pd

from ttsfeed.config import OUTPUT_DIR, TRUTH_SOCIAL_PROFILE_URL, output_path

logger = logging.getLogger(__name__)


def _safe_int(val, default: int = 0) -> int:
    """Convert a value to int, returning *default* on failure (NaN, None, etc.)."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def filter_recent_posts(
    df: pd.DataFrame,
    hours: int = 24,
    reference_time: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Return posts where created_at is within the last `hours` hours.

    Args:
        df: Archive DataFrame with a ``created_at`` column.
        hours: Size of the look-back window.
        reference_time: The "current" time to measure from. Defaults to now (UTC).
    """
    if reference_time is None:
        reference_time = pd.Timestamp.now("UTC")
    created = pd.to_datetime(df["created_at"], utc=True)
    cutoff = reference_time - pd.Timedelta(hours=hours)
    return df[created >= cutoff].copy()


def _post_to_dict(row: pd.Series) -> dict:
    """Convert a DataFrame row to the output dict format."""
    media = []
    if "media_attachments" in row.index and row["media_attachments"] is not None:
        val = row["media_attachments"]
        if isinstance(val, list):
            media = val
        elif isinstance(val, str):
            try:
                media = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                media = []

    return {
        "id": str(row.get("id", "")),
        "created_at": str(row.get("created_at", "")),
        "content": str(row.get("content", "")),
        "url": row.get("url", f"{TRUTH_SOCIAL_PROFILE_URL}/{row.get('id', '')}"),
        "media": media,
        "replies_count": _safe_int(row.get("replies_count", 0)),
        "reblogs_count": _safe_int(row.get("reblogs_count", 0)),
        "favourites_count": _safe_int(row.get("favourites_count", 0)),
    }


def save_output(
    new_posts_df: pd.DataFrame,
    total_archive: int,
    hours: int = 24,
    reference_time: pd.Timestamp | None = None,
) -> None:
    """Write the filtered posts to a JSON file."""
    if reference_time is None:
        reference_time = pd.Timestamp.now("UTC")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    new_posts = [_post_to_dict(row) for _, row in new_posts_df.iterrows()]

    result = {
        "as_of": reference_time.isoformat(),
        "window_hours": hours,
        "summary": {
            "total_posts_in_archive": total_archive,
            "new_posts_count": len(new_posts),
        },
        "new_posts": new_posts,
    }

    path = output_path(reference_time.date())
    with open(path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Saved output: %s (%d new posts)", path.name, len(new_posts))
