"""Serialize posts to JSON and write daily output files."""

import json
import logging
from pathlib import Path

import pandas as pd

from ttsenrich.analyze import EnrichResult
from ttsenrich.config import ENRICHED_OUTPUT_DIR, TRUTH_SOCIAL_PROFILE_URL, enriched_output_path

logger = logging.getLogger(__name__)


def _safe_int(val, default: int = 0) -> int:
    """Convert a value to int, returning *default* on failure (NaN, None, etc.)."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


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
    reference_time: pd.Timestamp | None = None,
    hours: int = 24,
    enrichment: EnrichResult | None = None,
    output_dir: Path | None = None,
    output_name: str | None = None,
) -> None:
    """Write the filtered posts to a JSON file.

    If ``output_name`` is provided, write to ``output_dir / output_name``.
    Otherwise use the date-based filename.
    """
    if reference_time is None:
        reference_time = pd.Timestamp.now("UTC")
    target_dir = output_dir if output_dir is not None else ENRICHED_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    sorted_df = new_posts_df.sort_values("created_at", ascending=False)
    new_posts = [_post_to_dict(row) for _, row in sorted_df.iterrows()]

    summary: dict = {
        "total_posts_in_archive": total_archive,
        "new_posts_count": len(new_posts),
    }
    if enrichment is not None:
        for post in new_posts:
            post["categories"] = enrichment.post_categories.get(post["id"], [])
        summary["daily_summary"] = enrichment.daily_summary

    result = {
        "as_of": reference_time.isoformat(),
        "window_hours": hours,
        "summary": summary,
        "new_posts": new_posts,
    }

    if output_name:
        path = target_dir / output_name
    elif output_dir is None:
        path = enriched_output_path(reference_time.date())
    else:
        path = target_dir / f"{reference_time.date().isoformat()}.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Saved output: %s (%d new posts)", path.name, len(new_posts))
